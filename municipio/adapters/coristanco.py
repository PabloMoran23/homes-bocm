"""Current municipal PXOM document inventory; one instrument, six volumes."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import Any

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://coristanco.gal/urbanismo/'
LABELS = {'INDICE XERAL', 'TOMO I', 'TOMO II', 'TOMO III', 'TOMO IV', 'TOMO V'}


def parse_projects(html: str, source_url: str = SOURCE) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, 'html.parser')
    headings = [h for h in soup.select('h2') if h.get_text(' ', strip=True) == 'PXOM']
    if len(headings) != 1:
        raise ValueError('Expected one municipal PXOM heading')
    section = next((p for p in headings[0].parents if p.select('[data-pdf-url]')), None)
    if section is None:
        raise ValueError('PXOM document inventory missing')
    if soup.select('a[rel~=next], a.page-numbers, .pagination, .nav-links'):
        raise ValueError('Pagination detected: single-page PXOM contract must be reviewed')
    documents = {}
    for node in section.select('[data-pdf-url]'):
        label = ' '.join(node.get_text(' ', strip=True).split()).upper()
        target = urljoin(source_url, node['data-pdf-url'])
        parsed = urlparse(target)
        if (label not in LABELS or parsed.scheme != 'https'
                or parsed.netloc != 'coristanco.gal'
                or not parsed.path.startswith('/wp-content/uploads/')
                or not parsed.path.lower().endswith('.pdf') or parsed.query or parsed.fragment):
            raise ValueError('Unexpected PXOM document label or URL')
        if label in documents and documents[label] != target:
            raise ValueError('Conflicting documents for PXOM volume')
        documents[label] = target
    if set(documents) != LABELS or len(set(documents.values())) != len(LABELS):
        raise ValueError('Incomplete or ambiguous PXOM document inventory')
    return [{
        'id': 'coristanco-pxom', 'municipio': 'Coristanco', 'codigo_ine': '15029',
        'provincia': 'A Coruña', 'titulo': 'Plan xeral de ordenación municipal de Coristanco (PXOM)',
        'tipo': 'PXOM', 'fase': None, 'fecha': None,
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': source_url, 'inventory_url': source_url,
        'url_documento': documents['INDICE XERAL'],
        'documentos': [{'titulo': label, 'url': url, 'source_url': source_url}
                       for label, url in documents.items()],
        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
        'descripcion': 'PXOM publicado en Urbanismo e Obras: índice xeral e cinco tomos.',
        'coverage': 'Single current municipal PXOM page; not a complete planning or works register',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified instrument geometry extracted',
    }]


class CoristancoAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=30, stream=True, headers={
            'User-Agent': 'municipio-coristanco/1.0'
        }) as response:
            response.raise_for_status()
            if response.url != SOURCE:
                raise ValueError('Unexpected municipal inventory redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Municipal inventory exceeds response size limit')
                chunks.append(chunk)
            html = b''.join(chunks).decode('utf-8')
        rows = parse_projects(html)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo-live.html').write_text(html, encoding='utf-8')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'current_pxom_document_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Refresh the entire unpaginated inventory; no date-based filtering.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
