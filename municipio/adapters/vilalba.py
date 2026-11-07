"""Vilalba's base planning instrument from the municipal-linked Xunta inventory.

Deliberately partial: the base NSP only, not its amendments/development plans.
The public form token is acquired anonymously for each snapshot.
"""
from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
INDEX = BASE + 'urb'
INVENTORY = BASE + 'inventario?inv=1&idconcello=27065'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
LIMITATIONS = [
    'Only the base Normas Subsidiarias de Planeamento; amendments, development '
    'plans, rural delimitations, territorial plans and public works are outside this snapshot.',
    'Current availability in SIOTUGA does not establish consolidated legal validity.',
    'Dates are inventory metadata, not independently transcribed from each PDF.',
    'No granted-licence register or verified project geometry; publication_ready=false.',
]


def _date(value):
    if not value:
        return None
    return date.fromisoformat(value).isoformat()


def select_base_plan(payload: Any) -> dict:
    # The browser endpoint returns its entire class as a JSON array. Refuse
    # wrappers/pagination metadata instead of silently accepting only one page.
    if not isinstance(payload, list) or not all(isinstance(x, dict) for x in payload):
        raise ValueError('Expected complete SIOTUGA class array')
    candidates = [x for x in payload if x.get('figura') == 'Normas Subsidiarias de Planeamento'
                  and x.get('docnome') == 'NORMAS SUBSIDIARIAS DE PLANEAMENTO DE VILALBA']
    if len(candidates) != 1 or not str(candidates[0].get('id', '')).isdigit():
        raise ValueError('Missing or ambiguous Vilalba base NSP')
    return candidates[0]


def parse_plan(item: dict, detail: dict) -> dict:
    general = detail['datos_xerais']
    if (str(general['id']) != str(item['id']) or general['menutitle'] != 'Vilalba'
            or general['denominacion'] != item['docnome']
            or general['figura'] != item['figura']):
        raise ValueError('Detail does not match Vilalba inventory instrument')
    for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
        if general.get(field) != item.get(field):
            raise ValueError('Conflicting inventory and detail dates')
    root = urljoin(BASE, general['filesroot'] + general['folder'] + '/documents/')
    if urlparse(root).hostname != 'siotuga.xunta.gal' or '/VILALBA/documents/' not in root:
        raise ValueError('Unexpected document provenance')
    documents = {}
    for section in detail['elementos']:
        for component in section['componentes']:
            url = urljoin(root, component['pathesperado'])
            if not url.startswith(root) or not component.get('descripcion'):
                raise ValueError('Invalid component link')
            documents[url] = {'url': url, 'titulo': component['descripcion'],
                              'seccion': section['description'],
                              'source_component_id': str(component['id'])}
    if not documents:
        raise ValueError('NSP has no linked documents')
    return {
        'id': 'vilalba-siotuga-' + str(item['id']),
        'municipio': 'Vilalba', 'provincia': 'Lugo', 'codigo_ine': '27065',
        'titulo': item['docnome'], 'tipo': item['figura'],
        'fase': 'aprobación definitiva' if item.get('fechaaddef') else None,
        'fecha': None, 'fecha_acuerdo': None,
        'fecha_aprob': _date(item.get('fechaaddef')),
        # Multiple publication channels retain their individual source fields.
        'fecha_publicacion': None,
        'fecha_publicacion_bop': _date(item.get('fechabop')),
        'fecha_publicacion_dog': _date(item.get('fechadog')),
        'fecha_publicacion_normativa_bop': _date(item.get('fechanormativabop')),
        'source': 'ayuntamiento', 'organismo_fuente': 'Xunta de Galicia — SIOTUGA',
        'origen': 'inventario_planeamiento_municipal', 'url': INVENTORY,
        'source_inventory_url': QUERY, 'source_detail_url': DETAIL,
        'source_detail_parameters': {'iddoc': str(item['id']), 'idp': '0', 'lang': 'gl_ES'},
        'source_document_id': str(item['id']), 'documentos': list(documents.values()),
        'incidencias_juridicas': detail.get('incidencias_iuris'),
        'source_metadata': {k: general.get(k) for k in (
            'fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop', 'fechatextodef')},
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'base_NSP_only', 'limitations': LIMITATIONS,
    }


class VilalbaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='vilalba', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        if slug != 'vilalba' or str(self.config.get('ine_code', '27065')) != '27065':
            raise ValueError('This adapter is restricted to Vilalba INE 27065')

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        captures = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-vilalba/1.0 (public planning inventory)'

            def fetch(url, name, data=None):
                with session.request('POST' if data else 'GET', url, data=data,
                                     timeout=40, stream=True) as response:
                    response.raise_for_status()
                    if urlparse(response.url).hostname != 'siotuga.xunta.gal':
                        raise ValueError('Unexpected source redirect')
                    body = bytearray()
                    for chunk in response.iter_content(65536):
                        body.extend(chunk)
                        if len(body) > 5_000_000:
                            raise ValueError('Source response too large; no truncated extraction')
                if captures:
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    with gzip.open(directory / (name + '.gz'), 'wb') as target:
                        target.write(body)
                return bytes(body)

            index = BeautifulSoup(fetch(INDEX, 'index.html'), 'html.parser')
            matches = [tr for tr in index.select('tr')
                       if [td.get_text(strip=True) for td in tr.select('td')][:2]
                       == ['27065', 'Vilalba']]
            if len(matches) != 1:
                raise ValueError('Official index no longer identifies Vilalba INE 27065')
            form = BeautifulSoup(fetch(INVENTORY, 'inventory.html'), 'html.parser')
            token = form.select_one('input#token')
            if token is None or not token.get('value'):
                raise ValueError('Anonymous inventory form unavailable')
            data = {'id': '27065', 'idclase': '14', 'token': token['value']}
            item = select_base_plan(json.loads(fetch(QUERY, 'general-planning.json', data)))
            params = {'iddoc': str(item['id']), 'idp': '0', 'lang': 'gl_ES', 'token': token['value']}
            detail = json.loads(fetch(DETAIL, 'plan-detail.json', params))
            row = parse_plan(item, detail)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(row, ensure_ascii=False) + '\n', encoding='utf-8')
        return {'status': 'ok', 'rows': 1, 'count': 1,
                'source_urls': [INDEX, INVENTORY, QUERY, DETAIL],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
