"""Calamocha's municipal PGOU document inventories (partial planning coverage)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://calamocha.es'
SOURCES = {
    'documentos': BASE + '/p-g-o-u-documentos/',
    'modificaciones': BASE + '/p-g-o-u-modificaciones/',
}
LIMITATIONS = [
    'Partial coverage: municipal PGOU document inventories only; not a complete planning history or public works register.',
    'The listed modifications are 1, 2, 3, 5, 6, 8 and 9 at verification; later instruments are outside these inventories.',
    'Publication, agreement and approval dates and legal phase are not stated in these inventories; upload paths are not dates of approval.',
    'PDF links are retained as documentary provenance; no verified vector geometry or coordinates.',
    'No granted licence register extracted; licences disabled.',
]


def parse_inventory(html: str, kind: str) -> list[dict]:
    """Group base-plan documents and numbered modifications, never PDF-per-project."""
    if kind not in SOURCES:
        raise ValueError('Unknown inventory')
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content')
    expected = 'P.G.O.U. ' + ('Documentos' if kind == 'documentos' else 'Modificaciones')
    if content is None or not any(h.get_text(' ', strip=True) == expected for h in content.select('h1,h2')):
        raise ValueError('Missing municipal PGOU inventory heading/content')
    # These are single-page document lists. Refuse changed pagination rather
    # than silently dropping a second page (including numbered WP navigation).
    if soup.select('[rel~=next], .pagination, .page-numbers, .page-links, .nav-links'):
        raise ValueError('Pagination detected; inventory traversal requires review')
    for a in content.select('a[href]'):
        if a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'más', 'ver más', 'cargar más'}:
            raise ValueError('Continuation detected; inventory traversal requires review')
    records = {}
    for a in content.select('li a[href]'):
        target = urljoin(SOURCES[kind], a['href'])
        title = a.get_text(' ', strip=True)
        if not urlparse(target).path.lower().endswith('.pdf'):
            continue
        if urlparse(target).netloc != 'calamocha.es' or not urlparse(target).path.startswith('/wp-content/uploads/'):
            raise ValueError('Unexpected document provenance')
        if not title:
            raise ValueError('Untitled planning document')
        number = None
        if kind == 'modificaciones':
            match = re.match(r'^Modificación puntual n[º°o]\s*(\d+)\b', title, re.I)
            if not match:
                raise ValueError('Unrecognized modification document: ' + title)
            number = str(int(match[1]))
        key = 'pgou' if number is None else 'pgou-modificacion-' + number
        row = records.setdefault(key, {
            'id': 'calamocha-' + key, 'municipio': 'Calamocha',
            'codigo_ine': '44050', 'provincia': 'Teruel',
            'titulo': 'Plan General de Ordenación Urbana de Calamocha' if number is None else
                      'Modificación puntual nº ' + number + ' del PGOU de Calamocha',
            'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCES[kind], 'source': 'ayuntamiento',
            'origen': 'inventario_documental_pgou', 'documentos': [],
            'coverage': 'partial_municipal_document_inventory',
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
        if not any(d['url'] == target for d in row['documentos']):
            row['documentos'].append({'titulo': title, 'url': target, 'source_url': SOURCES[kind]})
    if not records:
        raise ValueError('Empty PGOU inventory; review source before replacing snapshot')
    return list(records.values())


class CalamochaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, kind):
        url = SOURCES[kind]
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipal-inventory-calamocha/1.0'})
        # The canonical paths intermittently return an edge-cache 403 while the
        # same public page with a harmless query parameter serves HTTP 200.
        if response.status_code == 403:
            response = requests.get(url, params={'capture': '1'}, timeout=40,
                                    headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        if urlparse(response.url).netloc != 'calamocha.es' or urlparse(response.url).path != urlparse(url).path:
            raise ValueError('Unexpected inventory redirect')
        if self.config.get('capture_dir'):
            dest = Path(self.config['capture_dir'])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / (kind + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = []
        for kind in SOURCES:
            rows.extend(parse_inventory(self._fetch(kind), kind))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES.values()),
                'document_count': sum(len(r['documentos']) for r in rows), 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of the scoped inventories; no invented incremental date.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
