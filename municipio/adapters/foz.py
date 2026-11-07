"""Foz planning inventory delegated by the municipality to Xunta SIOTUGA."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
INVENTORY = BASE + 'inventario.php?inv=1&idconcello=27019'
MUNICIPAL = 'https://concellodefoz.gal/urbanismo/normativa/'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
DATE_FIELDS = ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop')


def parse_inventory(payload):
    """The public UI receives a complete JSON array, then paginates client-side."""
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Expected full inventory array; pagination/envelope needs review')
    rows = {}
    for item in payload:
        if not isinstance(item, dict) or not str(item.get('id', '')).isdigit():
            raise ValueError('Invalid SIOTUGA instrument')
        if not item.get('docnome') or not item.get('figura'):
            raise ValueError('Missing instrument title/type')
        for field in DATE_FIELDS:
            if item.get(field):
                date.fromisoformat(item[field])
        key = str(item['id'])
        if key in rows and rows[key] != item:
            raise ValueError('Conflicting duplicate instrument')
        rows[key] = item
    return list(rows.values())


def parse_detail(payload, instrument_id):
    if not isinstance(payload, dict):
        raise ValueError('Missing instrument detail')
    general = payload['datos_xerais']
    if str(general['id']) != str(instrument_id) or general['folder'] != 'FOZ':
        raise ValueError('Detail belongs to another instrument/municipality')
    root = urljoin(BASE, general['filesroot'] + general['folder'] + '/documents/')
    if urlparse(root).hostname != 'siotuga.xunta.gal':
        raise ValueError('Unexpected document host')
    docs = {}
    if payload['elementos'] is None:
        return []  # Official ficha exists but its document inventory is unavailable.
    for group in payload['elementos']:
        for component in group['componentes']:
            filename = component['pathesperado']
            if not filename or '/' in filename or '\\' in filename or filename in {'.', '..'}:
                raise ValueError('Unexpected document path')
            url = root + quote(filename)
            docs[url] = {'titulo': component['descripcion'].strip(), 'url': url,
                         'grupo': group['description'].strip(),
                         'source_document_id': str(instrument_id), 'provenance_url': DETAIL}
    if not docs:
        raise ValueError('Instrument without linked source documents')
    return list(docs.values())


def build_records(instruments, details):
    records = {}
    for item in instruments:
        doc_id = str(item['id'])
        # Two official document packages describe the same PXOM, not two projects.
        key = 'pxom' if doc_id in {'28131', '28708'} else doc_id
        row = records.setdefault(key, {
            'id': 'foz-plan-' + key, 'municipio': 'Foz', 'codigo_ine': '27019',
            'provincia': 'Lugo', 'titulo': ('Plan Xeral de Ordenación Municipal de Foz'
                                         if key == 'pxom' else item['docnome'].strip()),
            'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
            'organismo_fuente': 'Xunta de Galicia — SIOTUGA',
            'origen': 'inventario_planeamiento', 'url': INVENTORY,
            'municipal_source_url': MUNICIPAL, 'documentos': [], 'expedientes_fuente': [],
            'geometry_status': 'unavailable', 'publication_ready': False,
            'coverage': 'inventario SIOTUGA: planeamiento general y desarrollo; vigencia individual no verificada',
        })
        dates = {f: item.get(f) for f in DATE_FIELDS}
        entry = {'id': doc_id, 'titulo': item['docnome'].strip(), 'figura': item['figura'],
                 'source_url': QUERY, 'query': {'id': '27019', 'idclase': item['inventory_class']},
                 'detail_url': DETAIL, 'detail_query': {'iddoc': doc_id, 'idp': '0', 'lang': 'gl_ES'},
                 'fechas_fuente': dates, 'incidencias_iuris': item.get('incidencias_iuris')}
        # 28708's field is the resolution date according to the linked document
        # label; the approval order is a different act. Keep raw provenance only.
        if doc_id == '28708':
            entry['date_warning'] = 'fechaaddef 2025-04-21 corresponde a resolución; no se interpreta como fecha de aprobación de la orden'
        elif dates['fechaaddef']:
            entry['fecha_aprob'] = dates['fechaaddef']
        if dates['fechadog']:
            entry['fecha_publicacion_dog'] = dates['fechadog']
        if dates['fechabop']:
            entry['fecha_publicacion_bop'] = dates['fechabop']
        if dates['fechaaddef'] and any(dates[f] and dates[f] < dates['fechaaddef'] for f in ('fechabop', 'fechadog')):
            entry['chronology_warning'] = 'Publicación anterior a fechaaddef en SIOTUGA; fechas no corregidas ni inferidas'
        entry['documents_status'] = 'linked' if details[doc_id] else 'unavailable_in_source'
        row['expedientes_fuente'].append(entry)
        row['documentos'].extend(details[doc_id])
    for row in records.values():
        row['documentos'] = list({d['url']: d for d in row['documentos']}.values())
    if not records:
        raise ValueError('No usable Foz planning instruments')
    return list(records.values())


class FozAyuntamientoAdapter(AyuntamientoAdapter):
    def _capture(self, name, payload):
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir']) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)
        return {'rows': len(rows), 'status': 'ok'}

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; FozMunicipalInventory/1.0)'
            response = session.get(INVENTORY, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            selected = soup.select_one('option[value="27019"]')
            if not selected or selected.get_text(strip=True) != 'Foz':
                raise ValueError('Municipal inventory identity changed')
            # Public anti-CSRF form value; never persist it in evidence/output.
            form_value = soup.select_one('#token')['value']
            instruments = []
            for category in (14, 13):
                response = session.post(QUERY, data={'id': '27019', 'idclase': category,
                                                    'token': form_value}, timeout=30)
                response.raise_for_status()
                payload = response.json()
                self._capture(f'inventory-{category}.json', payload)
                instruments.extend({**r, 'inventory_class': category} for r in parse_inventory(payload))
            details = {}
            for item in instruments:
                doc_id = str(item['id'])
                response = session.post(DETAIL, data={'iddoc': doc_id, 'idp': '0',
                                                      'lang': 'gl_ES', 'token': form_value}, timeout=30)
                response.raise_for_status()
                payload = response.json()
                self._capture(f'detail-{doc_id}.json', payload)
                details[doc_id] = parse_detail(payload, doc_id)
            rows = build_records(instruments, details)
        return {**self._write(out_jsonl, rows), 'source_urls': [MUNICIPAL, INVENTORY, QUERY, DETAIL],
                'source_packages': len(instruments), 'coverage': 'general_and_development_inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
