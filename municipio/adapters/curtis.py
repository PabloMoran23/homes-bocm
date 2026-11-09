"""Curtis PXOM inventory: municipal detail pages with instrument documents.

This deliberately covers the documented modifications and reparcelaciones, not
licences, procurement, the generic regional registry link or ambiguous ZIP labels.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://curtis.gal/index.php/es/urbanismo/pxom'
LIMITATIONS = [
    'Partial coverage: only documented municipal detail pages linked by the PXOM inventory.',
    'Generic PXOM regional inventory and convenios links are references, not extracted instruments.',
    'Modificación del Plan Parcial ZIP has an ambiguous PXOM N2 filename; excluded pending verification.',
    'No verified approval/publication dates, current legal validity, licences or project geometry.',
]


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    # This inventory is a single Joomla article. Never accept a newly paged
    # inventory as a complete snapshot, including pagination outside the article.
    if soup.select('.pagination a[href], a[rel~=next], link[rel~=next]'):
        raise ValueError('Pagination detected; extend traversal before extracting')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'seguinte', 'next', '›', '»'} and a['href'] not in {'', '#'}:
            raise ValueError('Pagination detected')
    content = soup.select_one('article.item .content')
    if content is None:
        raise ValueError('Missing municipal article content')
    return content


def parse_inventory(html):
    content = _content(html)
    details = {}
    excluded = []
    for a in content.select('a[href]'):
        title = a.get_text(' ', strip=True)
        url = urljoin(SOURCE, a['href'])
        if urlparse(url).hostname == 'curtis.gal' and '/index.php/' in urlparse(url).path:
            if re.search(r'modificaci[oó]n|reparcelaci[oó]n', title, re.I):
                details[url] = title
            else:
                raise ValueError(f'Unreviewed municipal inventory entry: {title}')
        else:
            # Retain all out-of-scope references in the extraction report.
            excluded.append({'titulo': title, 'url': url})
    if not details:
        raise ValueError('No supported detail pages in the current PXOM inventory')
    return list(details), excluded


def _documents(block, page_url):
    docs = {}
    for a in block.select('a[href]'):
        url = urljoin(page_url, a['href'])
        if not urlparse(url).path.lower().endswith('.pdf'):
            continue
        if urlparse(url).hostname != 'curtis.gal':
            raise ValueError('Unexpected document host')
        parent = a.find_parent('li')
        label = (parent or a).get_text(' ', strip=True)
        docs.setdefault(url, {'titulo': label or unquote(urlparse(url).path.rsplit('/', 1)[-1]),
                              'url': url, 'source_url': page_url})
    return list(docs.values())


def _row(key, title, page_url, docs, description, kind):
    if not docs:
        raise ValueError(f'Instrument lacks documents: {title}')
    return {
        'id': 'curtis-proy-' + key, 'municipio': 'Curtis', 'codigo_ine': '15032',
        'provincia': 'A Coruña', 'titulo': title, 'tipo': kind,
        'url': page_url, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
        'origen': 'inventario_municipal_pxom', 'documentos': docs,
        'descripcion': description, 'fecha_publicacion': None,
        'fecha_acuerdo': None, 'fecha_aprob': None,
        'geometry': None, 'lat': None, 'lon': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


def parse_detail(html, page_url):
    content = _content(html)
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('article.item h1')
    title = heading.get_text(' ', strip=True) if heading else ''
    if re.search(r'reparcelaci[oó]n.*APE[- ]?4', title, re.I):
        docs = _documents(content, page_url)
        return [_row('reparcelacion-ape-4', title, page_url, docs, title, 'reparcelacion')]
    # Two independent instruments share one notice. Read headings and adjacent
    # document lists, never group by MPN folder: the site's MP7 form is in MPN6.
    if re.search(r'modificaci[oó]n', title, re.I):
        records = []
        for p in content.find_all('p', recursive=False):
            instrument = p.get_text(' ', strip=True)
            match = re.match(r'Modificaci[oó]n puntual n[º°.]?\s*(\d+)\s+do PXOM\b', instrument, re.I)
            if not match:
                continue
            block = p.find_next_sibling()
            if block is None or block.name != 'ul':
                raise ValueError('Missing instrument document list')
            description = '\n'.join(x.get_text(' ', strip=True) for x in content.find_all('p', recursive=False))
            records.append(_row('pxom-mp-' + match[1], instrument, page_url,
                                _documents(block, page_url), description, 'modificacion_planeamiento'))
        if records:
            if len({r['id'] for r in records}) != len(records):
                raise ValueError('Duplicate modification headings')
            # All PDF links must be assigned; changed markup must not drop a plan.
            assigned = {d['url'] for r in records for d in r['documentos']}
            if assigned != {d['url'] for d in _documents(content, page_url)}:
                raise ValueError('Unassigned modification documents')
            return records
    raise ValueError(f'Unsupported detail page: {title}')


class CurtisAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-curtis/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != 'curtis.gal':
            raise ValueError('Unexpected municipal redirect')
        response.encoding = 'utf-8'
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        urls, excluded = parse_inventory(self._fetch(SOURCE))
        rows = {}
        for url in urls:
            for row in parse_detail(self._fetch(url), url):
                if row['id'] in rows and rows[row['id']] != row:
                    raise ValueError('Conflicting instrument records')
                rows[row['id']] = row
        self._write(out_jsonl, list(rows.values()))
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, *urls],
                'excluded_references': excluded, 'limitations': LIMITATIONS,
                'coverage': 'partial_municipal_pxom_document_inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of this bounded inventory; state is not a date cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
