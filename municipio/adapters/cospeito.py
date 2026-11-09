"""Cospeito planning instruments from the Xunta's public SIOTUGA inventory."""
from __future__ import annotations

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
SOURCE = ROOT + 'inventario?inv=1&idconcello=27015'
QUERY = ROOT + 'assets/inventario/query_document.php'
DETAIL = ROOT + 'assets/inventario/getIOTPU.php'
CLASSES = (14, 13, 16, 18)  # general, development, historical, rural delimitations


def source_date(value):
    if value in (None, ''):
        return None
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload):
    # The official JS receives a complete array and paginates it client-side.
    # Reject a future server-side pagination envelope instead of losing pages.
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Expected complete SIOTUGA array; pagination/schema changed')
    rows = {}
    for item in payload:
        if not isinstance(item, dict) or not str(item.get('id', '')).isdigit():
            raise ValueError('Invalid SIOTUGA instrument identity')
        if not item.get('docnome') or not item.get('figura'):
            raise ValueError('Missing instrument title/type')
        key = str(item['id'])
        if key in rows and rows[key] != item:
            raise ValueError('Conflicting duplicate instrument')
        rows[key] = item
    return list(rows.values())


def parse_instrument(item, payload, classes):
    general = payload['datos_xerais']
    key = str(item['id'])
    if (str(general['id']) != key or general['menutitle'].strip() != 'Cospeito'
            or general['folder'] != 'COSPEITO'):
        raise ValueError('Detail identity/municipality mismatch')
    if general['denominacion'].strip() != item['docnome'].strip():
        raise ValueError('Inventory/detail title mismatch')
    for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
        if source_date(item.get(field)) != source_date(general.get(field)):
            raise ValueError('Inventory/detail date mismatch')
    documents = {}
    for group in payload['elementos']:
        for component in group['componentes']:
            filename = component['pathesperado']
            if not re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:pdf|jpg|jpeg|png)', filename, re.I):
                raise ValueError('Unexpected document path')
            url = urljoin(ROOT, general['filesroot'] + general['folder'] + '/documents/' + filename)
            if urlparse(url).hostname != 'siotuga.xunta.gal':
                raise ValueError('Unexpected document host')
            documents.setdefault(url, {
                'id_origen': str(component['id']), 'titulo': component['descripcion'],
                'grupo': group['description'], 'url': url,
            })
    if not documents:
        raise ValueError('Instrument without source documents')
    return {
        'id': 'cospeito-siotuga-' + key, 'id_origen': key,
        'municipio': 'Cospeito', 'codigo_ine': '27015', 'provincia': 'Lugo',
        'titulo': item['docnome'].strip(), 'tipo': item['figura'],
        'entity_type': 'expediente', 'expediente': 'SIOTUGA/' + key,
        'fecha': None, 'fecha_aprob': source_date(item.get('fechaaddef')),
        'fecha_publicacion': None,
        'fecha_publicacion_bop': source_date(item.get('fechabop')),
        'fecha_publicacion_dog': source_date(item.get('fechadog')),
        'fecha_publicacion_normativa_bop': source_date(item.get('fechanormativabop')),
        'fecha_texto_refundido': source_date(general.get('fechatextodef')),
        'incidencias_juridicas': payload.get('incidencias_iuris'),
        'url': SOURCE, 'source': 'siotuga', 'source_dataset': SOURCE,
        'origen': 'inventario_planeamiento_xunta',
        'provenance': {
            'publisher': 'Xunta de Galicia', 'inventory_classes': sorted(classes),
            'inventory_request': {'method': 'POST', 'url': QUERY, 'id': '27015'},
            'detail_request': {'method': 'POST', 'url': DETAIL, 'iddoc': key, 'idp': 0, 'lang': 'gl_ES'},
            'date_semantics': 'fechaaddef is definitive approval; BOP/DOG dates are publications. Legal exclusions retained; approval does not imply every area is approved.',
        },
        'documentos': list(documents.values()),
        'geometry': None, 'lat': None, 'lon': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class CospeitoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, records):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
        tmp.replace(path)
        return {'status': 'ok', 'rows': len(records)}

    def backfill_proyectos(self, out_jsonl):
        capture = self.config.get('capture_dir')
        if capture:
            capture = Path(capture)
            capture.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-cospeito/1.0'

            def fetch(url, name, data=None):
                time.sleep(.2)
                response = session.get(url, timeout=35) if data is None else session.post(url, data=data, timeout=35)
                response.raise_for_status()
                response.encoding = 'utf-8'
                if capture:
                    (capture / name).write_text(response.text, encoding='utf-8')
                return response

            page = BeautifulSoup(fetch(SOURCE, 'inventory.html').text, 'html.parser')
            # Public anti-CSRF form value, obtained anew in the same anonymous session.
            token = page.select_one('input#token')
            option = page.select_one('select#idconcello option[value="27015"]')
            if token is None or option is None or option.get_text(strip=True) != 'Cospeito':
                raise ValueError('SIOTUGA inventory form/municipality changed')
            instruments = {}
            for category in CLASSES:
                data = {'id': '27015', 'token': token['value'], 'idclase': category}
                rows = parse_inventory(fetch(QUERY, f'class-{category}.json', data).json())
                for item in rows:
                    key = str(item['id'])
                    if key in instruments and instruments[key][0] != item:
                        raise ValueError('Conflicting instrument across classes')
                    instruments.setdefault(key, (item, set()))[1].add(category)
            if not instruments:
                raise ValueError('Empty planning inventory requires review')
            records = []
            for key, (item, categories) in sorted(instruments.items()):
                data = {'iddoc': key, 'idp': 0, 'lang': 'gl_ES', 'token': token['value']}
                detail = fetch(DETAIL, f'document-{key}.json', data).json()
                records.append(parse_instrument(item, detail, categories))
        return {**self._write(out_jsonl, records), 'source_urls': [SOURCE, QUERY, DETAIL]}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh, including all four inventory classes and all documents.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
