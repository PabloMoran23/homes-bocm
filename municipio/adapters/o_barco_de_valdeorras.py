"""O Barco planning inventory, served by the Xunta and linked by the council."""
from __future__ import annotations

import gzip
import json
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = BASE + 'inventario.php?inv=1&idconcello=32009'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
CLASSES = {14: 'planeamento_xeral', 13: 'planeamento_desenvolvemento'}


def source_date(value):
    if value in (None, ''):
        return None
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload):
    # The site's DataTables pagination is client side: the endpoint returns the
    # entire array, without start/length. Reject a changed paginated envelope.
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Expected complete inventory array; pagination/schema changed')
    rows = {}
    for item in payload:
        if not isinstance(item, dict) or not str(item.get('id', '')).isdigit():
            raise ValueError('Invalid inventory item')
        if not item.get('docnome') or not item.get('figura'):
            raise ValueError('Missing planning title/type')
        key = str(item['id'])
        if key in rows and rows[key] != item:
            raise ValueError('Conflicting planning identifier')
        rows[key] = item
    return list(rows.values())


def parse_project(item, detail, category):
    general = detail['datos_xerais']
    if str(general['id']) != str(item['id']) or general['menutitle'] != 'Barco de Valdeorras, O':
        raise ValueError('Detail does not belong to requested instrument/municipality')
    for key in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
        if general.get(key) != item.get(key):
            raise ValueError('Inventory/detail date mismatch')
    approval = source_date(general.get('fechaaddef'))
    publications = []
    anomalies = []
    for field, medium in (('fechabop', 'BOP'), ('fechadog', 'DOG'), ('fechanormativabop', 'BOP normativa')):
        value = source_date(general.get(field))
        if value:
            publications.append({'medio': medium, 'fecha': value, 'campo_fuente': field})
            if approval and value < approval:
                anomalies.append(f'{field} precedes fechaaddef in source; retained without correction')
    docs = {}
    root = urljoin(BASE, general['filesroot'] + general['folder'] + '/documents/')
    if not root.startswith(BASE + 'documentos/urbanismo/OBARCODEVALDEORRAS/documents/'):
        raise ValueError('Unexpected municipal document root')
    for group in detail['elementos'] or []:
        for component in group['componentes'] or []:
            filename = component['pathesperado']
            if '/' in filename or '\\' in filename or filename in ('', '.', '..'):
                raise ValueError('Invalid document filename')
            url = urljoin(root, filename)
            docs.setdefault(url, {'id': str(component['id']), 'titulo': component['descripcion'].strip(),
                                  'grupo': group['description'].strip(), 'url': url})
    if not docs:
        anomalies.append('Official inventory/detail identifies instrument but exposes no document components')
    return {
        'id': 'o-barco-de-valdeorras-siotuga-' + str(item['id']),
        'municipio': 'O Barco de Valdeorras', 'codigo_ine': '32009', 'provincia': 'Ourense',
        'titulo': item['docnome'].strip(), 'tipo': item['figura'],
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': approval, 'publicaciones': publications,
        'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'siotuga_inventario_municipal',
        'organismo_fuente': 'Xunta de Galicia', 'categoria_inventario': category,
        'fuente_detalle': {'url': DETAIL, 'metodo': 'POST', 'parametros': {'iddoc': str(item['id']), 'idp': 0, 'lang': 'gl_ES'}},
        'incidencias_iuris': detail.get('incidencias_iuris'),
        'incidencias_iuris_inventario': item.get('incidencias_iuris'),
        'documentos': list(docs.values()),
        'documentos_status': 'linked' if docs else 'unavailable_in_source',
        'fechas_fuente': {k: general.get(k) for k in
            ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop', 'fechatextodef')},
        'advertencias_fuente': anomalies, 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class OBarcoDeValdeorrasAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.concellodobarco.gal')

    def _capture(self, name, value):
        if self.config.get('evidence_dir'):
            target = Path(self.config['evidence_dir']) / (name + '.json.gz')
            target.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(target, 'wt', encoding='utf-8') as stream:
                json.dump(value, stream, ensure_ascii=False)

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-o-barco-de-valdeorras/1.0'
            response = session.get(SOURCE, timeout=40)
            response.raise_for_status()
            page = BeautifulSoup(response.content, 'html.parser')
            selected = page.select_one('option[value="32009"]')
            if not selected or selected.get_text(strip=True) != 'Barco de Valdeorras, O':
                raise ValueError('Municipal inventory identity missing')
            # Anonymous anti-CSRF page value, freshly obtained without login.
            token = page.select_one('#token')['value']

            def post(url, params):
                time.sleep(.15)
                result = session.post(url, data={**params, 'token': token}, timeout=40)
                result.raise_for_status()
                return result.json()

            items = {}
            for cls, category in CLASSES.items():
                payload = post(QUERY, {'id': '32009', 'idclase': cls})
                self._capture('inventory-' + str(cls), payload)
                for item in parse_inventory(payload):
                    key = str(item['id'])
                    if key in items and items[key][0] != item:
                        raise ValueError('Conflicting instrument across inventory classes')
                    items[key] = (item, category)
            if not items:
                raise ValueError('No planning instruments; source requires review')
            rows = []
            for key, (item, category) in items.items():
                detail = post(DETAIL, {'iddoc': key, 'idp': 0, 'lang': 'gl_ES'})
                self._capture('detail-' + key, detail)
                rows.append(parse_project(item, detail, category))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, QUERY, DETAIL],
                'coverage': 'Complete returned classes 14 and 13; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
