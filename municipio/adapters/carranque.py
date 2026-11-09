"""Carranque's municipal NNSS document inventory, grouped as one instrument."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.carranque.es/portal/urbanismo/'
HOST = 'www.carranque.es'
LIMITATIONS = [
    'Partial coverage: municipal NNSS inventory and associated cartography only; no full works or planning history.',
    'Inventory presence does not establish approval, effective date or consolidated legal validity.',
    'CMS creation/update dates are not agreement or legal publication dates; dates remain unknown.',
    'No verified project geometry or public register of granted licences.',
    'PDF contents are not parsed; stable municipal document landing links are retained.',
]


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    sections = {}
    for block in soup.select('.w3eden'):
        heading = block.find('h3')
        if heading and heading.get_text(' ', strip=True) in ('Normas Subsidiarias', 'Planos'):
            name = heading.get_text(' ', strip=True)
            if name in sections:
                raise ValueError('Duplicate inventory section')
            sections[name] = block
    if set(sections) != {'Normas Subsidiarias', 'Planos'}:
        raise ValueError('Missing Carranque planning inventory sections')
    documents = {}
    for section, block in sections.items():
        # The observed inventory is unpaginated. Fail explicitly if the portal
        # introduces pagination rather than publishing a silently partial plan.
        if block.select('.pagination a, .pagination li, a[rel~=next], [data-next-page]'):
            raise ValueError('Inventory pagination detected; traversal requires review')
        for anchor in block.select('.link-template-widget .media-body a[href]'):
            title = anchor.get_text(' ', strip=True)
            if not title:
                continue
            target = urljoin(SOURCE, anchor['href'])
            parsed = urlparse(target)
            if (parsed.scheme != 'https' or parsed.netloc != HOST
                    or not parsed.path.startswith('/portal/download/')
                    or parsed.query or parsed.fragment):
                raise ValueError('Unexpected document provenance')
            if section == 'Normas Subsidiarias':
                included = bool(re.match(r'^(NNSS\s*[–-]|Ordenanza\s+[1-4]ª\b|Suelo No Urbanizable$)', title))
            else:
                included = bool(re.match(r'^(P\d+\s*[–-]\s*Clasificación y Calificación de Suelo$|Cuadrícula de Distribución de Planos$)', title))
            if included:
                documents[target] = {'titulo': title, 'url': target,
                                     'seccion': section, 'source_url': SOURCE}
    docs = list(documents.values())
    if not any(re.fullmatch(r'NNSS\s*[–-]\s*Completo', d['titulo']) for d in docs):
        raise ValueError('Missing complete NNSS package; refusing synthetic plan')
    if not any(d['seccion'] == 'Planos' for d in docs):
        raise ValueError('Missing planning cartography')
    return [{
        'id': 'carranque-nnss', 'municipio': 'Carranque', 'provincia': 'Toledo',
        'codigo_ine': '45038', 'titulo': 'Normas Subsidiarias de Carranque',
        'tipo': 'Normas Subsidiarias', 'url': SOURCE, 'inventory_url': SOURCE,
        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
        'documentos': docs,
        'descripcion': 'Instrumento publicado por el Ayuntamiento, agrupando capítulos, anexos y cartografía del inventario municipal.',
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'partial_current_document_inventory', 'limitations': LIMITATIONS,
    }]


class CarranqueAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'municipio-carranque/1.0 (public planning inventory)'})
        response.raise_for_status()
        if response.url != SOURCE or 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Unexpected inventory response')
        rows = parse_inventory(response.text)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_text(response.text, encoding='utf-8')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE],
                'documents': len(rows[0]['documentos']), 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete refresh of the scoped inventory; no date-based filtering.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
