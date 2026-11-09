"""Public AUCAN current planning tree linked by Cabezón de la Sal's council."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL = 'https://www.cabezondelasal.net/informacion-municipal-2/plan-general-de-ordenacion-urbana/'
SOURCE = 'https://aplicacionesweb.cantabria.es/aucan/public/zona/saja/cabezondelasal'
API = 'https://aplicacionesweb.cantabria.es/aucan/public/planes?idMunicipio=12'
DOWNLOAD = 'https://aplicacionesweb.cantabria.es/aucan/public/documento/download.do/'
LIMITATIONS = [
    'Snapshot of AUCAN Actual only; No Vigente is deliberately excluded.',
    'Partial municipal coverage: no comprehensive works or granted-licence register.',
    'Actual is the archive classification, not an independent legal validity determination.',
    'Dates come only from the instrument heading; document-specific dates are retained in labels.',
    'No PDF geometry extraction, coordinates, geocoding or publication readiness.',
]
INSTRUMENT = re.compile(r'^(?:Plan General\b|Plan Parcial\b|Plan Especial\b|Modificación Puntual\s*-|Estudio de Detalle\b)', re.I)


def _children(node):
    children = node.get('nodes')
    if children is None:
        return []
    if not isinstance(children, list):
        raise ValueError('Unexpected AUCAN children/pagination schema')
    return children


def _identity(title):
    # Date corrections and new attached documents must not change plan identity.
    name = re.sub(r'\s*\((?:CROTU|CRU|Ayto\.).*$', '', title).strip()
    return 'cabezon-de-la-sal-plan-' + hashlib.sha256(name.encode()).hexdigest()[:16]


def _heading_date(title, label):
    match = re.search(label + r'\s+(\d{2}/\d{2}/\d{4})', title)
    return datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None


def parse_inventory(payload):
    """Traverse every node of Actual, preserving document paths and plan nesting."""
    if not isinstance(payload, list) or not all(isinstance(n, dict) for n in payload):
        raise ValueError('Expected complete AUCAN tree array, not a paginated envelope')
    roots = [n for n in payload if n.get('text') == 'Actual']
    if len(roots) != 1 or any(n.get('text') not in {'Actual', 'No Vigente'} for n in payload):
        raise ValueError('AUCAN inventory branches changed')
    rows = {}

    def visit(node, path, owner=None):
        if not isinstance(node, dict) or not isinstance(node.get('text'), str):
            raise ValueError('Malformed AUCAN node')
        title = node['text'].strip()
        children = _children(node)
        current = owner
        if INSTRUMENT.match(title):
            key = _identity(title)
            if key in rows:
                raise ValueError('Ambiguous duplicate instrument identity')
            current = {
                'id': key, 'municipio': 'Cabezón de la Sal', 'codigo_ine': '39012',
                'provincia': 'Cantabria', 'titulo': title,
                'tipo': 'modificacion_planeamiento' if title.startswith('Modificación') else 'planeamiento_urbanistico',
                'url': SOURCE, 'inventory_url': API, 'municipal_source_url': MUNICIPAL,
                'source': 'gobierno_de_cantabria', 'origen': 'aucan_planeamiento_actual',
                'source_path': path + [title], 'estado_fuente': 'Actual',
                'fase': None, 'fecha': None,
                'fecha_acuerdo': _heading_date(title, r'(?:CROTU|CRU|Ayto\.)'),
                'fecha_publicacion': _heading_date(title, 'BOC'),
                'documentos': [], 'parent_id': owner['id'] if owner else None,
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            }
            rows[key] = current
        if node.get('id') is not None:
            if current is None or type(node['id']) is not int or node['id'] <= 0 or children:
                raise ValueError('Unassigned or malformed AUCAN document')
            current['documentos'].append({
                'id_origen': node['id'], 'titulo': title,
                'url': DOWNLOAD + str(node['id']), 'source_path': path + [title],
            })
        if title == 'Aprobación definitiva' and current is not None:
            current['fase'] = 'aprobación definitiva'
        for child in children:
            visit(child, path + [title], current)

    visit(roots[0], [])
    if not rows or any(not row['documentos'] for row in rows.values()):
        raise ValueError('No complete current instruments found')
    for row in rows.values():
        docs = {d['id_origen']: d for d in row['documentos']}
        row['documentos'] = list(docs.values())
    return list(rows.values())


class CabezonDeLaSalAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, capture):
        response = requests.get(url, timeout=45, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-cabezon-de-la-sal/1.0'),
        })
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(url).hostname:
            raise ValueError('Unexpected source redirect')
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture).write_bytes(response.content)
        return response

    def backfill_proyectos(self, out_jsonl):
        municipal = BeautifulSoup(self._fetch(MUNICIPAL, 'municipal-pgou.html').content, 'html.parser')
        content = municipal.select_one('.entry-content')
        if content is None or not content.select_one(f'a[href="{SOURCE}"]'):
            raise ValueError('Council no longer links the reviewed planning archive')
        page = self._fetch(SOURCE, 'aucan.html').text
        soup = BeautifulSoup(page, 'html.parser')
        heading = soup.select_one('h1')
        if heading is None or heading.get_text(strip=True) != 'Cabezón de la Sal' or not re.search(r"idMunicipio:\s*'12'", page):
            raise ValueError('AUCAN municipality identity changed')
        rows = parse_inventory(self._fetch(API, 'planes.json').json())
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(output)
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'source_urls': [MUNICIPAL, SOURCE, API], 'limitations': LIMITATIONS,
                'coverage': 'complete_actual_branch_of_aucan_snapshot', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Refresh the complete snapshot; do not advance a date cursor or discard documents.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
