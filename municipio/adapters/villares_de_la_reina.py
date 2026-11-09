"""Municipal works inventory; phases describe the undated source snapshot."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://villaresdelareina.es/proyecto/'
METADATA = 'https://villaresdelareina.es/wp-json/wp/v2/pages/3367'
PHASES = ('Fase de obras', 'Fase de contratación', 'Fase de licitación', 'Fase de redacción')
LIMITATIONS = [
    'Partial coverage: only the municipal Proyectos page, not a historical works register or planning archive.',
    'Source page last modified in 2021; phases are source assertions, not verified present-day execution status.',
    'No individual project publication/agreement/approval dates or verified geometry supplied.',
    'No verified granted-licence register; application forms and procurement notices excluded.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def parse_projects(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#main-content article .entry-content')
    if main is None or not main.find('h1', string=re.compile(r'^\s*Proyectos\s*$')):
        raise ValueError('Missing municipal project inventory')
    if 'los siguientes proyectos:' not in _text(main):
        raise ValueError('Missing works inventory narrative')
    # This inventory is a single page. Fail visibly if the source gains paging.
    if soup.select('a[rel~=next], link[rel~=next]') or main.select('.pagination, .page-links, .wp-pagenavi'):
        raise ValueError('Pagination detected; traversal must be implemented before extracting')
    rows = {}
    phases = set()
    for listing in main.find_all(['ul', 'ol']):
        items = listing.find_all('li', recursive=False)
        if not items:
            continue
        heading = listing.find_previous(['h1', 'h2', 'h3', 'h4'])
        phase = _text(heading) if heading else ''
        if phase not in PHASES:
            raise ValueError(f'Unrecognized project list phase: {phase}')
        phases.add(phase)
        for item in items:
            title = _text(item)
            if not title or item.find(['ul', 'ol']):
                raise ValueError('Empty or nested project entry')
            identity = unicodedata.normalize('NFKC', title).casefold()
            key = 'villares-de-la-reina-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16]
            links = []
            for anchor in item.select('a[href]'):
                target = urljoin(SOURCE, anchor['href'])
                if urlparse(target).scheme not in ('http', 'https'):
                    continue
                doc = {'titulo': _text(anchor), 'url': target}
                if doc not in links:
                    links.append(doc)
            if key in rows:
                if rows[key]['fase_fuente'] != phase:
                    raise ValueError('Conflicting phases for the same project')
                for doc in links:
                    if doc not in rows[key]['documentos']:
                        rows[key]['documentos'].append(doc)
                continue
            rows[key] = {
                'id': key, 'municipio': 'Villares de la Reina', 'codigo_ine': '37362',
                'provincia': 'Salamanca', 'titulo': title, 'descripcion': title,
                'tipo': 'obra pública', 'fase': phase.removeprefix('Fase de '),
                'fase_fuente': phase, 'fase_actual_verificada': False,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'url': SOURCE, 'source': 'ayuntamiento',
                'origen': 'inventario_municipal_obras', 'documentos': links,
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'geometry_status': 'unavailable',
            }
    if not rows or phases != set(PHASES):
        raise ValueError('Incomplete or changed municipal works inventory')
    return list(rows.values())


class VillaresDeLaReinaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://villaresdelareina.es')

    def _fetch(self, url):
        with requests.get(url, timeout=30, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-villares-de-la-reina/1.0')
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'villaresdelareina.es':
                raise ValueError('Unexpected municipal source redirect')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 2_000_000:
                    raise ValueError('Municipal source exceeds response size limit')
            return bytes(body)

    def backfill_proyectos(self, out_jsonl: Path):
        html = self._fetch(SOURCE)
        metadata_body = self._fetch(METADATA)
        metadata = json.loads(metadata_body)
        if metadata.get('id') != 3367 or metadata.get('link') != SOURCE or metadata.get('status') != 'publish':
            raise ValueError('Unexpected source-page metadata')
        rows = parse_projects(html.decode('utf-8'))
        for row in rows:
            # Page timestamps are provenance, never project event dates.
            row['source_page_publicada'] = metadata.get('date')
            row['source_page_modificada'] = metadata.get('modified')
            row['source_metadata_url'] = METADATA
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'projects-live.html').write_bytes(html)
            (capture / 'projects-metadata.json').write_bytes(metadata_body)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, METADATA],
                'coverage': 'complete single-page works inventory; partial municipal coverage',
                'publication_ready': False, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Refresh the entire source; no timestamp watermark or truncation.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': LIMITATIONS[-1]}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
