"""Snapshot of the municipal new-PGM documentation, not a licence register."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.aytonavalmoral.es/tramites/plan-general-municipal/'
HOST = 'www.aytonavalmoral.es'
LIMITATIONS = [
    'Partial coverage: only the new PGM documentation page, not the historical planning register or public works inventory.',
    'Participation documentation does not establish initial or definitive approval, publication or agreement dates.',
    'Document labels and filenames can disagree about dates; neither is used as a plan approval/publication date.',
    'No verified geometry or coordinates; publication_ready is false. Licences are disabled.',
]


def parse_projects(html: str, source_url: str = SOURCE) -> list[dict[str, Any]]:
    """Group every PDF in DOCUMENTACIÓN under the single named instrument.

    Fail on missing content or pagination rather than produce an incomplete
    snapshot. Navigation, forms, news cards and unrelated documents are excluded.
    """
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.entry-content')
    if content is None:
        raise ValueError('Missing municipal PGM content')
    headings = [h.get_text(' ', strip=True) for h in content.select('h1')]
    text = content.get_text(' ', strip=True)
    if ('Nuevo Plan General Municipal' not in headings
            or 'Navalmoral de la Mata' not in text
            or 'El proceso de participación' not in text):
        raise ValueError('Missing named PGM and participation narrative')
    if (soup.select('a[rel~=next], .pagination, .wp-pagenavi, .nav-links, .page-links')
            or soup.select('link[rel~=next]')):
        raise ValueError('Paginated source: traversal must be implemented before extraction')
    sections = [d for d in content.select('.et_pb_text_inner')
                if any(p.get_text(' ', strip=True) == 'DOCUMENTACIÓN' for p in d.find_all('p'))]
    if len(sections) != 1:
        raise ValueError('Missing or ambiguous DOCUMENTACIÓN section')
    documents: dict[str, dict[str, str]] = {}
    for a in sections[0].select('a[href]'):
        target = urljoin(source_url, a['href'])
        parsed = urlparse(target)
        if not parsed.path.lower().endswith('.pdf'):
            # A new sub-inventory may require traversal; do not silently drop it.
            raise ValueError('Unexpected non-PDF documentation link')
        if (parsed.scheme not in ('https', 'http') or parsed.hostname != HOST
                or not parsed.path.startswith('/wp-content/uploads/')
                or 'pgm-navalmoral-de-la-mata' not in parsed.path.lower()):
            raise ValueError('Unexpected PGM document provenance')
        label = a.get_text(' ', strip=True)
        if not label:
            raise ValueError('Document without a source label')
        documents.setdefault(target, {'titulo': label, 'url': target, 'source_url': source_url})
    if not documents:
        raise ValueError('No PGM documents published in source')
    return [{
        'id': 'navalmoral-de-la-mata-pgm-' + hashlib.sha256(SOURCE.encode()).hexdigest()[:16],
        'municipio': 'Navalmoral de la Mata', 'provincia': 'Cáceres', 'codigo_ine': '10131',
        'titulo': 'Nuevo Plan General Municipal de Navalmoral de la Mata',
        'tipo': 'Plan General Municipal', 'fase': 'participación en la elaboración',
        'descripcion': 'Documentación municipal del nuevo PGM y su proceso de participación.',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': source_url, 'source': 'ayuntamiento', 'origen': 'documentacion_pgm_municipal',
        'documentos': list(documents.values()),
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
        'limitations': list(LIMITATIONS),
    }]


class NavalmoralDeLaMataAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=40, stream=True, headers={
            'User-Agent': 'municipio-navalmoral-pgm/1.0',
        }) as response:
            response.raise_for_status()
            if urlparse(response.url)._replace(fragment='') != urlparse(SOURCE):
                raise ValueError('Unexpected PGM source redirect')
            if 'text/html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Expected HTML source')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 3_000_000:
                    raise ValueError('PGM source exceeds response size bound')
            html = body.decode('utf-8')
        rows = parse_projects(html)
        # Optional local audit capture of the exact response used by this run.
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'pgm-live.html').write_bytes(body)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': [SOURCE], 'coverage': 'new_pgm_documentation_snapshot',
                'publication_ready': False, 'limitations': list(LIMITATIONS)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete refresh of this unpaginated instrument, not a date-based delta.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
