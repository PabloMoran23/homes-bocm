"""Catral planning instruments from the municipal-linked GVA directory inventory."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL_SOURCE = 'https://transparencia.catral.es/informacion-de-relevancia-juridica/urbanismo-y-medio-ambiente/'
INVENTORY = 'https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/2%20ALICANTE/03055%20CATRAL/'
INSTRUMENT = re.compile(r'^(03055-\d{4})\s+(.+)$')


def parse_directory(html: str, url: str) -> list[dict[str, str]]:
    """Parse all Apache index entries, preserving the server's encoded hrefs."""
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table#indexlist')
    heading = soup.select_one('h1#indextitle')
    if table is None or heading is None or '03055 CATRAL' not in heading.get_text():
        raise ValueError(f'Not a Catral directory inventory: {url}')
    # The current Apache index is unpaginated. Sorting links are harmless; any
    # pagination or unrecognised query must fail rather than yield a partial run.
    for a in soup.select('a[href]'):
        query = urlsplit(a['href']).query
        if query and not re.fullmatch(r'C=[NMSD];O=[AD]', query):
            raise ValueError(f'Unexpected pagination/query at {url}')
        if 'next' in a.get('rel', []) or 'pagination' in ' '.join(a.get('class', [])):
            raise ValueError(f'Unexpected pagination at {url}')
    entries = {}
    for a in table.select('td.indexcolname a[href]'):
        href = a['href']
        if href.startswith('?') or href == '../':
            continue
        target = urljoin(url, href)
        parts = urlsplit(target)
        # Immediate descendants only; never traverse parent, other municipalities
        # or off-site links, even if accidentally inserted in the index.
        relative = target[len(url):] if target.startswith(url) else ''
        if (not target.startswith(INVENTORY) or parts.query or parts.fragment
                or not relative or '/' in relative.rstrip('/')
                or any(p in ('.', '..') for p in unquote(parts.path).split('/'))):
            raise ValueError(f'Out-of-scope directory entry: {target}')
        if not (target.endswith('/') or parts.path.lower().endswith('.pdf')):
            raise ValueError(f'Unsupported inventory entry: {target}')
        entries[target] = {'titulo': a.get_text(' ', strip=True).rstrip('/'), 'url': target}
    if not entries:
        raise ValueError(f'Empty or changed directory: {url}')
    return list(entries.values())


def collect_projects(fetch) -> tuple[list[dict], list[str]]:
    """Walk the entire municipality tree, grouping PDFs by RAIP instrument ID."""
    queue = [(INVENTORY, None, None)]
    seen = set()
    instruments = {}
    while queue:
        url, instrument_id, section = queue.pop(0)
        if url in seen:
            continue
        if len(seen) >= 500:
            raise ValueError('Inventory exceeded safety bound; no partial output')
        seen.add(url)
        for entry in parse_directory(fetch(url), url):
            target, title = entry['url'], entry['titulo']
            if target.endswith('/'):
                match = INSTRUMENT.fullmatch(title)
                child_id = instrument_id
                child_section = title
                if match:
                    if instrument_id or match[1] in instruments:
                        raise ValueError('Duplicate or nested instrument identifier')
                    child_id = match[1]
                    child_section = None
                    instruments[child_id] = {
                        'id': f'catral-plan-{child_id}', 'registro_autonomico_id': child_id,
                        'municipio': 'Catral', 'codigo_ine': '03055', 'provincia': 'Alicante',
                        'titulo': title, 'tipo': 'instrumento de planeamiento urbanístico',
                        'url': target, 'inventory_url': INVENTORY,
                        'municipal_source_url': MUNICIPAL_SOURCE,
                        'source': 'ayuntamiento', 'origen': 'registro_autonomico_planeamiento_gva',
                        'document_publisher': 'Generalitat Valenciana', 'documentos': [],
                        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                        'lat': None, 'lon': None, 'geometry': None,
                        'geometry_status': 'unavailable', 'publication_ready': False,
                        'coverage': 'inventario documental; sin verificación de vigencia ni fechas',
                    }
                queue.append((target, child_id, child_section))
            else:
                if instrument_id is None:
                    raise ValueError(f'Document outside an identified instrument: {target}')
                instruments[instrument_id]['documentos'].append({
                    **entry, 'seccion': section, 'source_url': url,
                })
    if not instruments or any(not r['documentos'] for r in instruments.values()):
        raise ValueError('No complete instrument/document groups found')
    rows = sorted(instruments.values(), key=lambda r: r['id'])
    for row in rows:
        row['documentos'].sort(key=lambda d: d['url'])
    return rows, sorted(seen)


class CatralAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url: str) -> str:
        response = requests.get(url, timeout=45, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-catral/1.0'),
        })
        response.raise_for_status()
        # Requests normalises percent-escape case; decoded paths must still match.
        if (urlsplit(response.url).hostname != urlsplit(url).hostname
                or unquote(urlsplit(response.url).path) != unquote(urlsplit(url).path)):
            raise ValueError(f'Unexpected source redirect: {response.url}')
        # Legacy GVA directories mix UTF-8 and ISO-8859-1 filenames/HTML.
        # Keep encoded href bytes intact and decode labels without replacement.
        try:
            html = response.content.decode('utf-8')
        except UnicodeDecodeError:
            html = response.content.decode('iso-8859-1')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            folder = Path(capture_dir)
            folder.mkdir(parents=True, exist_ok=True)
            stem = hashlib.sha256(url.encode()).hexdigest()
            (folder / f'{stem}.html').write_bytes(response.content)
            (folder / f'{stem}.url.txt').write_text(url, encoding='utf-8')
        return html

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        municipal = BeautifulSoup(self._fetch(MUNICIPAL_SOURCE), 'html.parser')
        content = municipal.select_one('.entry-content')
        if content is None or not any(
            a.get('href') == INVENTORY for a in content.select('a[href]')
        ):
            raise ValueError('Municipal page no longer links the Catral GVA inventory')
        rows, pages = collect_projects(self._fetch)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': [MUNICIPAL_SOURCE, *pages],
                'coverage': 'complete traversal of linked Catral RAIP directory; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full current snapshot; no date watermark can safely cover this index.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory; forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
