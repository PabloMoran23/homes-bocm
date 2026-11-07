"""Document inventory of Sanlúcar la Mayor (Sevilla), not a licence register."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://transparencia.sanlucarlamayor.es/es/transparencia/'
          'indicadores-de-transparencia/indicador/'
          'Plan-General-de-Ordenacion-Urbana-PGOU-e-Innovaciones-de-Planeamiento')
PAGE_KEY = 'pagegalleryfiles-1-1'
DOC_PATH = '/export/sites/sanlucarlamayor/es/transparencia/.galleries/IND-50-/'
LIMITATIONS = [
    'Inventario documental de planeamiento, no censo completo de proyectos u obras.',
    'No acredita vigencia, aprobación ni concesión de licencias; sin fechas inferidas ni coordenadas.',
    'Se excluyen ordenanza, zonificación acústica y láminas sin instrumento identificado.',
    'PGOM: solo documentación Fase1 del inventario; no incluye el avance anunciado en 2025.',
    'Enlaces documentales conservados; no se analiza íntegramente el contenido de cada PDF.',
]


def page_url(number):
    return SOURCE + '?' + PAGE_KEY + '=' + str(number)


def parse_page(html, url):
    """Return source documents and every advertised page; reject schema drift."""
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.select('table.table')
    if len(tables) != 1 or not tables[0].select_one('thead'):
        raise ValueError('Missing unambiguous document inventory')
    docs = []
    for a in tables[0].select('tbody a[href]'):
        target = urljoin(url, a['href'])
        p = urlparse(target)
        title = a.get_text(' ', strip=True)
        if (p.hostname != urlparse(SOURCE).hostname or not p.path.startswith(DOC_PATH)
                or not re.search(r'\.(pdf|jpg)$', p.path, re.I) or not title):
            raise ValueError('Unexpected inventory document: ' + target)
        docs.append({'titulo': title, 'url': target, 'inventory_url': url})
    if not docs:
        raise ValueError('Empty document inventory')
    pages = set()
    current = soup.select_one('a.currentpagelink')
    expected = int(parse_qs(urlparse(url).query).get(PAGE_KEY, ['1'])[0])
    if current is None or current.get('numpag') != str(expected):
        raise ValueError('Missing/mismatched current page; pagination may have been ignored')
    for a in soup.select('a[href]'):
        if PAGE_KEY not in a['href']:
            continue
        target = urldefrag(urljoin(url, a['href']))[0]
        p = urlparse(target)
        query = parse_qs(p.query)
        if (p.hostname != urlparse(SOURCE).hostname or p.path.rstrip('/') != urlparse(SOURCE).path
                or set(query) != {PAGE_KEY} or len(query[PAGE_KEY]) != 1
                or not query[PAGE_KEY][0].isdigit()):
            raise ValueError('Unexpected pagination URL')
        number = int(query[PAGE_KEY][0])
        if number < 1:
            raise ValueError('Invalid page number')
        pages.add(number)
    if expected not in pages:
        raise ValueError('Incomplete pagination metadata')
    return docs, pages


def instrument(title):
    """Group only explicit title families; no guessed approval dates or phases."""
    name = re.sub(r'^\d+(?:\.\d+)*\.', '', title).strip()
    if name.startswith(('DETERMINACIONES SUELO URBANO', 'PATRIMONIO ARQUITECTONICO',
                        'ORDENANZA MUNICIPAL', 'ZONIFICACION ACUSTICA')):
        return None
    if name == 'NNSS 1982':
        return 'nnss-1982', 'Normas Subsidiarias 1982'
    if name.startswith('PGOU_LOUA '):
        return 'pgou-loua', 'PGOU — adaptación a la LOUA'
    m = re.match(r'Innv nº(\d+)_', name)
    if m:
        return 'innovacion-' + m[1], 'Innovación nº ' + m[1] + ' del planeamiento'
    if name.startswith('PGOM_'):
        return 'pgom', 'Plan General de Ordenación Municipal (PGOM)'
    if re.match(r'^(PERI |MP |PP\d+-)', name):
        # The full instrument title, rather than its document URL, identifies it.
        key = re.sub(r'[^a-z0-9]+', '-', name.casefold()).strip('-')
        return key, name
    raise ValueError('Unreviewed inventory title: ' + title)


def group_documents(documents):
    rows = {}
    for doc in documents:
        family = instrument(doc['titulo'])
        if family is None:
            continue
        key, title = family
        if key not in rows:
            rows[key] = {
                'id': 'sanlucar-la-mayor-plan-' + key,
                'municipio': 'Sanlúcar la Mayor', 'codigo_ine': '41087',
                'provincia': 'Sevilla', 'titulo': title,
                'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
                'origen': 'inventario_documental_planeamiento', 'url': doc['url'],
                'inventory_url': SOURCE, 'documentos': [],
                'publication_ready': False, 'geometry_status': 'unavailable',
                'coverage': 'partial_document_inventory',
            }
        if doc['url'] not in {d['url'] for d in rows[key]['documentos']}:
            rows[key]['documentos'].append(dict(doc))
    if not rows:
        raise ValueError('No identified planning instruments')
    return list(rows.values())


class SanlucarLaMayorAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        pending, visited, documents, fingerprints = {1}, set(), [], set()
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-inventory/1.0'
            while pending:
                number = min(pending)
                pending.remove(number)
                url = page_url(number)
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if urldefrag(response.url)[0] != url:
                    raise ValueError('Unexpected inventory redirect: ' + response.url)
                response.encoding = 'utf-8'
                docs, pages = parse_page(response.text, url)
                fingerprint = tuple(d['url'] for d in docs)
                if fingerprint in fingerprints:
                    raise ValueError('Repeated inventory page; refusing partial extraction')
                fingerprints.add(fingerprint)
                visited.add(number)
                source_urls.append(url)
                documents.extend(docs)
                pending.update(pages - visited)
                if self.config.get('capture_dir'):
                    capture = Path(self.config['capture_dir'])
                    capture.mkdir(parents=True, exist_ok=True)
                    (capture / f'inventory-{number}.html').write_text(response.text, encoding='utf-8')
        if visited != set(range(1, max(visited) + 1)):
            raise ValueError('Gap in inventory pagination')
        rows = group_documents(documents)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'pages': len(visited),
                'listed_documents': len(documents),
                'retained_documents': sum(len(r['documentos']) for r in rows),
                'source_urls': source_urls, 'limitations': LIMITATIONS}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
