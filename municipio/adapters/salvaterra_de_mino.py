"""Salvaterra's municipal-linked SIOTUGA planning inventory (complete snapshot)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = ROOT + 'inventario?idconcello=36050&inv=1'
MUNICIPAL_SOURCE = 'https://www.concellodesalvaterra.com/departamentos/urbanismo'
INVENTORY_API = ROOT + 'assets/inventario/query_document.php'
DETAIL_API = ROOT + 'assets/inventario/getIOTPU.php'
CLASSES = {14: 'planeamiento_general', 13: 'planeamiento_desarrollo',
           16: 'planeamiento_historico', 18: 'delimitacion_nucleo_rural'}
LIMITATIONS = [
    'Partial municipal coverage: SIOTUGA urban planning only; not a public works or granted licence register.',
    'Inventory includes historical instruments; presence does not establish current legal validity or execution.',
    'Attachments are source links, not individually downloaded or interpreted by the adapter.',
    'Some source dossiers have no attachments; source date inconsistencies are retained and flagged.',
    'No verified geometry or coordinates; publication_ready=false.',
    'Territorial planning inventory and environmental assessment dossiers are outside this adapter coverage.',
]


def source_date(value):
    if value in (None, ''):
        return None
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload):
    """The public JS consumes a whole array, then paginates in the browser."""
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Expected complete SIOTUGA array; pagination/schema changed')
    records = {}
    for row in payload:
        if not isinstance(row, dict) or not str(row.get('id', '')).isdigit():
            raise ValueError('Invalid SIOTUGA instrument identity')
        if not row.get('figura') or not (row.get('docnome') or row.get('figura')):
            raise ValueError('Missing planning instrument title/type')
        key = str(row['id'])
        if key in records and records[key] != row:
            raise ValueError('Conflicting duplicate SIOTUGA instrument')
        records[key] = row
    return list(records.values())


def parse_project(summary, detail, category):
    general = detail['datos_xerais']
    key = str(summary['id'])
    if str(general.get('id')) != key or general.get('menutitle') != 'Salvaterra de Miño':
        raise ValueError('Dossier identity/municipality mismatch')
    for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
        if summary.get(field) != general.get(field):
            raise ValueError('Inventory/detail date mismatch: ' + field)
    if general.get('denominacion', '').strip() != (summary.get('docnome') or summary['figura']).strip():
        raise ValueError('Inventory/detail title mismatch')
    if general.get('figura') != summary['figura']:
        raise ValueError('Inventory/detail instrument type mismatch')
    documents = {}
    for section in detail.get('elementos') or []:
        for component in section.get('componentes') or []:
            filename = component['pathesperado']
            target = urljoin(ROOT, general['filesroot'] + general['folder'] + '/documents/' + filename)
            parsed = urlparse(target)
            if (parsed.scheme != 'https' or parsed.hostname != 'siotuga.xunta.gal'
                    or not parsed.path.startswith('/siotuga/documentos/urbanismo/SALVATERRADEMINO/documents/')
                    or '..' in filename or not filename):
                raise ValueError('Unexpected source document location')
            if target not in documents:
                documents[target] = {'url': target, 'titulo': component['descripcion'],
                                     'source_component_id': str(component['id']), 'secciones': []}
            if section['description'] not in documents[target]['secciones']:
                documents[target]['secciones'].append(section['description'])
    approval = source_date(general.get('fechaaddef'))
    bop = source_date(general.get('fechabop'))
    dog = source_date(general.get('fechadog'))
    warnings = []
    if any(p and approval and p < approval for p in (bop, dog)):
        warnings.append('Source publication date precedes recorded definitive approval; not corrected')
    if not documents:
        warnings.append('No attachments exposed by source dossier')
    return {
        'id': 'salvaterra-de-mino-siotuga-' + key,
        'siotuga_document_id': key, 'municipio': 'Salvaterra de Miño',
        'codigo_ine': '36050', 'provincia': 'Pontevedra',
        'titulo': general['denominacion'].strip(), 'tipo': summary['figura'],
        'categoria_inventario': CLASSES[category],
        'fase': 'aprobación definitiva según inventario' if approval else None,
        'fecha': None, 'fecha_acuerdo': None, 'fecha_aprob': approval,
        'fecha_publicacion': None, 'fecha_publicacion_bop': bop, 'fecha_publicacion_dog': dog,
        'fecha_publicacion_normativa_bop': source_date(general.get('fechanormativabop')),
        'fecha_texto_refundido': source_date(general.get('fechatextodef')),
        'source': 'ayuntamiento', 'source_publisher': 'Xunta de Galicia — SIOTUGA',
        'origen': 'inventario_planeamiento_municipal_enlazado_por_concello',
        'url': SOURCE, 'municipal_source_url': MUNICIPAL_SOURCE,
        'provenance': {
            'inventory': {'url': INVENTORY_API, 'method': 'POST',
                          'parameters': {'id': '36050', 'idclase': category}},
            'detail': {'url': DETAIL_API, 'method': 'POST',
                       'parameters': {'iddoc': key, 'idp': 0, 'lang': 'gl_ES'}},
            'date_fields': {'fecha_aprob': 'fechaaddef', 'fecha_publicacion_bop': 'fechabop',
                            'fecha_publicacion_dog': 'fechadog',
                            'fecha_publicacion_normativa_bop': 'fechanormativabop',
                            'fecha_texto_refundido': 'fechatextodef'},
        },
        'documentos': list(documents.values()),
        'incidencias_juridicas_inventario': summary.get('incidencias_iuris'),
        'incidencias_juridicas_ficha': detail.get('incidencias_iuris'),
        'quality_warnings': warnings,
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class SalvaterraDeMinoAyuntamientoAdapter(AyuntamientoAdapter):
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
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-salvaterra-planning/1.0'

            def fetch(url, name, data=None):
                response = session.get(url, timeout=35) if data is None else session.post(url, data=data, timeout=35)
                response.raise_for_status()
                if urlparse(response.url).hostname != 'siotuga.xunta.gal':
                    raise ValueError('Unexpected SIOTUGA redirect')
                self._capture(name, response.content)
                return response

            response = fetch(SOURCE, 'siotuga-inventory.html')
            soup = BeautifulSoup(response.content, 'html.parser')
            option = soup.select_one('option[value="36050"]')
            token = soup.select_one('input#token')
            if not option or option.get_text(strip=True) != 'Salvaterra de Miño' or not token:
                raise ValueError('SIOTUGA public inventory form unavailable')
            # Anonymous form nonce from the public page; no authentication.
            nonce = token['value']
            inventory = {}
            for category in CLASSES:
                payload = fetch(INVENTORY_API, f'inventory-{category}.json',
                                {'id': '36050', 'idclase': category, 'token': nonce}).json()
                for summary in parse_inventory(payload):
                    key = str(summary['id'])
                    if key in inventory:
                        if inventory[key][0] != summary:
                            raise ValueError('Conflicting instrument across inventory classes')
                        continue
                    inventory[key] = (summary, category)
            if not inventory:
                raise ValueError('No usable municipal planning instruments')
            rows = []
            for key, (summary, category) in inventory.items():
                detail = fetch(DETAIL_API, f'detail-{key}.json',
                               {'iddoc': key, 'idp': 0, 'lang': 'gl_ES', 'token': nonce}).json()
                rows.append(parse_project(summary, detail, category))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'coverage': 'SIOTUGA urban planning inventory snapshot',
                'source_urls': [MUNICIPAL_SOURCE, SOURCE, INVENTORY_API, DETAIL_API],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
