"""Salceda's general/development planning inventory on the official SIOTUGA portal."""
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
SOURCE = BASE + 'inventario.php?inv=1&idconcello=36049'
CLASSES = (14, 13, 18)  # general, development, rural settlement boundaries
FIGURES = {'Normas Subsidiarias de Planeamento', 'Modificación Puntual',
           'Modificación puntual', 'Plan Parcial', 'Plan Especial', 'Estudio de Detalle'}


def source_date(value):
    if value in (None, ''):
        return None
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload):
    """The website consumes a complete JSON array, then paginates in DataTables."""
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Expected complete inventory array; pagination/schema changed')
    result = {}
    for item in payload:
        if not isinstance(item, dict) or not re.fullmatch(r'\d+', str(item.get('id', ''))):
            raise ValueError('Invalid inventory identity')
        if item.get('figura') not in FIGURES or not str(item.get('docnome') or '').strip():
            raise ValueError('Unreviewed planning figure or missing instrument title')
        for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
            source_date(item.get(field))
        key = str(item['id'])
        if key in result and item != result[key]:
            raise ValueError('Conflicting instrument identity')
        result[key] = item
    return list(result.values())


def parse_project(item, detail, inventory_class):
    general = detail.get('datos_xerais', {}) if isinstance(detail, dict) else {}
    if (str(general.get('id')) != str(item['id']) or
            general.get('menutitle') != 'Salceda de Caselas' or
            general.get('folder') != 'SALCEDADECASELAS' or
            general.get('figura') != item['figura'] or
            str(general.get('denominacion', '')).strip() != item['docnome'].strip()):
        raise ValueError('Detail does not match Salceda instrument')
    for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
        if general.get(field) != item.get(field):
            raise ValueError('Inventory/detail date conflict')
    root = urljoin(BASE, general['filesroot'] + general['folder'] + '/documents/')
    if root != BASE + 'documentos/urbanismo/SALCEDADECASELAS/documents/':
        raise ValueError('Unexpected document root')
    docs = {}
    elements = detail.get('elementos')
    if elements is not None and not isinstance(elements, list):
        raise ValueError('Unexpected document groups')
    for group in elements or []:
        for component in group['componentes']:
            filename = component['pathesperado']
            if not re.fullmatch(r'[\w.-]+\.(?:pdf|jpg|jpeg|png)', filename, re.I):
                raise ValueError('Unexpected source document path')
            url = urljoin(root, filename)
            docs[url] = {'titulo': component['descripcion'], 'url': url,
                         'grupo': group['description'], 'source_id': component['id']}
    return {
        'id': 'salceda-de-caselas-siotuga-' + str(item['id']),
        'municipio': 'Salceda de Caselas', 'codigo_ine': '36049', 'provincia': 'Pontevedra',
        'titulo': item['figura'] + ' — ' + item['docnome'].strip(),
        'tipo': item['figura'], 'fecha': None,
        'fecha_aprob': source_date(item.get('fechaaddef')),
        'fecha_publicacion': None,
        'fecha_publicacion_bop': source_date(item.get('fechabop')),
        'fecha_publicacion_dog': source_date(item.get('fechadog')),
        'fecha_publicacion_normativa_bop': source_date(item.get('fechanormativabop')),
        'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'siotuga_inventario_municipal',
        'organismo_fuente': 'Xunta de Galicia — SIOTUGA',
        'siotuga_id': str(item['id']), 'inventario_clase': inventory_class,
        'procedencia': {'inventario': BASE + 'assets/inventario/query_document.php',
                        'parametros_inventario': {'id': '36049', 'idclase': inventory_class},
                        'detalle': BASE + 'assets/inventario/getIOTPU.php',
                        'parametros_detalle': {'iddoc': str(item['id']), 'idp': 0, 'lang': 'gl_ES'}},
        'incidencias_juridicas_inventario': item.get('incidencias_iuris'),
        'incidencias_juridicas_detalle': detail.get('incidencias_iuris'),
        'documentos': list(docs.values()),
        'cobertura_documental': 'adjuntos_enlazados' if docs else 'ficha_sin_adjuntos',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
    }


class SalcedaDeCaselasAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('capture_dir')
        def capture(name, content):
            if captures:
                directory = Path(captures)
                directory.mkdir(parents=True, exist_ok=True)
                (directory / name).write_text(content, encoding='utf-8')

        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-salceda-planning/1.0'
            response = session.get(SOURCE, timeout=35)
            response.raise_for_status()
            response.encoding = 'utf-8'
            if urlparse(response.url).hostname != 'siotuga.xunta.gal':
                raise ValueError('Unexpected inventory redirect')
            soup = BeautifulSoup(response.text, 'html.parser')
            option = soup.select_one('option[value="36049"]')
            token = soup.select_one('#token')
            if not option or option.get_text(strip=True) != 'Salceda de Caselas' or not token:
                raise ValueError('Missing municipal public search form')
            capture('live-inventory.html', response.text)
            # Public form CSRF value, obtained anonymously, never an account credential.
            def post(endpoint, params, filename):
                r = session.post(BASE + 'assets/inventario/' + endpoint,
                                 data={**params, 'token': token['value']}, timeout=35)
                r.raise_for_status()
                payload = r.json()
                capture(filename, json.dumps(payload, ensure_ascii=False, indent=2))
                return payload

            inventory = {}
            for category in CLASSES:
                payload = post('query_document.php', {'id': '36049', 'idclase': category},
                               f'live-inventory-{category}.json')
                for item in parse_inventory(payload):
                    key = str(item['id'])
                    if key in inventory:
                        raise ValueError('Instrument repeated across inventory classes')
                    inventory[key] = (item, category)
            if not inventory:
                raise ValueError('No usable planning instruments')
            rows = []
            for key, (item, category) in inventory.items():
                detail = post('getIOTPU.php', {'iddoc': key, 'idp': 0, 'lang': 'gl_ES'},
                              f'live-detail-{key}.json')
                rows.append(parse_project(item, detail, category))
        return {**self._write(out_jsonl, rows), 'source': SOURCE}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
