"""Abadiño's public planning document inventory (anonymous SharePoint reads)."""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.xn--abadio-0wa.org'
AREA = BASE + '/es-ES/Servicios/Urbanismo'
INDEX = AREA + "/_api/web/lists/getbytitle('Páginas')/items?$select=Id,Title,File/ServerRelativeUrl&$expand=File&$top=100"
LIMITATIONS = [
    'Cobertura parcial: PGOU y modificaciones NNSS publicadas en las páginas de Urbanismo; no es un registro completo de obras ni de expedientes vigentes.',
    'Las fases describen la documentación municipal publicada, no certifican el estado jurídico actual. No se interpretan fechas de archivo o de carga como acuerdos o publicaciones.',
    'Sin fechas de acuerdo, aprobación o publicación extraídas; sin geometría verificada. Planos PDF conservados como enlaces, no convertidos en coordenadas.',
    'Licencias deshabilitadas: formularios, consultas, contratación y noticias excluidos.',
]


def canonical(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != urlsplit(BASE).netloc:
        raise ValueError('Unexpected source host or protocol')
    return urlunsplit((parts.scheme, parts.netloc, quote(unquote(parts.path), safe='/'), parts.query, ''))


class AbadinoAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='abadino', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []

    def _get(self, url):
        url = canonical(url)
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'municipio-abadino/1.0',
            'Accept': 'application/json;odata=verbose' if '/_api/' in url else 'text/html',
        })
        response.raise_for_status()
        canonical(response.url)
        self.source_urls.append(url)
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            suffix = '.json' if '/_api/' in url else '.html'
            (folder / (hashlib.sha256(url.encode()).hexdigest()[:16] + suffix)).write_bytes(response.content)
        time.sleep(0.1)
        return response

    def inventory(self):
        """Follow all OData pages, failing on cycles or invalid continuations."""
        url, seen, items = INDEX, set(), {}
        while url:
            url = canonical(url)
            if not url.startswith(AREA + '/_api/') or url in seen:
                raise ValueError('Invalid or repeated inventory continuation')
            seen.add(url)
            payload = self._get(url).json()['d']
            for item in payload['results']:
                path = item['File']['ServerRelativeUrl']
                if not path.startswith(urlsplit(AREA).path + '/Paginas/'):
                    raise ValueError('Unexpected page outside Urbanismo inventory')
                page = canonical(urljoin(BASE, path))
                if page in items and items[page] != item['Title']:
                    raise ValueError('Conflicting inventory page titles')
                items[page] = item['Title']
            continuation = payload.get('__next')
            url = urljoin(url, continuation) if continuation else None
        if not items:
            raise ValueError('Empty planning page inventory')
        return items

    @staticmethod
    def root_kind(title):
        if title == 'Plan General de Ordenación Urbana':
            return 'PGOU'
        if re.match(r'^(?:MPNS\b|Modif NNSS\b|Aprobación Provisional NNSS\b)', title, re.I):
            return 'modificacion_normas_subsidiarias'
        return None

    @staticmethod
    def parse_page(html, page_url):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('#main-content')
        if main is None:
            raise ValueError('Municipal content container missing')
        docs, children = {}, set()
        for anchor in main.select('a[href]'):
            href = anchor['href']
            label = anchor.get_text(' ', strip=True)
            if label.lower() in {'siguiente', 'next', 'hurrengoa', 'sig.', '›', '»'} or 'next' in anchor.get('rel', []):
                raise ValueError('Unreviewed HTML pagination; refusing partial output')
            absolute = urljoin(page_url, href)
            parts = urlsplit(absolute)
            if parts.netloc != urlsplit(BASE).netloc:
                continue
            path = unquote(parts.path)
            if not path.startswith(urlsplit(AREA).path + '/'):
                continue
            url = canonical(absolute)
            if path.lower().endswith('.pdf'):
                docs[url] = {'titulo': label or path.rsplit('/', 1)[-1], 'url': url,
                             'url_procedencia': page_url}
            elif '/Paginas/' in path and path.rsplit('/', 1)[-1].lower() != 'default.aspx':
                children.add(url)
        return list(docs.values()), children

    def extract(self, pages):
        roots = {url: self.root_kind(title) for url, title in pages.items() if self.root_kind(title)}
        if not roots:
            raise ValueError('No supported planning instruments in municipal inventory')
        records = []
        for root, kind in sorted(roots.items()):
            pending, visited, documents = {root}, set(), {}
            while pending:
                url = min(pending)
                pending.remove(url)
                if url in visited:
                    continue
                inventory_url = url.split('?', 1)[0]
                if inventory_url not in pages:
                    raise ValueError('Linked planning page absent from complete inventory: ' + url)
                visited.add(url)
                if len(visited) > 200:
                    raise ValueError('Planning graph exceeds reviewed bound; no output written')
                docs, children = self.parse_page(self._get(url).text, url)
                for doc in docs:
                    previous = documents.setdefault(doc['url'], dict(doc, procedencias=[]))
                    previous['procedencias'].append(url)
                pending.update(child for child in children if child not in visited and (child not in roots or child == root))
            if not documents:
                raise ValueError('Planning instrument has no source documents')
            texts = ' '.join(pages[url.split('?', 1)[0]] for url in visited) + ' ' + ' '.join(d['titulo'] for d in documents.values())
            phase = None
            for pattern, label in [
                (r'segunda aprobaci[oó]n inicial|2[ºª]\s+apro\w*aci[oó]n inicial', 'segunda aprobación inicial'),
                (r'aprobaci[oó]n provisional', 'aprobación provisional'),
                (r'aprobaci[oó]n inicial', 'aprobación inicial'),
            ]:
                if re.search(pattern, texts, re.I):
                    phase = label
                    break
            records.append({
                'id': 'abadino-proy-' + hashlib.sha256(root.encode()).hexdigest()[:16],
                'municipio': 'Abadiño', 'codigo_ine': '48001', 'provincia': 'Bizkaia',
                'titulo': pages[root], 'tipo': kind, 'fase': phase,
                'fase_provenance': 'Rótulos de páginas/documentos municipales; no acredita vigencia ni aprobación definitiva',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': root, 'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
                'paginas_fuente': sorted(visited),
                'documentos': [documents[key] for key in sorted(documents)],
                'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                'publication_ready': False, 'cobertura': 'parcial',
            })
        return records

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        rows = self.extract(self.inventory())
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
