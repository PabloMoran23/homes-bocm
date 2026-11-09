"""Brión's municipal PXOM document inventory (one instrument, many documents)."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE_URL = 'https://www.concellodebrion.gal/es/urbanismo'
HOST = urlparse(SOURCE_URL).hostname


def parse_inventory(html: str, source_url: str = SOURCE_URL) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    if urlparse(source_url).hostname != HOST:
        raise ValueError('Unexpected municipal inventory host')
    # This is a single departmental document inventory, not a news listing.
    if soup.select('a[rel~="next"], .pager a[href], .pagination a[href]'):
        raise ValueError('Pagination detected; review traversal before accepting coverage')
    headings = [h for h in soup.find_all('h3') if h.get_text(' ', strip=True) == 'PXOM']
    if len(headings) != 1:
        raise ValueError('Expected exactly one PXOM section')
    section = headings[0].parent
    description = section.find('p')
    description = description.get_text(' ', strip=True) if description else ''
    if 'Plan Xeral Urbanístico de Brión' not in description:
        raise ValueError('PXOM municipality/description changed')
    docs = {}
    for anchor in section.select('a[href]'):
        url = urldefrag(urljoin(source_url, anchor['href']))[0]
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or parsed.hostname != HOST
                or not parsed.path.startswith('/sites/default/files/pxom/')
                or not parsed.path.lower().endswith('.pdf')):
            raise ValueError(f'Unreviewed PXOM link: {url}')
        title = anchor.get_text(' ', strip=True)
        if not title:
            raise ValueError('Untitled PXOM document')
        item = anchor.find_parent('li')
        docs.setdefault(url, {
            'titulo': title, 'url': url, 'source_url': source_url,
            'descripcion': item.get_text(' ', strip=True) if item else title,
        })
    if not docs or not any(d['titulo'] == 'Normativa urbanística' for d in docs.values()):
        raise ValueError('PXOM documents or normative anchor missing')
    return [{
        'id': 'brion-pxom', 'municipio': 'Brión', 'codigo_ine': '15013',
        'provincia': 'A Coruña', 'titulo': 'Plan Xeral Urbanístico de Brión (PXOM)',
        'tipo': 'planeamiento_urbanistico', 'descripcion': description,
        'url': source_url, 'inventory_url': source_url,
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_pxom',
        'documentos': list(docs.values()),
        'coverage': 'municipal_pxom_document_inventory_only',
        'geometry_status': 'unavailable', 'publication_ready': False,
    }]


def _write(path: Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    temporary.replace(path)


class BrionAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE_URL, timeout=45, headers={
            'User-Agent': 'municipio-brion/1.0 (public planning inventory)',
        })
        response.raise_for_status()
        if urlparse(response.url).path.rstrip('/') != urlparse(SOURCE_URL).path:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_text(response.text, encoding='utf-8')
        _write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'documents': len(rows[0]['documentos']),
                'source_urls': [response.url], 'coverage': rows[0]['coverage']}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full snapshot; no publication timestamp or incremental cursor is exposed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        _write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
