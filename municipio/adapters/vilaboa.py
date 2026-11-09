"""Vilaboa's approved planning inventory in the official Xunta SIOTUGA register."""
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
INVENTORY = BASE + 'inventario.php?inv=1&idconcello=36058'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
# These are whole JSON arrays, paginated only client-side by DataTables.
CLASSES = {'14': 'planeamento_xeral', '13': 'planeamento_desenvolvemento',
           '18': 'delimitacion_nucleo_rural'}
DATE_FIELDS = {'fechaaddef': 'fecha_aprob', 'fechadog': 'fecha_publicacion_dog',
               'fechabop': 'fecha_publicacion_bop',
               'fechanormativabop': 'fecha_publicacion_normativa_bop',
               'fechatextodef': 'fecha_texto_refundido'}


def dates(raw):
    result = {}
    for source, target in DATE_FIELDS.items():
        value = raw.get(source)
        if value:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError('Unexpected date precision: ' + str(value))
            result[target] = date.fromisoformat(value).isoformat()
    return result


def parse_inventory(payload):
    if payload is None:
        return []  # The documented empty-result representation.
    if not isinstance(payload, list):
        raise ValueError('Expected complete inventory array; pagination/schema changed')
    rows = {}
    for row in payload:
        if not isinstance(row, dict) or not str(row.get('id', '')).isdigit():
            raise ValueError('Invalid SIOTUGA document identity')
        if not row.get('docnome') or not row.get('figura'):
            raise ValueError('Missing planning title/figure')
        dates(row)
        key = str(row['id'])
        if key in rows and rows[key] != row:
            raise ValueError('Conflicting duplicate document')
        rows[key] = row
    return list(rows.values())


def parse_detail(payload, inventory_row, inventory_class):
    if not isinstance(payload, dict):
        raise ValueError('Missing planning detail')
    general = payload.get('datos_xerais', {})
    source_id = str(inventory_row['id'])
    if (str(general.get('id')) != source_id or general.get('menutitle') != 'Vilaboa'
            or general.get('folder') != 'VILABOA'
            or general.get('filesroot') != 'documentos/urbanismo/'):
        raise ValueError('Detail identity/municipality/document root mismatch')
    if general.get('denominacion', '').strip() != inventory_row['docnome'].strip():
        raise ValueError('Detail title changed during extraction')
    if general.get('figura') != inventory_row['figura']:
        raise ValueError('Detail figure mismatch')
    for name in DATE_FIELDS:
        if name in inventory_row and inventory_row[name] != general.get(name):
            raise ValueError('Detail date mismatch: ' + name)
    documents = {}
    for section in payload.get('elementos') or []:
        for component in section.get('componentes') or []:
            filename = component.get('pathesperado', '')
            if not re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:pdf|jpg|jpeg|png)', filename, re.I):
                raise ValueError('Unexpected document path')
            url = urljoin(BASE, general['filesroot'] + 'VILABOA/documents/' + filename)
            documents[url] = {'url': url, 'titulo': component.get('descripcion'),
                              'seccion': section.get('description'), 'siotuga_id': source_id,
                              'component_id': component.get('id')}
    if not documents:
        raise ValueError('Planning package has no documents')
    return {'siotuga_id': source_id, 'titulo': general['denominacion'].strip(),
            'figura': general['figura'], 'inventory_class': inventory_class,
            **dates(general), 'incidencias_juridicas': payload.get('incidencias_iuris'),
            'provenance': {'url': DETAIL, 'method': 'POST',
                           'parameters': {'iddoc': source_id, 'idp': '0', 'lang': 'es_ES'}},
            'documentos': list(documents.values())}


def group_instruments(versions):
    grouped = {}
    for version in versions:
        # Two partial approvals are document versions of the same municipal PXOM.
        # Modifications and all other figures remain distinct instruments.
        key = 'pxom' if version['figura'] == 'Plan Xeral de Ordenación Municipal' else version['siotuga_id']
        grouped.setdefault(key, []).append(version)
    records = []
    for key, packages in sorted(grouped.items()):
        packages = sorted(packages, key=lambda p: (p.get('fecha_aprob', ''), p['siotuga_id']))
        docs = {d['url']: d for p in packages for d in p['documentos']}
        records.append({'id': 'vilaboa-siotuga-' + key, 'municipio': 'Vilaboa',
                        'codigo_ine': '36058', 'provincia': 'Pontevedra',
                        'titulo': packages[0]['titulo'], 'tipo': 'planeamiento_urbanistico',
                        'figura': packages[0]['figura'], 'url': INVENTORY,
                        'source': 'siotuga_xunta', 'organismo_fuente': 'Xunta de Galicia',
                        'origen': 'inventario_municipal_planeamiento_aprobado',
                        'siotuga_ids': [p['siotuga_id'] for p in packages],
                        'versiones': packages, 'documentos': list(docs.values()),
                        'geometry_status': 'unavailable', 'publication_ready': False,
                        'coverage': 'approved_planning_inventory_classes_14_13_18',
                        **(dates_from_version(packages[0]) if len(packages) == 1 else {})})
    return records


def dates_from_version(version):
    return {key: version[key] for key in DATE_FIELDS.values() if key in version}


class VilaboaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, *, data=None, capture):
        response = session.request('POST' if data is not None else 'GET', url,
                                   data=data, timeout=35)
        response.raise_for_status()
        if urlparse(response.url).hostname != 'siotuga.xunta.gal':
            raise ValueError('Unexpected official-source redirect')
        payload = response.json()
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir']) / capture
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return payload

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'publication_ready': False}

    def backfill_proyectos(self, out_jsonl):
        versions = {}
        counts = {}
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipal-planning-inventory/1.0'
            response = session.get(INVENTORY, timeout=35)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            selected = soup.select_one('#idconcello option[value="36058"]')
            token = soup.select_one('#token')
            if not selected or selected.get_text(strip=True) != 'Vilaboa' or not token:
                raise ValueError('SIOTUGA inventory form missing')
            # Public anonymous form nonce, never persisted in evidence or records.
            for code, label in CLASSES.items():
                payload = self._fetch(session, QUERY, data={'id': '36058', 'idclase': code,
                                      'token': token['value']}, capture='class-' + code + '.json')
                rows = parse_inventory(payload)
                counts[code] = len(rows)
                for row in rows:
                    if str(row['id']) in versions:
                        raise ValueError('Document unexpectedly appears in multiple classes')
                    detail = self._fetch(session, DETAIL, data={'iddoc': row['id'], 'idp': '0',
                                         'lang': 'es_ES', 'token': token['value']},
                                         capture='detail-' + str(row['id']) + '.json')
                    versions[str(row['id'])] = parse_detail(detail, row, label)
        if not versions:
            raise ValueError('Empty approved inventory; review source before replacing snapshot')
        records = group_instruments(list(versions.values()))
        return {**self._write(out_jsonl, records), 'inventory_counts': counts,
                'source_urls': [INVENTORY, QUERY, DETAIL]}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
