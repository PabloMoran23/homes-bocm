"""Noia planning inventory in Xunta's official SIOTUGA (not a licence feed)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = BASE + 'inventario?inv=1&idconcello=15057&lang=es_ES'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
CLASSES = (14, 13)  # general (including modifications), development; no historic plans


def source_date(value):
    if value in (None, ''):
        return None
    return date.fromisoformat(value).isoformat()


class NoiaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(payload):
        # The web UI receives a complete JSON array and paginates client-side.
        # Never accept a new paginated envelope as if it were a complete array.
        if payload is None:
            return []
        if not isinstance(payload, list):
            raise ValueError('Expected complete SIOTUGA array; pagination/schema changed')
        found = {}
        for item in payload:
            if not isinstance(item, dict) or not str(item.get('id', '')).isdigit():
                raise ValueError('Invalid SIOTUGA instrument ID')
            if not item.get('docnome', '').strip() or not item.get('figura'):
                raise ValueError('Missing instrument title/type')
            for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
                source_date(item.get(field))
            key = str(item['id'])
            if key in found and found[key] != item:
                raise ValueError('Conflicting duplicate instrument')
            found[key] = item
        return list(found.values())

    @staticmethod
    def parse_project(item, detail, category):
        general = detail['datos_xerais']
        if (str(general['id']) != str(item['id']) or general['menutitle'] != 'Noia'
                or general['folder'] != 'NOIA'):
            raise ValueError('Detail belongs to a different instrument/municipality')
        if general['denominacion'].strip() != item['docnome'].strip():
            raise ValueError('Inventory/detail title mismatch')
        for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
            if source_date(item.get(field)) != source_date(general.get(field)):
                raise ValueError('Inventory/detail date mismatch')
        docs = {}
        for section in detail['elementos'] or []:
            for comp in section['componentes'] or []:
                relative = general['filesroot'] + general['folder'] + '/documents/' + comp['pathesperado']
                url = urljoin(BASE, relative)
                parsed = urlparse(url)
                if parsed.hostname != 'siotuga.xunta.gal' or not parsed.path.startswith('/siotuga/documentos/urbanismo/NOIA/documents/') or '..' in relative:
                    raise ValueError('Unexpected document provenance')
                docs.setdefault(url, {'id': str(comp['id']), 'titulo': comp['descripcion'],
                                      'grupo': section['description'], 'url': url})
        approval = source_date(item.get('fechaaddef'))
        warnings = [] if docs else ['SIOTUGA lists this instrument but exposes no linked documents']
        for field in ('fechabop', 'fechadog', 'fechanormativabop'):
            value = source_date(item.get(field))
            if approval and value and value < approval:
                warnings.append(f'{field} precedes fechaaddef in SIOTUGA; retained without correction')
        return {
            'id': 'noia-siotuga-' + str(item['id']), 'municipio': 'Noia',
            'codigo_ine': '15057', 'provincia': 'A Coruña',
            'titulo': item['figura'] + ': ' + item['docnome'].strip(),
            'tipo': item['figura'], 'fase': 'aprobación definitiva' if approval else None,
            'fecha_aprob': approval, 'fecha_publicacion': None,
            'fecha_bop': source_date(item.get('fechabop')),
            'fecha_dog': source_date(item.get('fechadog')),
            'fecha_normativa_bop': source_date(item.get('fechanormativabop')),
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'siotuga_inventario_municipal',
            'administracion_fuente': 'Xunta de Galicia', 'siotuga_id': str(item['id']),
            'categoria_inventario': category,
            'procedencia': {'inventario': QUERY, 'inventario_parametros': {'id': '15057', 'idclase': category},
                            'ficha': DETAIL, 'ficha_parametros': {'iddoc': str(item['id']), 'idp': '0', 'lang': 'es_ES'}},
            'incidencias_juridicas': detail.get('incidencias_iuris'),
            'documentos': list(docs.values()), 'documentos_status': 'available' if docs else 'unavailable',
            'advertencias_fuente': warnings,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }

    def _capture(self, name, content):
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir']) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-noia/1.0 (public planning inventory)'
            response = session.get(SOURCE, timeout=40)
            response.raise_for_status()
            self._capture('inventory.html', response.content)
            soup = BeautifulSoup(response.content, 'html.parser')
            token = soup.select_one('input#token')
            municipality = soup.select_one('select#idconcello option[value="15057"]')
            if token is None or municipality is None or municipality.get_text(strip=True) != 'Noia':
                raise ValueError('SIOTUGA inventory form changed')
            # Public form nonce, acquired anonymously for this session only.
            nonce = token['value']
            rows = {}
            for category in CLASSES:
                response = session.post(QUERY, data={'id': '15057', 'idclase': category, 'token': nonce}, timeout=40)
                response.raise_for_status()
                self._capture(f'class-{category}.json', response.content)
                for item in self.parse_inventory(response.json()):
                    key = str(item['id'])
                    if key in rows:
                        raise ValueError('Instrument repeated across inventory classes')
                    response = session.post(DETAIL, data={'iddoc': key, 'idp': '0', 'lang': 'es_ES', 'token': nonce}, timeout=40)
                    response.raise_for_status()
                    self._capture(f'detail-{key}.json', response.content)
                    rows[key] = self.parse_project(item, response.json(), category)
            if not rows:
                raise ValueError('No usable Noia planning instruments; review source')
        self._write(out_jsonl, list(rows.values()))
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, QUERY, DETAIL],
                'coverage': 'SIOTUGA general and development planning; historic and territorial sections excluded'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
