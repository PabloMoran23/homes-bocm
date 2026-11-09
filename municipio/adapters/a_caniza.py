"""A Cañiza planning inventory published by Xunta's public SIOTUGA portal."""
from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
INVENTORY = BASE + 'inventario?inv=1&idconcello=36009&lang=es_ES'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
# The inventory JS requests each whole class; DataTables paginates in-browser.
CLASSES = {14: 'general', 13: 'desarrollo', 16: 'historico', 18: 'nucleos_rurales'}
LIMITATIONS = [
    'Partial coverage: SIOTUGA municipal urban planning classes 14, 13, 16, 18 only; '
    'not municipal works, licences, pending applications or territorial/sectoral inventory.',
    'Historic instruments are explicitly labelled; approval does not establish current legal validity.',
    'Dates are source metadata, not independently reconciled with gazettes or document contents.',
    'Document links retained, not all attachments downloaded or availability-checked.',
    'No verified instrument geometry or coordinates; WMS/raster plans are not vector geometries.',
]


def source_date(value):
    if value in (None, ''):
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError(f'Unexpected source date: {value!r}')
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload):
    """Accept the complete anonymous API array, never a paginated envelope."""
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Expected complete SIOTUGA inventory array (pagination/schema changed)')
    rows = {}
    for item in payload:
        if not isinstance(item, dict) or not str(item.get('id', '')).isdigit():
            raise ValueError('Missing planning instrument ID')
        if not item.get('docnome', '').strip() or not item.get('figura', '').strip():
            raise ValueError('Missing planning instrument title/type')
        key = str(item['id'])
        if key in rows and rows[key] != item:
            raise ValueError('Conflicting duplicate instrument')
        rows[key] = item
    return list(rows.values())


def parse_instrument(item, payload, inventory_class):
    if not isinstance(payload, dict):
        raise ValueError('Missing planning instrument detail')
    meta = payload.get('datos_xerais') or {}
    if (str(meta.get('id')) != str(item['id']) or meta.get('folder') != 'ACANIZA'
            or meta.get('menutitle') != 'Cañiza, A'
            or meta.get('filesroot') != 'documentos/urbanismo/'):
        raise ValueError('Instrument detail municipality/identity mismatch')
    if (str(meta.get('denominacion', '')).strip() != item['docnome'].strip()
            or meta.get('figura') != item['figura']):
        raise ValueError('Inventory/detail title or type mismatch')
    for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
        if source_date(item.get(field)) != source_date(meta.get(field)):
            raise ValueError('Inventory/detail date mismatch')
    documents = {}
    elements = payload.get('elementos')
    if not isinstance(elements, list):
        raise ValueError('Missing document groups')
    for element in elements:
        components = element.get('componentes')
        if not isinstance(components, list):
            raise ValueError('Missing document components')
        for component in components:
            filename = component.get('pathesperado', '')
            if not re.fullmatch(r'[\w.-]+\.(?:pdf|jpg|jpeg|png|zip)', filename, re.I):
                raise ValueError('Unexpected attachment path; review source format')
            url = urljoin(BASE, meta['filesroot'] + meta['folder'] + '/documents/' + filename)
            doc = documents.setdefault(url, {'url': url, 'referencias': []})
            ref = {'id': str(component['id']), 'titulo': component['descripcion'],
                   'grupo': element['description']}
            if ref not in doc['referencias']:
                doc['referencias'].append(ref)
    if not documents:
        raise ValueError('Instrument has no source documents')
    approval = source_date(meta.get('fechaaddef'))
    return {
        'id': 'a-caniza-siotuga-' + str(item['id']),
        'municipio': 'A Cañiza', 'codigo_ine': '36009', 'provincia': 'Pontevedra',
        'titulo': item['docnome'].strip(), 'tipo': item['figura'],
        'fecha': None, 'fecha_acuerdo': None, 'fecha_aprob': approval,
        'fecha_publicacion': None,
        'fecha_publicacion_dog': source_date(meta.get('fechadog')),
        'fecha_publicacion_bop': source_date(meta.get('fechabop')),
        'fecha_publicacion_normativa_bop': source_date(meta.get('fechanormativabop')),
        'fecha_texto_refundido': source_date(meta.get('fechatextodef')),
        'url': INVENTORY, 'source': 'siotuga_xunta',
        'organismo_fuente': 'Xunta de Galicia — SIOTUGA',
        'origen': 'inventario_planeamiento_municipal',
        'source_id': str(item['id']), 'clase_inventario': CLASSES[inventory_class],
        'historico': inventory_class == 16,
        'incidencias_juridicas': payload.get('incidencias_iuris'),
        'incidencias_inventario': item.get('incidencias_iuris'),
        'provenance': {'inventory_url': INVENTORY, 'query_url': QUERY,
                       'query_parameters': {'id': '36009', 'idclase': inventory_class},
                       'detail_url': DETAIL,
                       'detail_parameters': {'iddoc': str(item['id']), 'idp': '0', 'lang': 'es_ES'}},
        'documentos': list(documents.values()),
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False,
    }


class ACanizaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, records):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('evidence_dir')
        if captures:
            captures = Path(captures)
            captures.mkdir(parents=True, exist_ok=True)

        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-a-caniza/1.0 (public planning inventory)'

            def fetch(url, data=None, capture=None):
                time.sleep(0.15)
                response = session.request('POST' if data is not None else 'GET', url,
                                           data=data, timeout=40)
                response.raise_for_status()
                response.encoding = 'utf-8'
                if capture and captures:
                    (captures / capture).write_text(response.text, encoding='utf-8')
                return response

            page = fetch(INVENTORY)
            soup = BeautifulSoup(page.text, 'html.parser')
            selected = soup.select_one('option[value="36009"]')
            if selected is None or selected.get_text(strip=True) != 'Cañiza, A':
                raise ValueError('Municipality missing from official inventory')
            # Public anti-CSRF form value obtained anonymously, never a user credential.
            form_value = soup.select_one('input#token')
            if form_value is None or not form_value.get('value'):
                raise ValueError('Anonymous inventory form changed')
            form_value = form_value['value']
            # Evidence excludes the transient anonymous form value.
            for node in soup.select('input#token'):
                node['value'] = '[redacted public form value]'
            if captures:
                (captures / 'inventory.html').write_text(str(soup), encoding='utf-8')
            instruments = {}
            for cls in CLASSES:
                payload = fetch(QUERY, {'id': '36009', 'idclase': cls, 'token': form_value},
                                f'inventory-class-{cls}.json').json()
                for item in parse_inventory(payload):
                    key = str(item['id'])
                    if key in instruments:
                        if instruments[key][0] != item or instruments[key][1] != cls:
                            raise ValueError('Instrument conflicts across inventory classes')
                        continue
                    instruments[key] = (item, cls)
            if not instruments:
                raise ValueError('No usable planning instruments; review source')
            records = []
            for key, (item, cls) in sorted(instruments.items()):
                detail = fetch(DETAIL, {'iddoc': key, 'idp': '0', 'lang': 'es_ES', 'token': form_value},
                               f'detail-{key}.json').json()
                records.append(parse_instrument(item, detail, cls))
        self._write(out_jsonl, records)
        return {'status': 'ok', 'rows': len(records), 'source_urls': [INVENTORY, QUERY, DETAIL],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        """Refresh all classes and attachments; no date cursor can miss older changes."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
