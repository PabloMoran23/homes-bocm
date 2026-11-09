"""Current PGOU document inventory published by Ugao-Miraballes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.ugao-miraballes.eus'
INVENTORY = BASE + '/es-ES/Servicios/Urbanismo/Paginas/default.aspx'
PREFIX = '/es-ES/Servicios/Urbanismo/Paginas/pgou-aprobacion-definitiva'


def municipal_url(page, href):
    url = urljoin(page, href)
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != urlsplit(BASE).netloc:
        return None
    return url.split('#')[0]


def parse_page(html, url):
    """Return every linked PGOU section, pagination URL and document."""
    soup = BeautifulSoup(html, 'html.parser')
    pages, docs = set(), {}
    for a in soup.select('a[href]'):
        title = a.get_text(' ', strip=True)
        href = a['href']
        pagination = (a.get('rel') and 'next' in a['rel']) or title.lower() in {'siguiente', 'next', 'hurrengoa', '>', '»'} or 'paged=true' in href.lower()
        target = municipal_url(url, href)
        if pagination and href not in {'', '#'} and (not target or not urlsplit(target).path.startswith(PREFIX)):
            raise ValueError('Uncovered pagination outside PGOU sections')
        if not target:
            continue
        path = unquote(urlsplit(target).path)
        if path.startswith(PREFIX) and path.endswith('.aspx'):
            pages.add(target)
        elif path.startswith('/es-ES/Servicios/Urbanismo/') and path.lower().endswith('.pdf'):
            docs[target] = {'titulo': title or path.rsplit('/', 1)[-1], 'url': target,
                            'url_indice': url}
    return pages, list(docs.values())


class UgaoMiraballesAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=30, headers={'User-Agent': 'municipio-ugao-miraballes/1.0'})
        response.raise_for_status()
        if len(response.content) > 5_000_000:
            raise ValueError('Oversized PGOU index; review source')
        if urlsplit(response.url).netloc != urlsplit(BASE).netloc:
            raise ValueError('Unexpected source redirect')
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
        return response.text

    def extract(self, fetch):
        roots, _ = parse_page(fetch(INVENTORY), INVENTORY)
        if not roots:
            raise ValueError('Municipal inventory no longer links the current PGOU')
        pending, visited, docs = set(roots), set(), {}
        while pending:
            url = min(pending)
            pending.remove(url)
            if url in visited:
                continue
            visited.add(url)
            if len(visited) > 100:
                raise ValueError('Unexpected PGOU section growth; no partial output written')
            pages, documents = parse_page(fetch(url), url)
            pending.update(pages - visited)
            for document in documents:
                key = document['url']
                if key not in docs:
                    docs[key] = {**document, 'indices': []}
                docs[key]['indices'].append(url)
        if not docs:
            raise ValueError('Current PGOU has no source documents')
        return [{
            'id': 'ugao-miraballes-pgou', 'municipio': 'Ugao-Miraballes',
            'codigo_ine': '48065', 'provincia': 'Bizkaia',
            'titulo': 'Plan General de Ordenación Urbana de Ugao-Miraballes',
            'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación definitiva',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'url': sorted(roots)[0],
            'source': 'ayuntamiento', 'origen': 'inventario_municipal_pgou',
            'source_urls': [INVENTORY] + sorted(visited),
            'documentos': [docs[key] for key in sorted(docs)],
            'descripcion': 'PGOU publicado en la sección municipal de aprobación definitiva. '
                           'Memorias, planos y anexos agrupados en un instrumento. '
                           'La fecha de carga o modificación de ficheros no se interpreta como aprobación.',
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'coverage': 'Solo el PGOU de aprobación definitiva enlazado desde Urbanismo; '
                        'no cubre antecedentes, otros instrumentos ni licencias.',
        }]

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        return self._write(out_jsonl, self.extract(self._fetch))

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
