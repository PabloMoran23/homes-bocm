"""Muros planning inventory, officially linked by the municipal Urbanismo page."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
MUNICIPAL = 'https://muros.gal/urbanismo/'
SOURCE = BASE + 'inventario?inv=1&idconcello=15053'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
# These are whole JSON arrays used by client-side DataTables, without a page/limit.
CLASSES = (14, 13, 18)  # general, development, rural settlement delimitations


def source_date(value):
    if value in (None, ''):
        return None
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload):
    if payload is None:
        return []  # SIOTUGA's explicit empty result
    if not isinstance(payload, list):
        raise ValueError('Expected complete SIOTUGA array; pagination/envelope changed')
    result = {}
    for item in payload:
        if not isinstance(item, dict) or not str(item.get('id', '')).isdigit():
            raise ValueError('Invalid inventory item')
        key = str(item['id'])
        if key in result and result[key] != item:
            raise ValueError('Conflicting duplicate planning identifier')
        result[key] = item
    return list(result.values())


def parse_instrument(item, detail):
    info = detail['datos_xerais']
    if str(info['id']) != str(item['id']) or info['menutitle'] != 'Muros':
        raise ValueError('Detail belongs to another instrument or municipality')
    for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
        if item.get(field) != info.get(field):
            raise ValueError('Inventory/detail dates disagree')
    if not info.get('denominacion') or not info.get('figura'):
        raise ValueError('Missing instrument identity')
    root = urljoin(BASE, info['filesroot'] + info['folder'] + '/documents/')
    if not root.startswith(BASE + 'documentos/urbanismo/MUROS/documents/'):
        raise ValueError('Unexpected document provenance')
    docs = {}
    for group in detail['elementos']:
        for component in group['componentes']:
            url = urljoin(root, component['pathesperado'])
            if not url.startswith(root) or urlparse(url).query:
                raise ValueError('Unexpected document URL')
            doc = docs.setdefault(url, {'id': str(component['id']), 'titulo': component['descripcion'],
                                       'url': url, 'grupos': []})
            if group['description'] not in doc['grupos']:
                doc['grupos'].append(group['description'])
    if not docs:
        raise ValueError('Planning instrument has no source documents')
    return {
        'id': 'muros-siotuga-' + str(info['id']), 'siotuga_id': str(info['id']),
        'municipio': 'Muros', 'codigo_ine': '15053', 'provincia': 'A Coruña',
        'titulo': info['denominacion'], 'tipo': info['figura'],
        'fase': 'aprobación definitiva', 'fecha': None,
        'fecha_aprob': source_date(info.get('fechaaddef')),
        'fecha_acuerdo': None, 'fecha_publicacion': None,
        'fecha_publicacion_bop': source_date(info.get('fechabop')),
        'fecha_publicacion_dog': source_date(info.get('fechadog')),
        'fecha_publicacion_normativa_bop': source_date(info.get('fechanormativabop')),
        'fecha_texto_refundido': source_date(info.get('fechatextodef')),
        'incidencias_juridicas': detail.get('incidencias_iuris'),
        'url': SOURCE, 'url_municipal': MUNICIPAL, 'source': 'ayuntamiento',
        'origen': 'inventario_planeamiento_siotuga_xunta',
        'provenance': {'inventory_endpoint': QUERY, 'detail_endpoint': DETAIL,
                       'detail_parameters': {'iddoc': str(info['id']), 'idp': 0}},
        'documentos': list(docs.values()), 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class MurosAyuntamientoAdapter(AyuntamientoAdapter):
    def _capture(self, name, content):
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir']) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-muros/1.0'

            def fetch(url, name, data=None):
                response = session.get(url, timeout=40) if data is None else session.post(url, data=data, timeout=40)
                response.raise_for_status()
                self._capture(name, response.content)
                return response

            page = fetch(SOURCE, 'inventario-live.html')
            soup = BeautifulSoup(page.content, 'html.parser')
            option = soup.select_one('#idconcello option[value="15053"]')
            token = soup.select_one('input#token')
            if not option or option.get_text(strip=True) != 'Muros' or not token:
                raise ValueError('SIOTUGA municipality selector changed')
            # Anonymous form nonce, obtained from the public page, never persisted in records.
            common = {'id': '15053', 'token': token['value']}
            inventory = []
            for category in CLASSES:
                payload = fetch(QUERY, f'inventory-{category}.json', {**common, 'idclase': category}).json()
                inventory.extend(parse_inventory(payload))
            inventory = parse_inventory(inventory)
            if not inventory:
                raise ValueError('No current Muros planning records; review source')
            rows = []
            for item in inventory:
                detail = fetch(DETAIL, f"detail-{item['id']}.json", {
                    'iddoc': item['id'], 'idp': 0, 'lang': 'gl_ES', 'token': token['value']}).json()
                rows.append(parse_instrument(item, detail))
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [MUNICIPAL, SOURCE, QUERY, DETAIL],
                'inventory_classes': list(CLASSES), 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
