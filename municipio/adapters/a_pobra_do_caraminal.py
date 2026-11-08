"""Municipality-scoped SIOTUGA planning inventory (general and development)."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = ROOT + 'inventario?inv=1&idconcello=15067&lang=es_ES'
QUERY = ROOT + 'assets/inventario/query_document.php'
DETAIL = ROOT + 'assets/inventario/getIOTPU.php'
CLASSES = (14, 13)  # General and development; historical inventory is excluded.


def source_date(value):
    if value is None or value == '':
        return None
    return date.fromisoformat(value).isoformat()


class APobraDoCaraminalAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(payload):
        if payload is None:
            return []
        # The public UI receives a complete array and paginates client-side.
        # Reject envelopes (including newly introduced server pagination).
        if not isinstance(payload, list):
            raise ValueError('Expected complete SIOTUGA inventory array')
        result = {}
        for item in payload:
            if not isinstance(item, dict) or not re.fullmatch(r'\d+', str(item.get('id', ''))):
                raise ValueError('Invalid planning instrument')
            if not item.get('docnome') or not item.get('figura'):
                raise ValueError('Missing instrument title or figure')
            key = str(item['id'])
            if key in result and result[key] != item:
                raise ValueError('Conflicting instrument identifiers')
            result[key] = item
        return list(result.values())

    @staticmethod
    def parse_project(item, detail, inventory_class):
        general = detail['datos_xerais']
        if str(general['id']) != str(item['id']) or general['menutitle'] != 'Pobra do Caramiñal, A':
            raise ValueError('Detail does not belong to requested instrument/municipality')
        if general['denominacion'].strip() != item['docnome'].strip():
            raise ValueError('Inventory/detail title mismatch')
        docs = {}
        for section in detail['elementos'] or []:
            for component in section['componentes']:
                url = urljoin(ROOT, general['filesroot'] + general['folder'] + '/documents/' + component['pathesperado'])
                if urlparse(url).hostname != 'siotuga.xunta.gal' or '/POBRADOCARAMINAL/documents/' not in urlparse(url).path:
                    raise ValueError('Unexpected document provenance')
                docs[url] = {'titulo': component['descripcion'], 'url': url, 'seccion': section['description']}
        incidences = item.get('incidencias_iuris')
        return {
            'id': 'a-pobra-do-caraminal-siotuga-' + str(item['id']),
            'municipio': 'A Pobra do Caramiñal', 'codigo_ine': '15067', 'provincia': 'A Coruña',
            'titulo': item['docnome'].strip(), 'tipo': item['figura'],
            'fecha': None, 'fecha_publicacion': None,
            # Complex partial/conditional approvals are retained verbatim below;
            # the inventory's first approval is not the final approval date.
            'fecha_aprob': None if incidences else source_date(item.get('fechaaddef')),
            'fecha_publicacion_dog': source_date(item.get('fechadog')),
            'fecha_publicacion_bop': source_date(item.get('fechabop')),
            'fecha_publicacion_normativa_bop': source_date(item.get('fechanormativabop')),
            'incidencias_juridicas': incidences,
            'fechas_fuente': {k: item.get(k) for k in ('fechaaddef', 'fechadog', 'fechabop', 'fechanormativabop')},
            'url': SOURCE, 'source': 'siotuga_xunta', 'origen': 'inventario_planeamiento_municipal',
            'source_id': str(item['id']), 'inventory_class': inventory_class,
            'provenance': {'inventory_endpoint': QUERY, 'detail_endpoint': DETAIL,
                           'detail_parameters': {'iddoc': str(item['id']), 'idp': '0', 'lang': 'es_ES'}},
            'documentos': list(docs.values()),
            'documentos_status': 'linked' if docs else 'No attachments exposed by SIOTUGA detail',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        }

    def _capture(self, name, content):
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(content)

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
            session.headers['User-Agent'] = 'municipio-a-pobra-do-caraminal/1.0'
            response = session.get(SOURCE, timeout=40)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            selected = soup.select_one('select#idconcello option[value="15067"]')
            if not selected or selected.get_text(strip=True) != 'Pobra do Caramiñal, A':
                raise ValueError('Municipality missing from official inventory')
            # Anonymous page-issued request nonce, never an account credential.
            nonce = soup.select_one('input#token')
            if not nonce or not nonce.get('value'):
                raise ValueError('Missing public inventory request nonce')
            self._capture('inventory.html', response.content)
            for inventory_class in CLASSES:
                response = session.post(QUERY, data={'id': '15067', 'idclase': inventory_class,
                                                    'token': nonce['value']}, timeout=40)
                response.raise_for_status()
                self._capture(f'class-{inventory_class}.json', response.content)
                for item in self.parse_inventory(response.json()):
                    if str(item['id']) in rows:
                        raise ValueError('Instrument occurs in multiple classes; review grouping')
                    response = session.post(DETAIL, data={'iddoc': item['id'], 'idp': 0,
                                                         'lang': 'es_ES', 'token': nonce['value']}, timeout=40)
                    response.raise_for_status()
                    self._capture(f'detail-{item["id"]}.json', response.content)
                    rows[str(item['id'])] = self.parse_project(item, response.json(), inventory_class)
        if not rows:
            raise ValueError('Empty planning inventory; review live sources')
        self._write(out_jsonl, rows.values())
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, QUERY, DETAIL],
                'coverage': 'Complete classes 14 and 13; excludes historical, IOT, licences and works'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
