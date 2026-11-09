"""Abegondo's municipal-linked SIOTUGA planning inventory (not licences)."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
INVENTORY = BASE + 'inventario?inv=1&idconcello=15001'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
CLASSES = {14: 'planeamento_xeral', 13: 'planeamento_desenvolvemento',
           16: 'historico', 18: 'delimitacion_nucleo_rural'}
DATES = {'fechaaddef': 'fecha_aprob', 'fechabop': 'fecha_publicacion_bop',
         'fechadog': 'fecha_publicacion_dog',
         'fechanormativabop': 'fecha_publicacion_normativa_bop',
         'fechatextodef': 'fecha_texto_refundido'}


def parse_inventory(payload):
    # The official UI iterates the whole array and paginates locally in DataTables.
    # Reject new envelope/pagination formats instead of accepting the first page.
    if not isinstance(payload, list):
        raise ValueError('Expected complete SIOTUGA inventory array')
    seen = set()
    for item in payload:
        if not isinstance(item, dict) or not re.fullmatch(r'\d+', str(item.get('id', ''))):
            raise ValueError('Malformed instrument identifier')
        if not item.get('docnome') or not item.get('figura') or item['id'] in seen:
            raise ValueError('Missing title/type or duplicate instrument')
        seen.add(item['id'])
    return payload


def parse_instrument(item, detail, category):
    general = detail['datos_xerais']
    if (str(general['id']) != str(item['id']) or general['menutitle'] != 'Abegondo'
            or general['folder'] != 'ABEGONDO'):
        raise ValueError('Instrument/municipality mismatch')
    documents = {}
    for group in detail['elementos'] or []:
        for component in group['componentes']:
            filename = component['pathesperado']
            if not re.fullmatch(r'[\w. -]+', filename) or '..' in filename:
                raise ValueError('Unexpected document path')
            url = urljoin(BASE, general['filesroot'] + general['folder'] + '/documents/' + filename)
            if urlparse(url).hostname != 'siotuga.xunta.gal':
                raise ValueError('Unexpected document host')
            documents[url] = {'id_origen': component['id'], 'titulo': component['descripcion'],
                              'grupo': group['description'], 'url': url}
    row = {'id': 'abegondo-siotuga-' + str(item['id']), 'id_origen': str(item['id']),
           'municipio': 'Abegondo', 'codigo_ine': '15001', 'provincia': 'A Coruña',
           'titulo': item['docnome'].strip(), 'tipo': 'planeamiento_urbanistico',
           'figura': item['figura'], 'categoria_inventario': CLASSES[category],
           'documentos_status': 'linked' if documents else 'unavailable_in_source',
           'historico': category == 16, 'url': INVENTORY, 'inventory_url': INVENTORY,
           'source': 'xunta_siotuga', 'origen': 'inventario_municipal_planeamiento',
           'source_entity_type': 'expediente', 'documentos': list(documents.values()),
           'provenance': {'inventory_endpoint': QUERY, 'inventory_parameters': {'id': '15001', 'idclase': category},
                          'detail_endpoint': DETAIL, 'detail_parameters': {'iddoc': str(item['id']), 'idp': '0'},
                          'date_fields': DATES},
           'incidencias_juridicas': item.get('incidencias_iuris'),
           'incidencias_juridicas_detalle': detail.get('incidencias_iuris'),
           'publication_ready': False, 'geometry_status': 'unavailable'}
    for source, target in DATES.items():
        value = general.get(source)
        if source in item and value != item[source]:
            raise ValueError('Conflicting inventory/detail date: ' + source)
        if value:
            date.fromisoformat(value)
            row[target] = value
    return row


class AbegondoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path):
        capture = self.config.get('evidence_dir')

        def save(name, response):
            if capture:
                directory = Path(capture)
                directory.mkdir(parents=True, exist_ok=True)
                (directory / name).write_bytes(response.content)

        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'

            def fetch(url, data=None):
                response = (session.get(url, timeout=45) if data is None else
                            session.post(url, data=data, timeout=45))
                response.raise_for_status()
                if urlparse(response.url).hostname != 'siotuga.xunta.gal':
                    raise ValueError('Unexpected source redirect')
                return response

            response = fetch(INVENTORY)
            save('inventory-live.html', response)
            soup = BeautifulSoup(response.content, 'html.parser')
            selected = soup.select_one('#idconcello option[value="15001"]')
            if selected is None or selected.get_text(strip=True) != 'Abegondo':
                raise ValueError('Municipal inventory identity unavailable')
            # Public page CSRF field used by the official browser UI, not a credential.
            token = soup.select_one('#token')['value']
            rows, identifiers, counts = [], set(), {}
            for category in CLASSES:
                response = fetch(QUERY, {'id': '15001', 'idclase': category, 'token': token})
                save(f'query-{category}.json', response)
                items = parse_inventory(response.json())
                counts[CLASSES[category]] = len(items)
                for item in items:
                    if str(item['id']) in identifiers:
                        raise ValueError('Instrument occurs in multiple inventory categories')
                    identifiers.add(str(item['id']))
                    response = fetch(DETAIL, {'iddoc': item['id'], 'idp': '0', 'lang': 'gl_ES', 'token': token})
                    save(f'detail-{item["id"]}.json', response)
                    rows.append(parse_instrument(item, response.json(), category))
            if not rows:
                raise ValueError('No usable planning instruments')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'category_counts': counts,
                'coverage': 'SIOTUGA municipal planning inventory including explicit historical entries',
                'source_urls': [INVENTORY, QUERY, DETAIL], 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Refresh full inventory to detect changes to attachments and legal incidents.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
