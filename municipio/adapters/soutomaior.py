"""Soutomaior planning inventory delegated by the municipal Urbanismo page."""
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
MUNICIPAL = 'https://soutomaior.gal/urbanismo/'
INVENTORY = ROOT + 'inventario.php?inv=1&idconcello=36053'
QUERY = ROOT + 'assets/inventario/query_document.php'
DETAIL = ROOT + 'assets/inventario/getIOTPU.php'
CLASSES = {14: 'planeamento_xeral', 13: 'planeamento_desenvolvemento',
           16: 'planeamento_historico', 18: 'delimitacion_nucleos_rurais'}


def source_date(value):
    if value in (None, ''):
        return None
    return date.fromisoformat(value).isoformat()


class SoutomaiorAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(payload, category):
        # The site's DataTables paginates locally over the complete JSON array.
        # Never accept a new paginated envelope as a complete response.
        if payload is None:
            return []
        if not isinstance(payload, list):
            raise ValueError('Expected complete inventory array, not pagination envelope')
        rows = {}
        for item in payload:
            if not isinstance(item, dict) or not re.fullmatch(r'\d+', str(item.get('id', ''))):
                raise ValueError('Invalid planning identifier')
            if not item.get('docnome') or not item.get('figura'):
                raise ValueError('Missing planning title or figure')
            key = str(item['id'])
            if key in rows and rows[key] != item:
                raise ValueError('Conflicting planning identifier')
            rows[key] = item
        return [dict(item, inventory_class=category) for item in rows.values()]

    @staticmethod
    def parse_project(item, detail):
        if not isinstance(detail, dict) or not isinstance(detail.get('datos_xerais'), dict):
            raise ValueError('Missing planning detail')
        general = detail['datos_xerais']
        if (str(general.get('id')) != str(item['id'])
                or general.get('menutitle', '').strip().casefold() != 'soutomaior'
                or general.get('folder') != 'SOUTOMAIOR'):
            raise ValueError('Detail identity/municipality mismatch')
        for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
            if source_date(item.get(field)) != source_date(general.get(field)):
                raise ValueError('Inventory/detail date mismatch')
        docs = {}
        groups = detail.get('elementos')
        if groups is not None and not isinstance(groups, list):
            raise ValueError('Invalid document inventory')
        for group in groups or []:
            for component in group['componentes']:
                filename = component['pathesperado']
                if not re.fullmatch(r'[\w.\-]+', filename):
                    raise ValueError('Unexpected document path')
                url = urljoin(ROOT, general['filesroot'] + general['folder'] + '/documents/' + filename)
                if urlparse(url).hostname != 'siotuga.xunta.gal':
                    raise ValueError('Unexpected document host')
                docs.setdefault(url, {'id': str(component['id']), 'titulo': component['descripcion'],
                                     'grupo': group['description'], 'url': url})
        if groups is not None and not docs:
            raise ValueError('Empty document groups; review source')
        return {
            'id': 'soutomaior-proy-' + str(item['id']), 'siotuga_id': str(item['id']),
            'municipio': 'Soutomaior', 'codigo_ine': '36053', 'provincia': 'Pontevedra',
            'titulo': item['docnome'].strip(), 'tipo': item['figura'],
            'fase': 'aprobación definitiva', 'fecha': None,
            'fecha_aprob': source_date(item.get('fechaaddef')),
            'fecha_publicacion': None,
            'fecha_publicacion_dog': source_date(item.get('fechadog')),
            'fecha_publicacion_bop': source_date(item.get('fechabop')),
            'fecha_publicacion_normativa_bop': source_date(item.get('fechanormativabop')),
            'incidencias_juridicas': detail.get('incidencias_iuris'),
            'incidencias_juridicas_inventario': item.get('incidencias_iuris'),
            'categoria_inventario': CLASSES[item['inventory_class']],
            'vigencia': 'histórico según inventario' if item['inventory_class'] == 16 else 'no inferida',
            'url': INVENTORY, 'url_documento': next(iter(docs), None),
            'documentos_status': 'enlazados' if docs else 'no disponibles en la ficha SIOTUGA',
            'documentos': list(docs.values()), 'source': 'ayuntamiento',
            'organismo_fuente': 'Xunta de Galicia — SIOTUGA', 'url_referencia_municipal': MUNICIPAL,
            'provenance': {'inventory_endpoint': QUERY, 'inventory_parameters': {'id': '36053', 'idclase': item['inventory_class']},
                           'detail_endpoint': DETAIL, 'detail_parameters': {'iddoc': str(item['id']), 'idp': '0', 'lang': 'gl_ES'}},
            'origen': 'inventario_planeamiento_siotuga', 'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        capture = self.config.get('capture_dir')
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-soutomaior/1.0'

            def fetch(url, name, data=None):
                time.sleep(.2)
                response = session.get(url, timeout=40) if data is None else session.post(url, data=data, timeout=40)
                response.raise_for_status()
                response.encoding = 'utf-8'
                source_urls.append(url)
                if capture:
                    folder = Path(capture)
                    folder.mkdir(parents=True, exist_ok=True)
                    # Public page nonce is used in memory only; do not archive it.
                    content = re.sub(r'(<input[^>]*id="token"[^>]*value=")[^"]*', r'\1', response.text)
                    (folder / name).write_text(content, encoding='utf-8')
                return response

            municipal = BeautifulSoup(fetch(MUNICIPAL, 'municipal-live.html').text, 'html.parser')
            if not any(a['href'].replace('http:', 'https:') == INVENTORY for a in municipal.select('a[href]')):
                raise ValueError('Municipal delegation to SIOTUGA changed')
            soup = BeautifulSoup(fetch(INVENTORY, 'inventory-live.html').text, 'html.parser')
            nonce = soup.select_one('#token')
            if not nonce or not nonce.get('value'):
                raise ValueError('Missing public inventory form nonce')
            common = {'token': nonce['value']}
            inventory = {}
            for category in CLASSES:
                payload = fetch(QUERY, f'class-{category}.json', dict(common, id='36053', idclase=category)).json()
                for item in self.parse_inventory(payload, category):
                    if item['id'] in inventory:
                        raise ValueError('Instrument occurs in multiple inventory classes; review grouping')
                    inventory[item['id']] = item
            if not inventory:
                raise ValueError('No usable planning instruments')
            rows = []
            for item in inventory.values():
                detail = fetch(DETAIL, f"detail-{item['id']}.json", dict(common, iddoc=item['id'], idp='0', lang='gl_ES')).json()
                rows.append(self.parse_project(item, detail))
        result = self._write(out_jsonl, rows)
        return dict(result, source_urls=list(dict.fromkeys(source_urls)), coverage='partial: urban planning inventory classes 14,13,16,18; territorial instruments excluded')

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
