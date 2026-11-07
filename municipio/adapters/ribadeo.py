"""Ribadeo planning inventory, served by the municipal-linked Xunta SIOTUGA."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = BASE + 'inventario?idconcello=27051&inv=1'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
# Verified in the correction's signed memoria: correction no. 1 of the 2014 PXOM.
CORRECTIONS = {'28691': '27886'}


def source_date(value):
    if value in (None, ''):
        return None
    return date.fromisoformat(value).isoformat()


def dates(data):
    return {
        'fecha_aprob': source_date(data.get('fechaaddef')),
        'fecha_publicacion_dog': source_date(data.get('fechadog')),
        'fecha_publicacion_bop': source_date(data.get('fechabop')),
        'fecha_publicacion_normativa_bop': source_date(data.get('fechanormativabop')),
    }


class RibadeoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(payload):
        # The site's JS retrieves a complete array then paginates in DataTables.
        # An envelope/pagination protocol change must fail, never truncate it.
        if payload is None:
            return []
        if not isinstance(payload, list):
            raise ValueError('Expected complete SIOTUGA inventory array')
        unique = {}
        for item in payload:
            if not isinstance(item, dict) or not str(item.get('id', '')).isdigit() or not item.get('docnome') or not item.get('figura'):
                raise ValueError('Invalid planning inventory row')
            key = str(item['id'])
            if key in unique and unique[key] != item:
                raise ValueError('Conflicting inventory identifier')
            unique[key] = item
        return list(unique.values())

    @staticmethod
    def parse_detail(item, detail):
        if not isinstance(detail, dict):
            raise ValueError('Missing planning detail')
        data = detail.get('datos_xerais', {})
        if str(data.get('id')) != str(item['id']):
            raise ValueError('Detail identifier mismatch')
        if data.get('menutitle') != 'Ribadeo' or data.get('folder') != 'RIBADEO':
            raise ValueError('Detail municipality mismatch')
        for field in ('denominacion', 'figura'):
            expected = item['docnome' if field == 'denominacion' else 'figura']
            if data.get(field) != expected:
                raise ValueError('Detail title/type mismatch')
        if dates(data) != dates(item):
            raise ValueError('Inventory/detail dates disagree')
        docs = {}
        for group in detail.get('elementos') or []:
            for component in group.get('componentes') or []:
                url = urljoin(BASE, data['filesroot'] + data['folder'] + '/documents/' + component['pathesperado'])
                if urlparse(url).hostname != 'siotuga.xunta.gal' or '/urbanismo/RIBADEO/documents/' not in urlparse(url).path:
                    raise ValueError('Unexpected document location')
                docs[url] = {'titulo': component['descripcion'].strip(), 'url': url,
                             'grupo': group['description'].strip(), 'siotuga_id': str(item['id'])}
        return {
            'id': 'ribadeo-proy-' + str(item['id']), 'siotuga_id': str(item['id']),
            'municipio': 'Ribadeo', 'codigo_ine': '27051', 'provincia': 'Lugo',
            'titulo': item['docnome'], 'tipo': item['figura'],
            'fase': 'aprobación definitiva (según inventario SIOTUGA)',
            'fecha': None, **dates(data),
            'url': SOURCE, 'url_ficha': DETAIL + '?' + urlencode({'iddoc': item['id'], 'idp': 0, 'lang': 'gl_ES'}),
            'source': 'ayuntamiento', 'organismo_fuente': 'Xunta de Galicia — SIOTUGA',
            'origen': 'inventario_planeamiento_municipal',
            'incidencias_iuris': item.get('incidencias_iuris'),
            'documentos': list(docs.values()), 'correcciones': [],
            'documentacion_disponible': bool(docs),
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }

    @staticmethod
    def group_instruments(rows):
        grouped = {row['siotuga_id']: row for row in rows}
        for key, row in list(grouped.items()):
            if row['titulo'].startswith('CE '):
                parent = CORRECTIONS.get(key)
                if parent not in grouped:
                    raise ValueError('Unreviewed correction or missing parent instrument')
                original = grouped[parent]
                original['correcciones'].append({k: row[k] for k in (
                    'siotuga_id', 'titulo', 'url_ficha', 'fecha_aprob',
                    'fecha_publicacion_dog', 'fecha_publicacion_bop',
                    'fecha_publicacion_normativa_bop')})
                original['documentos'].extend(row['documentos'])
                original['documentacion_disponible'] = bool(original['documentos'])
                del grouped[key]
        return list(grouped.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('capture_dir')
        def capture(name, payload):
            if captures:
                folder = Path(captures)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

        excluded, rows, urls = [], [], [SOURCE]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-ribadeo/1.0'
            response = session.get(SOURCE, timeout=35)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            if not soup.select_one('option[value="27051"]'):
                raise ValueError('Ribadeo municipality absent from inventory')
            # Anonymous anti-CSRF field generated by the public search page.
            token = soup.select_one('#token')
            if token is None:
                raise ValueError('Public inventory form changed')
            for category in (14, 13):
                response = session.post(QUERY, data={'id': '27051', 'idclase': category, 'token': token['value']}, timeout=35)
                response.raise_for_status()
                payload = response.json()
                capture(f'inventory-{category}.json', payload)
                urls.append(QUERY + '?' + urlencode({'id': '27051', 'idclase': category}))
                for item in self.parse_inventory(payload):
                    response = session.post(DETAIL, data={'iddoc': item['id'], 'idp': 0, 'lang': 'gl_ES', 'token': token['value']}, timeout=35)
                    response.raise_for_status()
                    detail = response.json()
                    capture('detail-' + str(item['id']) + '.json', detail)
                    try:
                        row = self.parse_detail(item, detail)
                    except ValueError as exc:
                        if str(exc) != 'Detail municipality mismatch':
                            raise
                        excluded.append({'siotuga_id': item['id'], 'reason': str(exc)})
                        continue
                    rows.append(row)
                    urls.append(row['url_ficha'])
        if not rows:
            raise ValueError('No usable Ribadeo planning instruments')
        rows = self.group_instruments(rows)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': urls,
                'excluded': excluded, 'coverage': 'Current general and development planning inventories only',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
