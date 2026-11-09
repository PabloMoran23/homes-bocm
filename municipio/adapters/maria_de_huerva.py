"""Municipal PGOU document inventory; one instrument, no inferred legal status."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://mariadehuerva.org/ayuntamiento/urbanismo/pgou/'
HOST = 'mariadehuerva.org'
LIMITATIONS = [
    'Partial coverage: only the municipal PGOU document inventory, not all planning amendments or public works.',
    'No granted licence register extracted; forms and procurement announcements are excluded.',
    'No verified approval/agreement/publication dates, legal validity or project geometry; upload paths are not dates of approval.',
    'Linked PDFs are retained as document provenance, not parsed as separate projects.',
]


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    if urlparse(url).hostname != HOST or urlparse(url).path != urlparse(SOURCE).path:
        raise ValueError('Unexpected municipal PGOU source URL')
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#wpb-content-root')
    if content is None or soup.h1 is None or soup.h1.get_text(strip=True) != 'PGOU':
        raise ValueError('PGOU content missing or changed')
    # This is a complete single-page document inventory. Fail if it starts
    # advertising pagination, rather than returning a silently partial snapshot.
    if content.select('[rel~=next], .pagination, .page-numbers, .nav-links'):
        raise ValueError('Unexpected pagination in PGOU inventory')
    section = None
    documents = {}
    for element in content.find_all(['h2', 'a']):
        label = element.get_text(' ', strip=True)
        if element.name == 'h2':
            section = label if label in ('Plan General de Ordenación Urbana', 'Catálogo de Protección') else None
            continue
        href = urljoin(url, element.get('href', ''))
        if not section or not urlparse(href).path.lower().endswith('.pdf'):
            continue
        if urlparse(href).hostname != HOST or not urlparse(href).path.startswith('/wp-content/uploads/'):
            raise ValueError('Unexpected PGOU document provenance')
        if not label:
            raise ValueError('Unlabelled PGOU document')
        documents.setdefault(href, {'titulo': label, 'url': href, 'seccion': section, 'source_url': url})
    labels = {doc['titulo'] for doc in documents.values()}
    if not {'Fichas de Ordenación', 'Normas Urbanísticas'} <= labels:
        raise ValueError('PGOU core planning documents missing')
    if not any(doc['seccion'] == 'Catálogo de Protección' for doc in documents.values()):
        raise ValueError('PGOU protection catalogue missing')
    return [{
        'id': 'maria-de-huerva-pgou',
        'municipio': 'María de Huerva', 'codigo_ine': '50163', 'provincia': 'Zaragoza',
        'titulo': 'Plan General de Ordenación Urbana de María de Huerva (PGOU)',
        'tipo': 'PGOU', 'url': url, 'inventory_url': url,
        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
        'documentos': list(documents.values()),
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'municipal_pgou_document_inventory', 'limitations': LIMITATIONS.copy(),
    }]


class MariaDeHuervaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'municipio-maria-de-huerva/1.0 (public planning inventory)',
        })
        response.raise_for_status()
        rows = parse_inventory(response.text, response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'pgou.html').write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE],
                'documents': len(rows[0]['documentos']), 'limitations': LIMITATIONS.copy(),
                'coverage': 'complete_single_page_pgou_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh: this inventory has no dated incremental feed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
