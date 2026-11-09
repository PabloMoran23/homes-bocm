"""Ribadavia's municipal PXOM document inventory, corroborated by SIOTUGA."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://ribadavia.gal/pxom/'
STATUS_SOURCE = 'https://siotuga.xunta.gal/siotuga/urb'
LIMITATIONS = [
    'Only the municipal PXOM document inventory; not all municipal planning, works or amendments.',
    'Document links are retained as listed, not assumed downloadable or current individually.',
    'Publication and agreement dates are unavailable; approval date comes from SIOTUGA.',
    'No verified project geometry or coordinates; licences disabled.',
]


def canonical_url(base, href):
    parts = urlsplit(urljoin(base, href))
    return urlunsplit((parts.scheme, parts.netloc, quote(unquote(parts.path), safe='/'), parts.query, ''))


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    entry = soup.select_one('article .entry')
    heading = soup.select_one('h1.entry-title')
    if not entry or not heading or heading.get_text(strip=True).upper() != 'PXOM':
        raise ValueError('Expected municipal PXOM inventory absent')
    if soup.select('a[rel~=next], .page-links a, .pagination a, a.next'):
        raise ValueError('Pagination detected: extend traversal before accepting this inventory')
    documents = {}
    registry = {}
    title = None
    for anchor in entry.select('a[href]'):
        url = canonical_url(SOURCE, anchor['href'])
        parts = urlsplit(url)
        label = anchor.get_text(' ', strip=True)
        if parts.hostname in {'ribadavia.gal', 'www.ribadavia.gal'} and parts.path.startswith('/wp-content/uploads/') and parts.path.lower().endswith('.pdf'):
            documents.setdefault(url, {'titulo': label, 'url': url, 'source_url': SOURCE,
                                       'availability': 'listed_not_verified'})
        if parts.hostname == 'www.planeamentourbanistico.xunta.es' and 'RIBADAVIA_PXOM_' in parts.query:
            registry[url] = {'titulo': 'Paquete PXOM en SIOTUGA (enlace municipal)', 'url': url,
                             'source_url': SOURCE, 'availability': 'listed_not_verified'}
            if 'PLAN XERAL' in label.upper():
                title = label
    if not documents or len(registry) != 1 or not title:
        raise ValueError('PXOM inventory lacks document links or an unambiguous named plan')
    return title, list(documents.values()) + list(registry.values())


def parse_approval(html):
    soup = BeautifulSoup(html, 'html.parser')
    matches = []
    for row in soup.select('tr'):
        cells = row.find_all('td', recursive=False)
        if cells and cells[0].get_text(strip=True) == '32069':
            matches.append(cells)
    if len(matches) != 1:
        raise ValueError('SIOTUGA must identify exactly one INE 32069 municipality')
    cells = matches[0]
    if len(cells) < 5 or cells[1].get_text(strip=True) != 'Ribadavia' or cells[2].get_text(' ', strip=True).lower() != 'plan xeral de ordenación municipal':
        raise ValueError('SIOTUGA municipality or planning instrument changed')
    return date.fromisoformat(cells[3].get_text(strip=True)).isoformat()


class RibadaviaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, capture_name):
        response = requests.get(url, timeout=40, stream=True,
                                headers={'User-Agent': 'Mozilla/5.0'})
        with response:
            response.raise_for_status()
            if urlsplit(response.url).hostname != urlsplit(url).hostname:
                raise ValueError('Unexpected source redirect')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 3_000_000:
                    raise ValueError('Source exceeds reviewed HTML size')
        if self.config.get('capture_dir'):
            target = Path(self.config['capture_dir']) / capture_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        return body.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        title, documents = parse_inventory(self._fetch(SOURCE, 'pxom.html'))
        approval = parse_approval(self._fetch(STATUS_SOURCE, 'siotuga.html'))
        row = {
            'id': 'ribadavia-pxom', 'municipio': 'Ribadavia', 'codigo_ine': '32069',
            'provincia': 'Ourense', 'titulo': title + ' de Ribadavia',
            'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación definitiva',
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': approval,
            'fecha_aprob_source_url': STATUS_SOURCE,
            'url': SOURCE, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_pxom', 'documentos': documents,
            'source_urls': [SOURCE, STATUS_SOURCE],
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False, 'limitations': LIMITATIONS,
        }
        self._write(out_jsonl, [row])
        return {'status': 'ok', 'rows': 1, 'source_urls': row['source_urls'],
                'documents': len(documents), 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh of a single instrument, never an append of document records.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
