"""Selva's official planning document trees, grouped by instrument."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://ajselva.net'
URBANISME = BASE + '/ca/ajuntament/departament-durbanisme'
INVENTORIES = (
    (BASE + '/ca/arxius-i-documents/projecte-de-delimitacio-del-sol-urba-0',
     'Projecte de delimitació del sol urbà', 'delimitacion_suelo_urbano'),
    (BASE + '/ca/arxius-i-documents/cataleg-delements-i-espais-protegits-del-terme-municipal-de-selva',
     "Catàleg d'elements i espais protegits del Terme Municipal de Selva", 'catalogo_proteccion'),
)


def official_url(base, href):
    url = urljoin(base, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'ajselva.net':
        raise ValueError('Unexpected non-municipal source: ' + url)
    return url


def parse_page(html, url):
    """Return only inventory children or actual attached files, never navigation."""
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('main .layout-content')
    if content is None or content.select_one('h1') is None:
        raise ValueError('Missing Selva document content: ' + url)
    # Refuse any unhandled pagination, including numeric pagers.
    if content.select('.pager, [rel~=next], .pagination') or any(
        'page=' in a.get('href', '') for a in content.select('a[href]')
    ):
        raise ValueError('Pagination requires review; refusing a truncated inventory')
    title = content.select_one('h1').get_text(' ', strip=True)
    children = []
    for a in content.select('.taxonomy-term-files a[href]'):
        if a.select_one('h3'):
            child = official_url(url, a['href'])
            if not urlparse(child).path.startswith('/ca/arxius-i-documents/'):
                raise ValueError('Unexpected inventory child')
            children.append(child)
    docs = []
    for a in content.select('article.node-file-or-document a[download][href]'):
        file_url = official_url(url, a['href'])
        if not urlparse(file_url).path.startswith('/sites/cilma_selva/files/'):
            raise ValueError('Unexpected document path')
        block = a.parent
        heading = block.select_one('h3')
        if heading is None:
            raise ValueError('Attachment has no title')
        label = heading.get_text(' ', strip=True)
        # BOIB label dates describe the bulletin, not the agreement or upload.
        match = re.search(r'boib.*?\b(\d{2})-(\d{2})-(\d{4})', label, re.I)
        published = date(int(match[3]), int(match[2]), int(match[1])).isoformat() if match else None
        docs.append({'titulo': label, 'url': file_url, 'url_origen': url,
                     'fecha_publicacion_boib': published})
    if not children and not docs:
        raise ValueError('Empty or changed document inventory: ' + url)
    return title, list(dict.fromkeys(children)), docs


class SelvaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        if slug != 'selva':
            raise ValueError('This adapter is exclusively for Selva (07058)')
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        with requests.get(url, timeout=35, stream=True,
                          headers={'User-Agent': 'municipio-selva/1.0'}) as response:
            response.raise_for_status()
            official_url(BASE, response.url)
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected an HTML document inventory')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Inventory too large; refusing partial response')
                chunks.append(chunk)
            raw = b''.join(chunks)
            if self.config.get('capture_dir'):
                directory = Path(self.config['capture_dir'])
                directory.mkdir(parents=True, exist_ok=True)
                name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
                (directory / name).write_bytes(raw)
            self.source_urls.append(url)
            return raw.decode('utf-8')

    def collect_projects(self, fetch):
        rows = []
        for root, expected_title, kind in INVENTORIES:
            pending, visited, documents = [root], set(), {}
            title = None
            while pending:
                url = pending.pop(0)
                if url in visited:
                    continue
                if len(visited) >= 150:
                    raise ValueError('Document tree exceeds reviewed bound')
                visited.add(url)
                page_title, children, docs = parse_page(fetch(url), url)
                if url == root:
                    title = page_title
                    if title != expected_title:
                        raise ValueError('Planning instrument identity changed')
                pending.extend(child for child in children if child not in visited)
                for doc in docs:
                    existing = documents.get(doc['url'])
                    if existing:
                        existing['paginas_origen'] = sorted(set(existing['paginas_origen'] + [doc['url_origen']]))
                    else:
                        documents[doc['url']] = {**doc, 'paginas_origen': [doc['url_origen']]}
            if not documents:
                raise ValueError('Instrument lacks actual source documents')
            rows.append({
                'id': 'selva-proy-' + hashlib.sha256(root.encode()).hexdigest()[:16],
                'municipio': 'Selva', 'provincia': 'Illes Balears', 'codigo_ine': '07058',
                'titulo': title, 'tipo': kind, 'fase': None,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': root, 'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
                'documentos': sorted(documents.values(), key=lambda d: d['url']),
                'paginas_fuente': sorted(visited),
                'descripcion': 'Instrumento publicado en el inventario municipal de urbanismo. '
                    'Documentos agrupados; fechas de BOIB conservadas por documento. '
                    'Sin inferir fecha de acuerdo, aprobación o vigencia desde etiquetas o cargas de archivos.',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'geometry_status': 'Cartografía PDF enlazada; geometría vectorial no extraída',
            })
        return rows

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        rows = self.collect_projects(self._fetch)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'documents': sum(len(row['documentos']) for row in rows), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh; no date cursor can hide corrections or undated files.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
