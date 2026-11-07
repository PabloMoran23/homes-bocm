"""Mos planning inventory linked by the council; SIOTUGA public read endpoints."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = ROOT + 'inventario.php?inv=1&idconcello=36033'
INVENTORY = ROOT + 'assets/inventario/query_document.php'
DETAIL = ROOT + 'assets/inventario/getIOTPU.php'
CLASSES = {'14': 'planeamento_xeral', '13': 'planeamento_desenvolvemento'}
LIMITATIONS = [
    'Partial coverage: only SIOTUGA general and development planning categories (14, 13).',
    'Includes older instruments; approval does not establish present legal validity or construction.',
    'Territorial instruments, historical category, rural delimitations, works and licences are outside scope.',
    'Document links retained as published; document contents and georeferenced geometry are not extracted.',
    'No verified coordinates; publication_ready is false.',
]


def _date(value):
    return date.fromisoformat(value).isoformat() if value else None


class MosAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(payload):
        # The public UI receives a whole array and paginates it client-side.
        # Reject envelopes, errors and duplicate IDs rather than losing pages.
        if not isinstance(payload, list):
            raise ValueError('Expected complete SIOTUGA inventory array')
        rows = {}
        for item in payload:
            if not isinstance(item, dict) or not str(item.get('id', '')).isdigit():
                raise ValueError('Invalid planning identifier')
            key = str(item['id'])
            if key in rows or not item.get('docnome') or not item.get('figura'):
                raise ValueError('Duplicate or incomplete planning instrument')
            for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
                _date(item.get(field))
            rows[key] = item
        return rows

    @staticmethod
    def parse_detail(item, detail, category):
        if not isinstance(detail, dict) or not isinstance(detail.get('datos_xerais'), dict):
            raise ValueError('Missing SIOTUGA detail')
        general = detail['datos_xerais']
        key = str(item['id'])
        if str(general.get('id')) != key or general.get('menutitle') != 'Mos':
            raise ValueError('Detail does not belong to the requested Mos instrument')
        for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
            if general.get(field) != item.get(field):
                raise ValueError('Inventory/detail date mismatch')
        if 'elementos' not in detail or (detail['elementos'] is not None and not isinstance(detail['elementos'], list)):
            raise ValueError('Missing complete document inventory')
        documents = {}
        for group in detail['elementos'] or []:
            if not isinstance(group.get('componentes'), list):
                raise ValueError('Incomplete document group')
            for component in group['componentes']:
                path = component.get('pathesperado')
                if not path:
                    raise ValueError('Document lacks published path')
                url = urljoin(ROOT, general['filesroot'] + general['folder'] + '/documents/' + path)
                if urlparse(url).hostname != 'siotuga.xunta.gal':
                    raise ValueError('Unexpected document host')
                doc = documents.setdefault(url, {
                    'url': url, 'titulo': component.get('descripcion'),
                    'source_component_id': str(component['id']), 'grupos': [],
                    'procedencia': 'SIOTUGA getIOTPU: elementos.componentes',
                })
                if group.get('description') not in doc['grupos']:
                    doc['grupos'].append(group.get('description'))
        detail_url = DETAIL + '?' + urlencode({'iddoc': key, 'idp': '0', 'lang': 'gl_ES'})
        return {
            'id': 'mos-siotuga-' + key, 'municipio': 'Mos', 'provincia': 'Pontevedra',
            'codigo_ine': '36033', 'titulo': item['docnome'].strip(),
            'tipo': item['figura'], 'categoria_inventario': CLASSES[category],
            'fase': 'aprobación definitiva' if item.get('fechaaddef') else None,
            'fecha': None, 'fecha_acuerdo': None, 'fecha_aprob': _date(item.get('fechaaddef')),
            'fecha_publicacion': None,
            'fecha_publicacion_bop': _date(item.get('fechabop')),
            'fecha_publicacion_dog': _date(item.get('fechadog')),
            'fecha_publicacion_normativa_bop': _date(item.get('fechanormativabop')),
            'url': SOURCE, 'url_fuente_detalle': detail_url,
            'source': 'ayuntamiento', 'organismo_fuente': 'Xunta de Galicia — SIOTUGA',
            'origen': 'inventario_planeamento_enlazado_por_concello',
            'source_id': key, 'documentos': list(documents.values()),
            'documentos_estado': 'enlaces publicados' if documents else 'sin documentos en SIOTUGA',
            'incidencias_juridicas': detail.get('incidencias_iuris'),
            'observaciones_inventario': item.get('incidencias_iuris'),
            'vigencia_actual': 'no verificada',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        }

    def backfill_proyectos(self, out_jsonl):
        capture = self.config.get('capture_dir')
        captures = Path(capture) if capture else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
        sources = [SOURCE]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-mos/1.0'

            def fetch(url, name, data=None):
                response = session.get(url, timeout=40) if data is None else session.post(url, data=data, timeout=40)
                response.raise_for_status()
                if len(response.content) > 10_000_000:
                    raise ValueError('SIOTUGA response exceeds reviewed size')
                if captures:
                    (captures / name).write_bytes(response.content)
                return response

            page = fetch(SOURCE, 'live-inventory.html')
            soup = BeautifulSoup(page.content, 'html.parser')
            option = soup.select_one('#idconcello option[value="36033"]')
            token = soup.select_one('#token')
            if option is None or option.get_text(strip=True) != 'Mos' or token is None:
                raise ValueError('Mos public inventory form missing')
            # Anonymous form nonce supplied by the public site, not login access.
            nonce = token['value']
            rows, seen = [], set()
            for category in CLASSES:
                payload = fetch(INVENTORY, f'live-class-{category}.json',
                                {'id': '36033', 'idclase': category, 'token': nonce}).json()
                sources.append(INVENTORY + '?' + urlencode({'id': '36033', 'idclase': category}))
                for key, item in self.parse_inventory(payload).items():
                    if key in seen:
                        raise ValueError('Instrument repeated across categories; review grouping')
                    seen.add(key)
                    detail = fetch(DETAIL, f'live-plan-{key}.json',
                                   {'iddoc': key, 'idp': '0', 'lang': 'gl_ES', 'token': nonce}).json()
                    row = self.parse_detail(item, detail, category)
                    sources.append(row['url_fuente_detalle'])
                    rows.append(row)
        if not rows:
            raise ValueError('No usable Mos planning instruments')
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': sources, 'limitations': LIMITATIONS,
                'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
