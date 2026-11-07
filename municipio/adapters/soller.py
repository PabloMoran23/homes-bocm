"""Sóller municipal planning-document inventory (partial, complete folder snapshots)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://ajsoller.net'
SOURCE = BASE + '/es/arxius-i-documents/normativa-activitades-obras-y-urbanismo'
# Deliberately limited to the three named planning instruments. Ordinances,
# heritage declarations, guidance and the external pending-dossier portal differ.
FOLDERS = {
    '01-pla-general-1998': ('Pla General 1998', 'plan_general'),
    '02-pla-especial-proteccio-i-sanejament-de-lhorta-2011':
        ("Pla especial Protecció i sanejament de l'horta 2011", 'plan_especial'),
    '03-adaptacio-dot-2005': ('Adaptació DOT 2005', 'adaptacion_planeamiento'),
}
LIMITATIONS = [
    'Partial coverage: three municipal planning folders only; pending modifications in the linked electronic office are not extracted.',
    'Documents and amendments grouped by municipal instrument folder; not an exhaustive historical dossier register.',
    'File-list dates have unknown semantics and are retained only as document metadata; no approval, agreement or publication dates inferred.',
    'PDF and ZIP contents are linked, not parsed; no verified coordinates or geometry.',
    'No granted-licence register or physical works inventory extracted.',
]


def _page(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None or not main.select_one('h1'):
        raise ValueError('Missing municipal inventory content')
    # Current inventories are unpaginated. Refuse a future pager rather than
    # silently save a first page. Counts on the parent also guard completeness.
    if soup.select('a[rel~=next], .pager, nav[aria-label*="agin"], .pagination'):
        raise ValueError('Pagination detected; crawler needs review')
    return main


class SollerAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='soller', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html):
        main = _page(html)
        if 'Normativa' not in main.h1.get_text():
            raise ValueError('Unexpected municipal inventory')
        found = {}
        for a in main.select('a[href]'):
            url = urljoin(SOURCE, a['href'])
            key = urlparse(url).path.rstrip('/').rsplit('/', 1)[-1]
            if key not in FOLDERS:
                continue
            if urlparse(url).netloc != 'ajsoller.net':
                raise ValueError('Unexpected planning folder host')
            count = re.search(r'\b(\d+)\s+documents?\b', a.get_text(' ', strip=True))
            if not count or key in found:
                raise ValueError('Missing count or duplicate planning folder')
            found[key] = (url, int(count[1]))
        if set(found) != set(FOLDERS):
            raise ValueError('Planning inventory incomplete or changed')
        return found

    @staticmethod
    def parse_folder(html, key, url, expected_count):
        main = _page(html)
        title, kind = FOLDERS[key]
        heading = ' '.join(main.h1.get_text(' ', strip=True).split())
        if re.sub(r'^\d+\s+', '', heading) != title:
            raise ValueError('Unexpected planning folder title')
        docs = {}
        for a in main.select('a[href]'):
            link = urljoin(url, a['href'])
            if '/sites/cilma_soller/files/' not in urlparse(link).path:
                continue
            if urlparse(link).netloc != 'ajsoller.net' or urlparse(link).scheme != 'https':
                raise ValueError('Unexpected document origin')
            block = a.parent
            h = block.select_one('h3')
            if h is None or not h.get_text(strip=True):
                raise ValueError('Document title missing')
            text = block.get_text(' ', strip=True)
            dates = re.findall(r'\b\d{2}/\d{2}/\d{4}\b', text)
            listed = datetime.strptime(dates[0], '%d/%m/%Y').date().isoformat() if len(dates) == 1 else None
            docs[link] = {'titulo': h.get_text(' ', strip=True), 'url': link,
                          'source_url': url, 'fecha_listado_archivo': listed,
                          'fecha_listado_semantica': 'unknown; not an instrument approval or publication date'}
        if not docs or len(docs) != expected_count:
            raise ValueError(f'Incomplete folder {key}: {len(docs)} != {expected_count}')
        return {
            'id': 'soller-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'municipio': 'Sóller', 'codigo_ine': '07061', 'provincia': 'Illes Balears',
            'titulo': title, 'tipo': kind, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_planeamiento', 'url': url,
            'source_inventory_url': SOURCE, 'documentos': list(docs.values()),
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'fase': None, 'lat': None, 'lon': None,
            'geometry': None, 'publication_ready': False,
            'coverage': 'Municipal folder snapshot; amendments retained as documents of the parent instrument',
        }

    def _fetch(self, url):
        with requests.get(url, timeout=35, stream=True,
                          headers={'User-Agent': 'municipio-soller/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).netloc != 'ajsoller.net':
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Source response too large')
                chunks.append(chunk)
            payload = b''.join(chunks)
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(payload)
        return payload.decode('utf-8')

    def backfill_proyectos(self, out_jsonl):
        inventory = self.parse_inventory(self._fetch(SOURCE))
        rows = [self.parse_folder(self._fetch(url), key, url, count)
                for key, (url, count) in inventory.items()]
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        tmp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + [u for u, _ in inventory.values()],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh: no timestamp filter can establish complete folder changes.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
