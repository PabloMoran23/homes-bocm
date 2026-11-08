"""Polinyà's municipal PGOU working-compilation inventory (partial coverage)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.polinya.cat/ajuntament/1644-informacio-oficial/normativa/normativa-durbanisme'
LIMITATIONS = [
    'Partial coverage: only the PGOU working compilation linked by the municipal inventory.',
    'Not an authoritative consolidated legal text; official instruments and amendments are in RPUC.',
    'No individual amendment inventory, public-works inventory or granted-licence register extracted.',
    'No verified approval/agreement/publication dates or project geometry; publication_ready=false.',
    'PDF links retained; PDF contents are not parsed.',
]


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('#readspeakerPage')
    content = article.select_one('.dinamic') if article else None
    heading = article.select_one('h1') if article else None
    if not content or not heading or heading.get_text(' ', strip=True) != "Normativa d'urbanisme":
        raise ValueError('Missing Polinyà planning inventory content')
    # This source is a single document page. Never silently ignore a new pager.
    main = soup.select_one('main') or article
    if main.select('[rel~=next], .pagination, .paginacio, .paginator'):
        raise ValueError('Unexpected pagination: inventory coverage must be reviewed')
    subtitle = content.select_one('.subtitle')
    text = content.get_text(' ', strip=True)
    if (not subtitle or subtitle.get_text(' ', strip=True) != "Pla General d'Ordenació Urbana"
            or 'Planejament Urbanístic de Polinyà' not in text
            or 'document de treball' not in text or 'text refós' not in text):
        raise ValueError('Missing PGOU identity or working-document provenance')
    documents = {}
    register_urls = set()
    for anchor in content.select('a[href]'):
        target = urljoin(source_url, anchor['href'])
        parsed = urlsplit(target)
        if parsed.hostname == 'dtes.gencat.cat' and parsed.path == '/rpucportal/':
            register_urls.add(target)
        if parsed.path.lower().endswith('.pdf'):
            if (parsed.scheme != 'https' or parsed.netloc != 'www.polinya.cat'
                    or not parsed.path.startswith('/media/repository/documents_oficials/normativa_urbanistica/')
                    or not parsed.path.rsplit('/', 1)[-1].upper().startswith('PGOU_POLINYA_')):
                raise ValueError('Unexpected planning document; review grouping before extraction')
            if target not in documents:
                documents[target] = {
                    'url': target, 'titulo': anchor.get_text(' ', strip=True),
                    'provenance': 'municipal working compilation of PGOU amendments',
                    'source_url': source_url,
                }
    if not documents or not register_urls:
        raise ValueError('Missing PGOU documents or official-register reference')
    return [{
        'id': 'polinya-pgou', 'municipio': 'Polinyà', 'codigo_ine': '08167',
        'provincia': 'Barcelona', 'titulo': "Pla General d'Ordenació Urbana de Polinyà",
        'tipo': 'PGOU', 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': source_url, 'inventory_url': source_url,
        'url_documento': next(iter(documents)), 'documentos': list(documents.values()),
        'registro_urls': sorted(register_urls),
        'descripcion': 'PGOU municipal; text refós de treball de les modificacions urbanístiques. La font remet al RPUC per a la informació oficial.',
        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
        'document_provenance': 'working compilation, not authoritative legal consolidation',
        'coverage': 'single_instrument_working_compilation',
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
        'limitations': LIMITATIONS,
    }]


class PolinyaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.polinya.cat')

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=30, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-polinya/1.0'),
        }) as response:
            response.raise_for_status()
            if response.url != SOURCE:
                raise ValueError('Unexpected inventory redirect')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Inventory did not return HTML')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 4_000_000:
                    raise ValueError('Inventory exceeds bounded response size')
            rows = parse_inventory(body.decode('utf-8'), response.url)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'single_instrument_working_compilation',
                'publication_ready': False, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete snapshot of the single instrument; no incremental date inference.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
