"""Museros: complete snapshot of the municipal NNSS document inventory."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://museros.org/inici/es/normas-subsidiarias-de-planeamiento-de-museros/'
LIMITATIONS = [
    'Partial municipal coverage: only the current NNSS document inventory; no historical register, other plans or public works feed.',
    'Document availability does not establish approval, legal validity or a granted licence.',
    'Publication and agreement dates are not stated in the inventory; upload paths and filenames are not event dates.',
    'PDF maps are retained as documents, without verified vector geometry or coordinates.',
]


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('article .entry-content')
    if content is None:
        raise ValueError('Museros inventory content missing')
    # This is a static document page. Fail explicitly if it becomes paginated;
    # never treat the first page of a changed inventory as a complete snapshot.
    if soup.select('a[rel~=next], link[rel~=next], .pagination, .page-links, .nav-links') or content.select('a.next, a.page-numbers, a[href*="/page/"], a[href*="paged="]'):
        raise ValueError('Museros inventory pagination detected; traversal needs review')

    groups = []
    current = None
    for node in content.find_all(['h3', 'h6', 'a']):
        text = node.get_text(' ', strip=True)
        if node.name == 'h3':
            current = {'heading': text, 'description': [], 'documents': []}
            groups.append(current)
        elif node.name == 'h6' and current is not None:
            current['description'].append(text)
        elif node.name == 'a':
            target = urljoin(source_url, node.get('href', ''))
            parsed = urlparse(target)
            if not parsed.path.lower().endswith('.pdf'):
                continue
            if current is None:
                raise ValueError('Ungrouped PDF in Museros inventory')
            if parsed.scheme != 'https' or parsed.hostname != 'museros.org' or not parsed.path.startswith('/wp-content/uploads/') or not text:
                raise ValueError('Unexpected Museros document link')
            doc = {'titulo': text, 'url': target, 'source_url': source_url}
            if doc not in current['documents']:
                current['documents'].append(doc)

    rows = []
    keys = set()
    for group in groups:
        heading, docs = group['heading'], group['documents']
        upper = heading.upper()
        if upper.startswith('MODIFICACIÓN PUNTUAL DE LAS NORMAS SUBSIDIARIAS'):
            numbers = {m for d in docs for m in re.findall(r'MODIFICACIÓN PUNTUAL\s+N[º°.]?\s*(\d+)', d['titulo'].upper())}
            if len(numbers) != 1 or not any('BORRADOR' in d['titulo'].upper() for d in docs):
                raise ValueError('Modification identifier or draft document missing/ambiguous')
            number = next(iter(numbers))
            key = 'nnss-modificacion-' + number
            title = heading + ' nº ' + number
            kind = 'modificación de normas subsidiarias'
        elif upper == 'TEXTO CONSOLIDADO DE PLANEAMIENTO URBANÍSTICO DE MUSEROS':
            if not any(d['titulo'].upper() == 'TEXTO CONSOLIDADO NORMAS URBANÍSTICAS' for d in docs):
                raise ValueError('Consolidated norms document missing')
            key, title, kind = 'nnss-texto-consolidado', heading, 'normas subsidiarias (texto consolidado)'
        else:
            raise ValueError('Unrecognised Museros inventory section: ' + heading)
        if not docs or key in keys:
            raise ValueError('Empty or duplicate Museros instrument')
        keys.add(key)
        rows.append({
            'id': 'museros-plan-' + key,
            'municipio': 'Museros', 'codigo_ine': '46177', 'provincia': 'Valencia',
            'titulo': title, 'tipo': kind, 'fase': None,
            'descripcion': ' '.join(group['description']) or None,
            'url': source_url, 'inventory_url': source_url,
            'documentos': docs, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'geometry_status': 'unavailable',
        })
    if not rows:
        raise ValueError('No Museros planning instruments found')
    return rows


class MuserosAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=(15, 60), stream=True, headers={
            'User-Agent': 'municipio-museros/1.0 (public planning inventory)',
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'museros.org' or urlparse(response.url).path != urlparse(SOURCE).path:
                raise ValueError('Unexpected Museros inventory redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 5_000_000:
                    raise ValueError('Museros inventory exceeds response size limit')
                chunks.append(chunk)
            raw = b''.join(chunks)
        rows = parse_inventory(raw.decode('utf-8'))
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory.html').write_bytes(raw)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': [SOURCE], 'coverage': 'complete_current_nnss_page',
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh: stable instrument IDs; no date-based incremental filtering.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'count': 0, 'reason': 'No verified public granted-licence register; application forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
