"""Gondomar planning instruments from the official Xunta SIOTUGA inventory.

The browser's query_document endpoint returns the whole category as a JSON array;
DataTables paginates that array locally. No page-size or historic-news cutoff.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = BASE + 'inventario?inv=1&idconcello=36021&lang=es_ES'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
CLASSES = {13: 'planeamiento_de_desarrollo', 18: 'delimitacion_nucleo_rural'}
LIMITATIONS = [
    'Cobertura parcial: solo planeamiento de desarrollo y delimitaciones de núcleo rural de SIOTUGA (clases 13 y 18).',
    'Excluye planeamiento histórico/anulado, instrumentos territoriales supramunicipales, noticias y contratación.',
    'La web municipal devuelve HTTP 403 al cliente; no se extraen sus anuncios ni obras.',
    'La presencia en el inventario no prueba vigencia jurídica; se conservan incidencias y fechas nulas.',
    'Algunos instrumentos tienen metadatos pero no documentos expuestos por SIOTUGA.',
    'Sin registro de licencias concedidas ni geometría vectorial verificada; no se infieren coordenadas.',
]


def source_date(value):
    if value in (None, ''):
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError(f'Unrecognized source date: {value!r}')
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload):
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Expected complete inventory array; pagination/schema changed')
    rows = {}
    for item in payload:
        if not isinstance(item, dict) or not str(item.get('id', '')).isdigit():
            raise ValueError('Missing SIOTUGA instrument identifier')
        key = str(item['id'])
        if not item.get('docnome') or not item.get('figura'):
            raise ValueError('Missing instrument title/type')
        if key in rows and rows[key] != item:
            raise ValueError('Conflicting duplicate instrument')
        rows[key] = item
    return list(rows.values())


def parse_instrument(item, detail, category):
    if not isinstance(detail, dict) or not isinstance(detail.get('datos_xerais'), dict):
        raise ValueError('Missing instrument detail')
    general = detail['datos_xerais']
    identifier = str(item['id'])
    if (str(general.get('id')) != identifier or general.get('menutitle') != 'Gondomar'
            or general.get('folder') != 'GONDOMAR'):
        raise ValueError('Instrument identity/municipality mismatch')
    if general.get('denominacion') != item['docnome'] or general.get('figura') != item['figura']:
        raise ValueError('Inventory/detail disagreement')
    dates = {}
    for source, target in [('fechaaddef', 'fecha_aprob'), ('fechabop', 'fecha_publicacion_bop'),
                           ('fechadog', 'fecha_publicacion_dog'),
                           ('fechanormativabop', 'fecha_publicacion_normativa_bop')]:
        if general.get(source) != item.get(source):
            raise ValueError('Inventory/detail date disagreement')
        dates[target] = source_date(general.get(source))
    root = urljoin(BASE, general.get('filesroot', '') + general['folder'] + '/documents/')
    if root != BASE + 'documentos/urbanismo/GONDOMAR/documents/':
        raise ValueError('Unexpected document provenance')
    documents = {}
    groups = detail.get('elementos')
    if 'elementos' not in detail or (groups is not None and not isinstance(groups, list)):
        raise ValueError('Invalid document groups')
    for group in groups or []:
        for component in group['componentes']:
            filename = component['pathesperado']
            if not re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:pdf|jpg|png|zip)', filename, re.I):
                raise ValueError('Unexpected document filename')
            url = urljoin(root, filename)
            documents.setdefault(url, {'id_origen': component['id'],
                'titulo': component['descripcion'].strip(), 'grupo': group['description'].strip(), 'url': url})
    return {
        'id': 'gondomar-siotuga-' + identifier, 'id_origen': identifier,
        'municipio': 'Gondomar', 'codigo_ine': '36021', 'provincia': 'Pontevedra',
        'titulo': item['docnome'].strip(), 'tipo': item['figura'], 'categoria_inventario': category,
        'fecha': None, **dates,
        'url': SOURCE, 'source': 'xunta_siotuga', 'source_dataset': QUERY,
        'origen': 'inventario_municipal_planeamiento',
        'procedencia': {'inventario_url': SOURCE, 'consulta_url': QUERY,
                       'consulta_parametros': {'id': '36021', 'idclase': next(k for k,v in CLASSES.items() if v == category)},
                       'detalle_url': DETAIL, 'detalle_parametros': {'iddoc': identifier, 'idp': 0, 'lang': 'es_ES'}},
        'incidencias_juridicas_inventario': item.get('incidencias_iuris'),
        'incidencias_juridicas_detalle': detail.get('incidencias_iuris'),
        'documentos': list(documents.values()),
        'documentos_status': 'available' if documents else 'not_exposed_by_source', 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class GondomarAyuntamientoAdapter(AyuntamientoAdapter):
    def _capture(self, name, response):
        if self.config.get('evidence_dir'):
            path = Path(self.config['evidence_dir'])
            path.mkdir(parents=True, exist_ok=True)
            (path / name).write_bytes(response.content)

    @staticmethod
    def _write(path, rows, status='ok'):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)
        return {'status': status, 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        urls = [SOURCE, QUERY, DETAIL]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-gondomar/1.0'
            response = session.get(SOURCE, timeout=35)
            response.raise_for_status()
            self._capture('inventario.html', response)
            soup = BeautifulSoup(response.content, 'html.parser')
            option = soup.select_one('#idconcello option[value="36021"]')
            token = soup.select_one('input#token')
            if not option or option.get_text(strip=True) != 'Gondomar' or not token or not token.get('value'):
                raise ValueError('SIOTUGA inventory identity/token missing')
            rows, seen = [], set()
            for class_id, category in CLASSES.items():
                response = session.post(QUERY, data={'id': '36021', 'idclase': class_id, 'token': token['value']}, timeout=35)
                response.raise_for_status()
                self._capture(f'class-{class_id}.json', response)
                for item in parse_inventory(response.json()):
                    if item['id'] in seen:
                        raise ValueError('Instrument appears in multiple categories; review grouping')
                    seen.add(item['id'])
                    response = session.post(DETAIL, data={'iddoc': item['id'], 'idp': 0,
                        'lang': 'es_ES', 'token': token['value']}, timeout=35)
                    response.raise_for_status()
                    self._capture(f'detail-{item["id"]}.json', response)
                    rows.append(parse_instrument(item, response.json(), category))
        if not rows:
            raise ValueError('No usable Gondomar instruments; source review required')
        return {**self._write(out_jsonl, rows), 'source_urls': urls, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot, including every item in both source arrays.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return self._write(out_jsonl, [], status='disabled')

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
