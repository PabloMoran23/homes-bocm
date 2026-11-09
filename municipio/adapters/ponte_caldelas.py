"""Ponte Caldelas municipal planning inventory published by Xunta SIOTUGA."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = BASE + 'inventario.php?inv=1&idconcello=36043'
CLASSES = (14, 13, 16, 18)  # general, development, historical, rural boundaries
LIMITATIONS = [
    'Partial coverage: SIOTUGA municipal planning inventory only; excludes territorial/sectoral inventories, municipal works and plans still in processing.',
    'No granted licence register extracted; application forms excluded.',
    'Dates are SIOTUGA metadata, with approval, BOP, DOG and normative publication kept separate.',
    'Some instrument files are unavailable; linked scans are not verified vector geometry. No coordinates inferred.',
]


def _date(value):
    return date.fromisoformat(value).isoformat() if value else None


def parse_inventory(payload):
    """The public endpoint returns the entire array; DataTables pages it locally."""
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Expected complete inventory array; refusing a paginated envelope')
    rows = {}
    for item in payload:
        if not isinstance(item, dict) or not str(item.get('id', '')).isdigit() or not item.get('figura'):
            raise ValueError('Invalid planning inventory row')
        key = str(item['id'])
        if key in rows and rows[key] != item:
            raise ValueError('Conflicting inventory IDs')
        rows[key] = item
    return list(rows.values())


def parse_instrument(item, detail, class_ids):
    general = detail['datos_xerais']
    if (str(general['id']) != str(item['id']) or general['menutitle'] != 'Ponte Caldelas'
            or general['folder'] != 'PONTECALDELAS'):
        raise ValueError('Instrument identity/municipality mismatch')
    for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
        if general.get(field) != item.get(field):
            raise ValueError('Inventory/detail dates disagree')
    docs = {}
    elements = detail.get('elementos')
    if elements is not None and not isinstance(elements, list):
        raise ValueError('Unexpected document groups')
    for group in elements or []:
        for component in group['componentes']:
            filename = component['pathesperado']
            root = general['filesroot'] + general['folder'] + '/documents/'
            url = urljoin(BASE, root + quote(filename))
            if urlparse(url).hostname != 'siotuga.xunta.gal' or not urlparse(url).path.startswith('/siotuga/documentos/urbanismo/PONTECALDELAS/documents/'):
                raise ValueError('Unexpected document origin')
            doc = docs.setdefault(url, {'url': url, 'titulo': component['descripcion'], 'grupos': []})
            if group['description'] not in doc['grupos']:
                doc['grupos'].append(group['description'])
    figure, name = general['figura'], general['denominacion']
    title = name if name.casefold() == figure.casefold() else figure + ' — ' + name
    return {
        'id': 'ponte-caldelas-siotuga-' + str(item['id']),
        'municipio': 'Ponte Caldelas', 'codigo_ine': '36043', 'provincia': 'Pontevedra',
        'titulo': title, 'tipo': 'planeamiento_urbanistico', 'figura': figure,
        'fecha': None, 'fecha_aprob': _date(general.get('fechaaddef')),
        'fecha_publicacion': None,
        'fecha_publicacion_bop': _date(general.get('fechabop')),
        'fecha_publicacion_dog': _date(general.get('fechadog')),
        'fecha_publicacion_normativa_bop': _date(general.get('fechanormativabop')),
        'fecha_texto_refundido': _date(general.get('fechatextodef')),
        'incidencias_juridicas': detail.get('incidencias_iuris'),
        'url': SOURCE, 'source': 'xunta_siotuga', 'origen': 'inventario_municipal_planeamiento',
        'source_id': str(item['id']), 'inventory_classes': sorted(class_ids),
        'provenance': {'inventory_endpoint': BASE + 'assets/inventario/query_document.php',
                       'inventory_parameters': {'id': '36043', 'idclase': sorted(class_ids)},
                       'detail_endpoint': BASE + 'assets/inventario/getIOTPU.php',
                       'detail_parameters': {'iddoc': str(item['id']), 'idp': '0', 'lang': 'gl_ES'}},
        'documentos': list(docs.values()),
        'documentos_status': 'linked' if docs else 'unavailable_in_source',
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'coverage': 'partial', 'publication_ready': False,
    }


class PonteCaldelasAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('evidence_dir')
        source_urls = [SOURCE]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-ponte-caldelas/1.0'

            def fetch(url, name, data=None):
                # Public anonymous form nonce from the inventory page; no authentication.
                response = session.get(url, timeout=40) if data is None else session.post(url, data=data, timeout=40)
                response.raise_for_status()
                source_urls.append(url) if url not in source_urls else None
                if captures:
                    p = Path(captures) / name
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(response.content)
                return response

            page = fetch(SOURCE, 'live-inventory.html')
            soup = BeautifulSoup(page.content, 'html.parser')
            nonce = soup.select_one('#token')
            municipality = soup.select_one('#idconcello option[value="36043"]')
            if not nonce or not municipality or municipality.get_text(strip=True) != 'Ponte Caldelas':
                raise ValueError('Unrecognized official municipality inventory')
            token = nonce['value']
            inventory, memberships = {}, {}
            for class_id in CLASSES:
                payload = fetch(BASE + 'assets/inventario/query_document.php', f'live-class-{class_id}.json',
                                {'id': '36043', 'idclase': class_id, 'token': token}).json()
                for item in parse_inventory(payload):
                    key = str(item['id'])
                    if key in inventory and inventory[key] != item:
                        raise ValueError('Conflicting instrument across inventory classes')
                    inventory[key] = item
                    memberships.setdefault(key, set()).add(class_id)
            if not inventory:
                raise ValueError('No usable planning instruments; source requires review')
            rows = []
            for key, item in inventory.items():
                detail = fetch(BASE + 'assets/inventario/getIOTPU.php', f'live-detail-{key}.json',
                               {'iddoc': key, 'idp': '0', 'lang': 'gl_ES', 'token': token}).json()
                rows.append(parse_instrument(item, detail, memberships[key]))
        return {**self._write(out_jsonl, rows), 'source_urls': source_urls, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot; no incremental timestamp is available from this source.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
