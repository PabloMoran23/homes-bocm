"""Meaño's approved planning inventory in the official Xunta SIOTUGA register."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = BASE + 'inventario?inv=1&idconcello=36027'
INVENTORY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
CLASSES = {14: 'planeamento_xeral', 13: 'planeamento_desenvolvemento', 18: 'delimitacion_nucleos_rurais'}


def source_date(value):
    if value is None or value == '':
        return None
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload):
    # The site's JS receives the entire array and paginates it locally with
    # DataTables. Do not accept an envelope that could hide server pagination.
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Expected complete SIOTUGA inventory array')
    found = {}
    for row in payload:
        if not isinstance(row, dict) or not str(row.get('id', '')).isdigit():
            raise ValueError('Invalid planning inventory identity')
        if not row.get('docnome') or not row.get('figura'):
            raise ValueError('Missing instrument title/type')
        key = str(row['id'])
        if key in found and found[key] != row:
            raise ValueError('Conflicting duplicate instrument')
        found[key] = row
    return list(found.values())


def parse_project(row, detail, category):
    general = detail['datos_xerais']
    if (general.get('menutitle') != 'Meaño' or general.get('folder') != 'MEANO'
            or str(general.get('id')) != str(row['id'])):
        raise ValueError('Detail belongs to another municipality/instrument')
    for key in ('figura', 'fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
        if general.get(key) != row.get(key):
            raise ValueError('Inventory/detail disagree: ' + key)
    if general.get('denominacion') != row['docnome']:
        raise ValueError('Inventory/detail titles disagree')
    if general.get('filesroot') != 'documentos/urbanismo/':
        raise ValueError('Unexpected document root')
    documents = {}
    for group in detail['elementos']:
        for component in group['componentes']:
            name = component['pathesperado']
            # Match the public UI's filesroot + folder + /documents/ + path.
            url = urljoin(BASE, general['filesroot'] + general['folder'] + '/documents/' + quote(name, safe='/'))
            if (urlparse(url).hostname != 'siotuga.xunta.gal'
                    or not urlparse(url).path.startswith('/siotuga/documentos/urbanismo/MEANO/documents/')
                    or '..' in name.split('/')):
                raise ValueError('Unexpected attachment path')
            documents[url] = {'id': str(component['id']), 'titulo': component['descripcion'],
                              'grupo': group['description'].strip(), 'url': url}
    if not documents:
        raise ValueError('Instrument has no source documents')
    approval = source_date(row.get('fechaaddef'))
    return {
        'id': 'meano-siotuga-' + str(row['id']), 'siotuga_id': str(row['id']),
        'municipio': 'Meaño', 'codigo_ine': '36027', 'provincia': 'Pontevedra',
        'titulo': row['docnome'], 'tipo': row['figura'], 'categoria_inventario': category,
        'fase': 'aprobación definitiva' if approval else None,
        'fecha': None, 'fecha_aprob': approval,
        'fecha_publicacion': None,
        'fecha_publicacion_bop': source_date(row.get('fechabop')),
        'fecha_publicacion_dog': source_date(row.get('fechadog')),
        'fecha_publicacion_normativa_bop': source_date(row.get('fechanormativabop')),
        'incidencias_juridicas': row.get('incidencias_iuris'),
        'url': SOURCE, 'url_documento': next(iter(documents)),
        'documentos': list(documents.values()),
        'source': 'xunta_siotuga', 'origen': 'inventario_municipal_planeamiento',
        'provenance': {'inventory_url': INVENTORY, 'inventory_parameters': {'id': '36027', 'idclase': next(k for k, v in CLASSES.items() if v == category)},
                       'detail_url': DETAIL, 'detail_parameters': {'iddoc': str(row['id']), 'idp': '0', 'lang': 'gl_ES'}},
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'Not extracted; linked plans are documents, not verified vector geometry',
    }


class MeanoAyuntamientoAdapter(AyuntamientoAdapter):
    def _capture(self, name, payload):
        if self.config.get('evidence_dir'):
            path = Path(self.config['evidence_dir']) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = {}
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-meano/1.0 (public planning inventory)'
            def fetch(url, data=None):
                response = (session.get(url, timeout=35) if data is None
                            else session.post(url, data=data, timeout=35))
                response.raise_for_status()
                if urlparse(response.url).hostname != 'siotuga.xunta.gal':
                    raise ValueError('Unexpected SIOTUGA redirect')
                return response
            page = BeautifulSoup(fetch(SOURCE).content, 'html.parser')
            option = page.select_one('#idconcello option[value="36027"]')
            if not option or option.get_text(strip=True) != 'Meaño':
                raise ValueError('Cannot verify INE 36027 in public inventory')
            # Public anonymous page nonce, never an account credential.
            nonce = page.select_one('#token')['value']
            for class_id, category in CLASSES.items():
                payload = fetch(INVENTORY, {'id': '36027', 'idclase': class_id, 'token': nonce}).json()
                self._capture(f'live-inventory-{class_id}.json', payload)
                for row in parse_inventory(payload):
                    key = str(row['id'])
                    if key in rows:
                        raise ValueError('Instrument appears in multiple inventory classes')
                    detail = fetch(DETAIL, {'iddoc': key, 'idp': '0', 'lang': 'gl_ES', 'token': nonce}).json()
                    self._capture(f'live-detail-{key}.json', detail)
                    rows[key] = parse_project(row, detail, category)
        if not rows:
            raise ValueError('No usable planning instruments in current inventory')
        self._write(out_jsonl, rows.values())
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, INVENTORY, DETAIL],
                'coverage': 'Complete returned arrays for classes 14, 13, 18; historical and territorial instruments excluded',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
