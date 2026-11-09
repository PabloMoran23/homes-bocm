"""Snapshot of the official planning document inventory, not a licence register."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.losmontesinos.es/el-ayuntamiento/areas/urbanismo/planeamiento-urbanistico-de-los-montesinos/'
LIMITATIONS = [
    'Partial coverage: only the municipal planning document inventory, not all municipal projects or works.',
    'Publication, agreement, approval dates and legal validity are not established by this inventory.',
    'Five inventory maps have no explicit instrument attribution; links retained separately, no synthetic map projects.',
    'No verified granted-licence register or project geometry; licences disabled.',
    'The PGOU website linked from Urbanismo failed DNS resolution during research; not covered.',
]


def _norm(text):
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


def parse_inventory(html: str, url: str = SOURCE) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find('h1')
    content = soup.select_one('.entry-content')
    if not heading or 'planeamiento urbanistico de los montesinos' not in _norm(heading.get_text(' ', strip=True)) or content is None:
        raise ValueError('Missing Los Montesinos planning inventory')
    groups, maps, pages = {}, {}, set()
    for a in content.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        label = a.get_text(' ', strip=True)
        name = _norm(unquote(parsed.path.rsplit('/', 1)[-1]))
        is_page = ('next' in a.get('rel', []) or 'page=' in parsed.query or '/page/' in parsed.path)
        if is_page:
            if parsed.hostname != urlparse(SOURCE).hostname or parsed.path != urlparse(SOURCE).path:
                raise ValueError('Unexpected inventory pagination URL')
            pages.add(target)
            continue
        if not parsed.path.lower().endswith(('.pdf', '.tif', '.tiff')):
            continue
        if parsed.scheme != 'https' or parsed.hostname != urlparse(SOURCE).hostname or not parsed.path.startswith('/wp-content/uploads/'):
            raise ValueError('Unexpected document provenance')
        doc = {'titulo': label, 'url': target, 'inventory_url': url}
        if re.fullmatch(r'plano-[1-5]_.*\.tif', name):
            maps.setdefault(target, doc)
            continue
        if re.fullmatch(r'normas-subsidiarias-parte-\d+\.pdf', name):
            key, title = 'nnss', 'Normas Subsidiarias de Los Montesinos'
        elif re.fullmatch(r'normas-urbanisticas-(loma-de-las-lagunas|res-1|res-2)\.pdf', name):
            key = name.removeprefix('normas-urbanisticas-').removesuffix('.pdf')
            title = label
        elif name == 'ordenanza-poligono-industrial-levante-ii.pdf':
            key, title = 'levante-ii', label
        else:
            # New documents need review instead of silently disappearing.
            raise ValueError(f'Unclassified inventory document: {target}')
        row = groups.setdefault(key, {
            'id': 'los-montesinos-plan-' + key,
            'municipio': 'Los Montesinos', 'provincia': 'Alicante', 'codigo_ine': '03903',
            'titulo': title, 'tipo': 'instrumento de planeamiento',
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'fase': None, 'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'geometry_status': 'unavailable',
            'documentos': [],
        })
        previous = next((d for d in row['documentos'] if d['url'] == target), None)
        if previous is None:
            row['documentos'].append(doc)
        elif len(label) > len(previous['titulo']):
            previous['titulo'] = label
    if not groups:
        raise ValueError('No named planning instruments found')
    for row in groups.values():
        row['url_documento'] = row['documentos'][0]['url']
    return {'records': list(groups.values()), 'unassigned_documents': list(maps.values()), 'pages': sorted(pages)}


class LosMontesinosAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.losmontesinos.es')

    def _fetch(self, url, document=False):
        with requests.get(url, timeout=45, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-los-montesinos/1.0')
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != urlparse(SOURCE).hostname:
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 20_000_000:
                    raise ValueError('Source exceeds response size limit')
                chunks.append(chunk)
            body = b''.join(chunks)
            if document and not body.startswith(b'%PDF-'):
                raise ValueError('Inventory PDF did not return a PDF')
            capture = self.config.get('capture_dir')
            if capture:
                path = Path(capture)
                path.mkdir(parents=True, exist_ok=True)
                name = hashlib.sha256(url.encode()).hexdigest()[:20] + ('.pdf' if document else '.html')
                (path / name).write_bytes(body)
            return body

    def backfill_proyectos(self, out_jsonl: Path):
        pending, visited, records, maps, document_urls = [SOURCE], set(), {}, {}, set()
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Inventory pagination safety limit reached; no partial output written')
            parsed = parse_inventory(self._fetch(url).decode('utf-8'), url)
            visited.add(url)
            pending.extend(u for u in parsed['pages'] if u not in visited)
            for row in parsed['records']:
                existing = records.setdefault(row['id'], row)
                known = {d['url'] for d in existing['documentos']}
                for doc in row['documentos']:
                    if doc['url'] not in known:
                        existing['documentos'].append(doc)
                        known.add(doc['url'])
            maps.update({d['url']: d for d in parsed['unassigned_documents']})
        for row in records.values():
            for doc in row['documentos']:
                if doc['url'] not in document_urls:
                    self._fetch(doc['url'], document=True)
                    document_urls.add(doc['url'])
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records.values()), encoding='utf-8')
        return {'status': 'ok', 'live_records': len(records), 'source_urls': sorted(visited | document_urls),
                'unassigned_documents': list(maps.values()), 'limitations': LIMITATIONS,
                'coverage': 'complete snapshot of selected planning inventory; partial municipal coverage'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
