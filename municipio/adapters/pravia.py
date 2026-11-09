"""Municipal planning inventory: instruments, not one project per PDF."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.ayto-pravia.es/urbanismo-y-vivienda'
HOST = 'www.ayto-pravia.es'
SECTIONS = {
    'PLAN GENERAL DE ORDENACIÓN DEL CONCEJO DE PRAVIA': ('pgo', 'Plan General de Ordenación del Concejo de Pravia - Texto Refundido'),
    'CATÁLOGO URBANÍSTICO': ('catalogo', 'Catálogo Urbanístico de Pravia'),
    'PLAN ESPECIAL DE PROTECCIÓN DEL CASCO ANTIGUO DE PRAVIA': ('pepc', 'Plan Especial de Protección del Casco Antiguo de Pravia'),
}


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    # These pages are static inventories. If pagination appears, refuse a partial
    # snapshot until its semantics can be reviewed and traversal implemented.
    for a in soup.select('a[href]'):
        label = ' '.join((text(a), a.get('aria-label', ''), a.get('title', ''))).lower()
        if a['href'].strip() not in {'', '#'} and (
            'next' in a.get('rel', []) or any(w in label for w in ('siguiente', 'next page'))
        ):
            raise ValueError('Uncovered pagination in Pravia inventory')
    if soup.select('.lfr-pagination, .pagination, .taglib-page-iterator'):
        raise ValueError('Pagination controls require review')
    blocks = soup.select('.journal-content-article .detalle')
    if len(blocks) != 1:
        raise ValueError('Missing or ambiguous Pravia inventory content')
    return blocks[0]


def link_info(a, page):
    title = text(a)
    href = a.get('href', '').strip()
    if not href or href == '#':
        return {'titulo': title, 'url': None, 'source_url': page, 'status': 'missing_link'}
    url = urljoin(page, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != HOST:
        raise ValueError(f'Unreviewed external inventory link: {url}')
    if not (parsed.path.startswith('/documents/') or parsed.path == '/c/document_library/get_file'
            or parsed.path.startswith('/web/ayto-pravia/')):
        raise ValueError(f'Unreviewed document route: {url}')
    return {'titulo': title, 'url': url, 'source_url': page}


class PraviaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        block = content(html)
        rows = {}
        current = None
        for node in block.find_all(['h3', 'a']):
            if node.name == 'h3':
                heading = text(node)
                if heading in SECTIONS:
                    key, title = SECTIONS[heading]
                    if key in rows:
                        raise ValueError('Duplicate instrument section')
                    current = {
                        'id': f'pravia-proy-{key}', 'municipio': 'Pravia',
                        'codigo_ine': '33051', 'provincia': 'Asturias',
                        'titulo': title, 'tipo': 'planeamiento_urbanistico',
                        'fecha': None, 'fecha_publicacion': None,
                        'fecha_acuerdo': None, 'fecha_aprob': None,
                        'url': SOURCE, 'source': 'ayuntamiento',
                        'origen': 'inventario_municipal_planeamiento',
                        'documentos': [], 'enlaces_incompletos': [],
                        'paginas_documentos': [], 'geometry': None,
                        'lat': None, 'lon': None, 'geometry_status': 'unavailable',
                        'publication_ready': False,
                    }
                    rows[key] = current
                elif heading == 'Plusvalía':
                    current = None  # unrelated tax form, explicitly excluded
                elif heading not in {'Contenido del documento', 'Documentación gráfica'}:
                    raise ValueError(f'Unreviewed inventory section: {heading}')
            elif current is not None:
                item = link_info(node, SOURCE)
                target = 'enlaces_incompletos' if item['url'] is None else 'documentos'
                if item not in current[target]:
                    current[target].append(item)
        if set(rows) != {value[0] for value in SECTIONS.values()} or any(not r['documentos'] for r in rows.values()):
            raise ValueError('Planning instrument inventory missing required sections/documents')
        return list(rows.values())

    @staticmethod
    def parse_document_page(html, url):
        items = [link_info(a, url) for a in content(html).select('a[href]')]
        if not items or not any(i['url'] for i in items):
            raise ValueError('Empty nested document inventory')
        return items

    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-pravia/1.0 (public planning inventory)'
        })
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST or 'html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Unexpected inventory response')
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (directory / name).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        rows = self.parse_inventory(self._fetch(SOURCE))
        cache = {}
        for row in rows:
            pending = list(row['documentos'])
            row['documentos'] = []
            seen = set()
            while pending:
                item = pending.pop(0)
                url = item['url']
                if url in seen:
                    continue
                seen.add(url)
                if urlparse(url).path.startswith('/web/ayto-pravia/'):
                    row['paginas_documentos'].append(item)
                    if url not in cache:
                        cache[url] = self.parse_document_page(self._fetch(url), url)
                    for child in cache[url]:
                        if child['url'] is None:
                            row['enlaces_incompletos'].append(child)
                        else:
                            pending.append(child)
                else:
                    row['documentos'].append(item)
            row['cobertura'] = 'Inventario municipal parcial; sin registro de licencias ni histórico completo de modificaciones. Enlaces documentales conservados; descarga integral de PDFs no verificada.'
        return {**self._write(out_jsonl, rows), 'source_urls': [SOURCE, *cache], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
