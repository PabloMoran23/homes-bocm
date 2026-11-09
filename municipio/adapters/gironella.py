"""Gironella's published municipal planning-document inventory (partial coverage)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://gironella.cat/ajuntament/normativa-municipal/'
LIMITATIONS = [
    'Only planning instruments listed in the municipal normative inventory; not all RPUC history or public works.',
    'Listing does not establish current legal validity, approval stage, agreement or publication dates.',
    'Documents are linked with provenance; their PDF text and the RPUC application are not parsed.',
    'No verified project geometry or coordinates; publication_ready is false.',
    'No granted-licence register extracted; forms, taxes, subsidies and procurement excluded.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split()) if node else ''


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    inventory = soup.select_one('.facetwp-template[data-name="llista_normativa"]')
    if inventory is None:
        raise ValueError('Municipal normative inventory missing')
    # FacetWP renders every row server-side today. Fail explicitly if this ever
    # becomes paginated/filtered, rather than quietly returning the first page.
    scripts = '\n'.join(s.get_text() for s in soup.find_all('script'))
    match = re.search(r'window\.FWP_JSON\s*=\s*', scripts)
    if not match:
        raise ValueError('Missing inventory completeness metadata')
    metadata, _ = json.JSONDecoder().raw_decode(scripts[match.end():])
    pager = metadata['preload_data']['settings']['pager']
    cards = inventory.select('div.ordenanca')
    if (pager['page'] != 1 or pager['total_pages'] != 1
            or pager['total_rows'] != pager['total_rows_unfiltered']
            or len(cards) != pager['total_rows']):
        raise ValueError('Inventory paginated, filtered or incomplete; full traversal required')
    rows = {}
    for card in cards:
        title = _text(card.select_one('.titol-ordenanca'))
        category = _text(card.select_one('.tipologia'))
        if category != "Ordenances d'urbanisme":
            continue
        if title.startswith('Modificació puntual del Pla general'):
            kind = 'modificación puntual del plan general'
        elif title.startswith('Pla de millora urbana '):
            kind = 'plan de mejora urbana'
        elif title.startswith('Pla especial urbanístic '):
            kind = 'plan especial urbanístico'
        elif title == 'Revisió pla general ordenació urbana municipal':
            kind = 'revisión del plan general'
        else:
            continue
        docs = {}
        for link in card.select('a[href]'):
            href = link['href'].strip()
            if not href:
                continue
            url = urljoin(SOURCE, href)
            parsed = urlparse(url)
            municipal_pdf = (parsed.hostname in ('gironella.cat', 'www.gironella.cat')
                             and parsed.path.startswith('/wp-content/uploads/')
                             and parsed.path.lower().endswith('.pdf'))
            rpuc = (parsed.hostname == 'dtes.gencat.cat'
                    and parsed.path.startswith('/rpucportal/'))
            if parsed.scheme != 'https' or not (municipal_pdf or rpuc):
                raise ValueError(f'Unexpected planning document URL: {url}')
            doc = docs.setdefault(url, {'url': url, 'labels': [], 'source_url': SOURCE,
                                        'publisher': 'Ajuntament de Gironella' if municipal_pdf else 'Generalitat de Catalunya (RPUC)'})
            label = _text(link)
            if label and label not in doc['labels']:
                doc['labels'].append(label)
        if not docs:
            raise ValueError(f'Planning instrument without documents: {title}')
        # Identity is the named instrument, not individual PDFs or link labels.
        key = 'gironella-plan-' + hashlib.sha256(title.casefold().encode()).hexdigest()[:16]
        if key in rows:
            raise ValueError(f'Duplicate instrument card: {title}')
        rows[key] = {
            'id': key, 'municipio': 'Gironella', 'codigo_ine': '08092', 'provincia': 'Barcelona',
            'titulo': title, 'tipo': kind, 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'url_documento': next(iter(docs)), 'documentos': list(docs.values()),
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
            'source_category': category, 'inventory_url': SOURCE,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'unavailable', 'coverage': 'partial_municipal_document_inventory',
        }
    if not rows:
        raise ValueError('No named planning instruments found')
    return list(rows.values())


class GironellaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='gironella', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://gironella.cat')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-gironella/1.0')
        }) as response:
            response.raise_for_status()
            if response.url.rstrip('/') != SOURCE.rstrip('/'):
                raise ValueError(f'Unexpected inventory redirect: {response.url}')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Inventory exceeds response size bound')
            html = data.decode('utf-8-sig')
        rows = parse_inventory(html)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'normativa.html').write_bytes(data)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete refresh of the published inventory, not a date-based delta.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': LIMITATIONS[-1]}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
