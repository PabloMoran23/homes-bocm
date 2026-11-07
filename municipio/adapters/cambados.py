"""Cambados planning inventory, published by Xunta and linked by the municipal sede."""
from __future__ import annotations

import gzip
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = ROOT + 'inventario?inv=1&idconcello=36006'
QUERY = ROOT + 'assets/inventario/query_document.php'
DETAIL = ROOT + 'assets/inventario/getIOTPU.php'
CLASSES = {14: 'planeamento_xeral', 13: 'planeamento_desenvolvemento', 18: 'delimitacion_nucleo_rural'}


def source_date(value):
    if value is None or value == '':
        return None
    # An unexpected date must not silently become a fabricated or missing date.
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload):
    """The UI receives the complete array, then paginates it client-side."""
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Expected complete SIOTUGA array; pagination/schema requires review')
    rows = {}
    for row in payload:
        if not isinstance(row, dict) or not str(row.get('id', '')).isdigit():
            raise ValueError('Missing official planning document identity')
        if not row.get('docnome') or not row.get('figura'):
            raise ValueError('Missing planning instrument title or figure')
        key = str(row['id'])
        if key in rows and rows[key] != row:
            raise ValueError('Conflicting duplicate planning identifier')
        rows[key] = row
    return list(rows.values())


def parse_project(item, detail, class_id):
    """One official instrument ID, with all its component documents retained."""
    general = detail.get('datos_xerais', {}) if isinstance(detail, dict) else {}
    key = str(item['id'])
    if str(general.get('id')) != key or general.get('menutitle') != 'Cambados':
        raise ValueError('Detail does not belong to the requested Cambados instrument')
    for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
        if source_date(general.get(field)) != source_date(item.get(field)):
            raise ValueError('Inventory/detail date disagreement')
    if general.get('folder') != 'CAMBADOS':
        raise ValueError('Unexpected municipal document folder')
    folder = urljoin(ROOT, general.get('filesroot', '') + general['folder'] + '/documents/')
    if not folder.startswith(ROOT + 'documentos/urbanismo/CAMBADOS/documents/'):
        raise ValueError('Unexpected document root')
    documents = {}
    elements = detail.get('elementos')
    if 'elementos' not in detail or (elements is not None and not isinstance(elements, list)):
        raise ValueError('Missing document component inventory')
    for group in elements or []:
        for component in group['componentes']:
            filename = component['pathesperado']
            if not re.fullmatch(r'[\w.-]+\.(?:pdf|jpg|jpeg|png|zip)', filename, re.I):
                raise ValueError('Unexpected component filename')
            url = urljoin(folder, filename)
            document = {'id': str(component['id']), 'titulo': component['descripcion'],
                        'grupo': group['description'], 'url': url}
            # A file can occur under several source sections/component IDs.
            # Retain those source contexts; collapse only identical entries.
            documents[json.dumps(document, sort_keys=True)] = document
    return {
        'id': 'cambados-siotuga-' + key, 'id_origen': key,
        'municipio': 'Cambados', 'codigo_ine': '36006', 'provincia': 'Pontevedra',
        'titulo': item['figura'] + ': ' + item['docnome'].strip(),
        'tipo': item['figura'], 'categoria': 'planeamiento_urbanistico',
        'fecha': None, 'fecha_aprob': source_date(item.get('fechaaddef')),
        'fecha_publicacion': None,
        'fecha_publicacion_dog': source_date(item.get('fechadog')),
        'fecha_publicacion_bop': source_date(item.get('fechabop')),
        'fecha_publicacion_normativa_bop': source_date(item.get('fechanormativabop')),
        'fecha_texto_refundido_fuente': source_date(general.get('fechatextodef')),
        'incidencias_juridicas': item.get('incidencias_iuris'),
        'incidencias_juridicas_detalle': detail.get('incidencias_iuris'),
        'url': SOURCE, 'source': 'xunta_siotuga', 'origen': CLASSES[class_id],
        'provenance': {'inventory_url': QUERY, 'inventory_method': 'POST',
                       'inventory_parameters': {'id': '36006', 'idclase': class_id},
                       'detail_url': DETAIL, 'detail_method': 'POST',
                       'detail_parameters': {'iddoc': key, 'idp': 0, 'lang': 'gl_ES'}},
        'documentos': list(documents.values()),
        'document_coverage': 'linked_components' if documents else 'no_components_available_in_source',
        'geometry': None, 'lat': None, 'lon': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class CambadosAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://cambados.sedelectronica.gal')

    def _capture(self, name, content):
        if self.config.get('capture_dir'):
            target = Path(self.config['capture_dir'])
            target.mkdir(parents=True, exist_ok=True)
            (target / (name + '.gz')).write_bytes(gzip.compress(content))

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = {}
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-cambados/1.0 (public planning inventory)'
            response = session.get(SOURCE, timeout=45)
            response.raise_for_status()
            soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
            # This is the anonymous public form's anti-CSRF value, not a login.
            token = soup.select_one('input#token')
            option = soup.select_one('select#idconcello option[value="36006"]')
            if token is None or option is None or option.get_text(strip=True) != 'Cambados':
                raise ValueError('Cambados public inventory form changed')
            public_token = token['value']
            token['value'] = '[public form token omitted]'
            self._capture('inventory.html', str(soup).encode())
            for class_id in CLASSES:
                response = session.post(QUERY, data={'id': '36006', 'idclase': class_id, 'token': public_token}, timeout=45)
                response.raise_for_status()
                inventory = parse_inventory(response.json())
                self._capture(f'class-{class_id}.json', response.content)
                for item in inventory:
                    key = str(item['id'])
                    if key in rows:
                        raise ValueError('Instrument repeated across planning classes')
                    time.sleep(0.2)
                    response = session.post(DETAIL, data={'iddoc': key, 'idp': 0, 'lang': 'gl_ES', 'token': public_token}, timeout=45)
                    response.raise_for_status()
                    self._capture('detail-' + key + '.json', response.content)
                    rows[key] = parse_project(item, response.json(), class_id)
        if not rows:
            raise ValueError('Empty Cambados planning inventory requires review')
        self._write(out_jsonl, list(rows.values()))
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, QUERY, DETAIL],
                'coverage': 'SIOTUGA general/development/rural-delimitation inventory; excludes historical class 16 and territorial instruments',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'Application forms are not granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
