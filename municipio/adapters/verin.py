"""Verín's municipal planning catalogue and complete Snap2HTML file inventories.

Catalogue presence is not evidence of current legal validity. Legacy frames/maps
are explicitly reported as excluded; file timestamps are never approval dates.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.verin.es/planeamento/'
LEGACY_PATHS = {'/pxom2012', '/pepri'}
LIMITATIONS = [
    'Partial municipal planning catalogue: legacy PXOM 2012 frames and PEPRI '
    'image-map viewers are excluded and reported individually.',
    'Catalogue presence and source descriptions do not establish current legal '
    'validity, approval or execution; historical documents may be included.',
    'No granted licences, public-works register, inferred dates or coordinates.',
    'File links are inventoried in full; their contents are not all downloaded '
    'or interpreted. Filesystem timestamps are not publication/agreement dates.',
]


def reject_pagination(soup):
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if ('next' in a.get('rel', []) or label in {
            'next', 'siguiente', 'seguinte', 'seguinte páxina', 'próxima', '›', '»'
        } or a.find_parent(class_=re.compile(r'pagination|paginacion|paxinacion', re.I))):
            if a['href'] not in {'', '#'}:
                raise ValueError('Pagination detected; refusing an incomplete catalogue')


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    reject_pagination(soup)
    cards = soup.select('a[data-cvu-folla][href]')
    if not cards:
        raise ValueError('Municipal planning catalogue missing')
    counters = soup.select('.cvu__conta')
    if counters:
        counts = [re.fullmatch(r'(\d+) documentos?', c.get_text(strip=True)) for c in counters]
        if not all(counts) or sum(int(c[1]) for c in counts) != len(cards):
            raise ValueError('Catalogue card count differs from declared inventory')
    rows = {}
    for card in cards:
        title = card.select_one('h3.cvu__folla-tit')
        desc = card.select_one('.cvu__desc')
        target = urljoin(url, card['href']).split('#')[0]
        if not title or urlparse(target).hostname != 'urbanismo.verin.gal':
            raise ValueError('Unrecognised planning card or non-municipal target')
        rows.setdefault(target, {
            'id': 'verin-plan-' + hashlib.sha256(target.rstrip('/').encode()).hexdigest()[:16],
            'municipio': 'Verín', 'codigo_ine': '32085', 'provincia': 'Ourense',
            'titulo': title.get_text(' ', strip=True),
            'descripcion': desc.get_text(' ', strip=True) if desc else '',
            'tipo': 'planeamiento_urbanistico', 'url': target,
            'inventory_url': url, 'source': 'ayuntamiento',
            'origen': 'catalogo_municipal_planeamento',
            'vigencia_verificada': False, 'geometry_status': 'unavailable',
            'publication_ready': False,
        })
    return list(rows.values())


def parse_documents(html, url):
    """Decode data arrays as JSON, without executing any external JavaScript."""
    soup = BeautifulSoup(html, 'html.parser')
    reject_pagination(soup)
    arrays = [json.loads(x) for x in re.findall(r'^D\.p\((\[.*\])\)\s*;?\s*$', html, re.M)]
    root_match = re.search(r'var sourceRoot = ("[^"\n]*");', html)
    count_match = re.search(r'var numberOfFiles = (\d+);', html)
    stats = soup.select_one('.app_header_stats')
    stats_match = re.search(r'(\d+) files in (\d+) folders', stats.get_text() if stats else '')
    if not arrays or not root_match or not count_match or not stats_match:
        raise ValueError('Unsupported or incomplete Snap2HTML inventory')
    root = json.loads(root_match[1])
    for key in ('linkRoot', 'linkProtocol'):
        if not re.search(r'var ' + key + r' = "";', html):
            raise ValueError('Unreviewed Snap2HTML link mapping')
    files = []
    for directory in arrays:
        if len(directory) < 3 or not isinstance(directory[0], str):
            raise ValueError('Malformed directory data')
        path = directory[0].rsplit('*', 2)[0]
        if path != root and not path.startswith(root + '/'):
            raise ValueError('Directory outside source root')
        relative = path[len(root):].strip('/')
        for entry in directory[1:-2]:
            name, size, _mtime = entry.rsplit('*', 2)
            if '/' in name or '\\' in name or name in {'.', '..'}:
                raise ValueError('Unexpected filename')
            relpath = '/'.join(filter(None, (relative, name)))
            if '..' in relpath.split('/'):
                raise ValueError('Unexpected file path')
            files.append({
                'titulo': name, 'ruta': relpath,
                'url': urljoin(url, quote(relpath, safe='/')),
                'inventory_url': url, 'bytes': int(size),
            })
    if (not files or len(files) != int(count_match[1])
            or len(files) != int(stats_match[1]) or len(arrays) != int(stats_match[2])
            or len({f['url'] for f in files}) != len(files)):
        raise ValueError('Incomplete or duplicate file inventory; refusing truncation')
    return files


class VerinAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-verin/1.0 (public planning catalogue)'
        })
        response.raise_for_status()
        if (urlparse(response.url).scheme != 'https'
                or urlparse(response.url).hostname != urlparse(url).hostname):
            raise ValueError('Unexpected source redirect')
        # These reviewed pages declare UTF-8, despite incomplete HTTP charset headers.
        html = response.content.decode('utf-8-sig')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            dest = Path(capture_dir)
            dest.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (dest / name).write_bytes(response.content)
        return html

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = parse_inventory(self._fetch(SOURCE))
        extracted, excluded = [], []
        source_urls = [SOURCE]
        for row in rows:
            if urlparse(row['url']).path.rstrip('/') in LEGACY_PATHS:
                excluded.append({'titulo': row['titulo'], 'url': row['url'],
                                 'reason': 'Legacy frames/image-map viewer outside supported inventory format'})
                continue
            row['documentos'] = parse_documents(self._fetch(row['url']), row['url'])
            source_urls.append(row['url'])
            row['coverage'] = 'complete_file_inventory_for_instrument; partial_municipal_catalogue'
            extracted.append(row)
        if not extracted:
            raise ValueError('No usable municipal planning instruments')
        self._write(out_jsonl, extracted)
        return {'count': len(extracted), 'written': len(extracted),
                'catalogue_records': len(rows), 'excluded': excluded,
                'document_count': sum(len(r['documentos']) for r in extracted),
                'source_urls': source_urls, 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Refresh full inventory; state never suppresses records or pages.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
