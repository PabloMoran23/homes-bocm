"""Moraña planning inventory from the Xunta's public SIOTUGA service."""
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
SOURCE = BASE + 'inventario?inv=1&idconcello=36032'
CLASSES = {14: 'planeamiento_general', 13: 'planeamiento_desarrollo', 18: 'delimitacion_nucleo_rural'}
LIMITATIONS = [
    'Partial coverage: SIOTUGA general/development/rural-delimitation planning inventory only; no works or granted licences.',
    'Historical planning and supramunicipal territorial instruments excluded; newer proceedings may be absent from this inventory.',
    'Source approval/publication dates do not establish present legal validity; legal observations retained.',
    'No verified vector geometry or coordinates; publication_ready false.',
    'Document links retained as supplied; individual file availability is not exhaustively checked.',
]


def _date(value):
    if value in (None, ''):
        return None
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload):
    # The site's JS renders the entire array in client-side DataTables, with no
    # server-side page/limit arguments. Reject envelopes instead of dropping pages.
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Unexpected inventory envelope/pagination; review service')
    seen = set()
    for row in payload:
        if not isinstance(row, dict) or not re.fullmatch(r'\d+', str(row.get('id', ''))):
            raise ValueError('Invalid planning inventory entry')
        if row['id'] in seen or not row.get('figura'):
            raise ValueError('Duplicate or unnamed planning entry')
        seen.add(row['id'])
    return payload


def parse_project(entry, detail, category):
    info = detail['datos_xerais']
    if (str(info['id']) != str(entry['id']) or info['menutitle'] != 'Moraña'
            or info['folder'] != 'MORANA'):
        raise ValueError('Dossier identity/municipality mismatch')
    title = info['denominacion'].strip()
    if not title or info['figura'] != entry['figura']:
        raise ValueError('Missing or conflicting planning instrument')
    dates = {}
    for key in ('fechaaddef', 'fechadog', 'fechabop', 'fechanormativabop'):
        dates[key] = _date(info.get(key))
        if dates[key] != _date(entry.get(key)):
            raise ValueError('Conflicting inventory/detail dates')
    documents = []
    for group in detail['elementos']:
        for component in group['componentes']:
            filename = component['pathesperado']
            if not re.fullmatch(r'[\w.-]+\.(?:pdf|jpg|jpeg|png)', filename, re.I):
                raise ValueError('Unexpected source document path')
            url = urljoin(BASE, info['filesroot'] + info['folder'] + '/documents/' + filename)
            if urlparse(url).hostname != 'siotuga.xunta.gal':
                raise ValueError('Unexpected document host')
            # Keep component identity even where the source repeats a file path
            # under two labels (e.g. rural-study fichas 12 and 13).
            documents.append({'id': str(component['id']), 'titulo': component['descripcion'],
                              'grupo': group['description'], 'url': url})
    if not documents:
        raise ValueError('Instrument has no source documents')
    return {
        'id': 'morana-siotuga-' + str(entry['id']), 'siotuga_id': str(entry['id']),
        'municipio': 'Moraña', 'codigo_ine': '36032', 'provincia': 'Pontevedra',
        'titulo': info['figura'] + ' — ' + title, 'tipo': info['figura'],
        'categoria_inventario': category,
        'fecha': None, 'fecha_aprob': dates['fechaaddef'],
        'fecha_publicacion': dates['fechadog'], 'canal_publicacion': 'DOG',
        'fecha_publicacion_bop': dates['fechabop'],
        'fecha_publicacion_normativa_bop': dates['fechanormativabop'],
        'url': SOURCE, 'source': 'xunta', 'origen': 'siotuga_inventario_municipal',
        'provenance': {'inventory_url': BASE + 'assets/inventario/query_document.php',
                       'inventory_method': 'POST', 'inventory_params': {'id': '36032', 'idclase': next(k for k, v in CLASSES.items() if v == category)},
                       'detail_url': BASE + 'assets/inventario/getIOTPU.php',
                       'detail_method': 'POST', 'detail_params': {'iddoc': str(entry['id']), 'idp': 0, 'lang': 'gl_ES'}},
        'documentos': documents,
        'incidencias_juridicas': detail.get('incidencias_iuris'),
        'incidencias_inventario': entry.get('incidencias_iuris'),
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'coverage': LIMITATIONS,
    }


class MoranaAyuntamientoAdapter(AyuntamientoAdapter):
    def _capture(self, name, content):
        if self.config.get('capture_dir'):
            root = Path(self.config['capture_dir'])
            root.mkdir(parents=True, exist_ok=True)
            (root / name).write_bytes(content)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-morana/1.0'
            def fetch(path, name, data=None):
                response = session.request('GET' if data is None else 'POST', urljoin(BASE, path), data=data, timeout=30)
                response.raise_for_status()
                self._capture(name, response.content)
                return response

            page = fetch(SOURCE, 'inventario.html')
            soup = BeautifulSoup(page.content, 'html.parser')
            municipality = soup.select_one('select#idconcello option[value="36032"]')
            csrf = soup.select_one('input#token')
            if not municipality or municipality.get_text(strip=True) != 'Moraña' or not csrf:
                raise ValueError('SIOTUGA public search form changed')
            # Public anti-CSRF form field, obtained anonymously; no login needed.
            form = {'id': '36032', 'token': csrf['value']}
            rows = {}
            for ident, category in CLASSES.items():
                response = fetch('assets/inventario/query_document.php', f'inventory-{ident}.json', {**form, 'idclase': ident})
                for entry in parse_inventory(response.json()):
                    key = str(entry['id'])
                    if key in rows:
                        raise ValueError('Instrument repeated across inventory classes')
                    detail = fetch('assets/inventario/getIOTPU.php', f'detail-{key}.json',
                                   {'iddoc': key, 'idp': 0, 'lang': 'gl_ES', 'token': csrf['value']}).json()
                    rows[key] = parse_project(entry, detail, category)
        if not rows:
            raise ValueError('No usable Moraña planning instruments')
        result = self._write(out_jsonl, [rows[k] for k in sorted(rows)])
        return {**result, 'source_urls': [SOURCE, BASE + 'assets/inventario/query_document.php', BASE + 'assets/inventario/getIOTPU.php'], 'limitations': LIMITATIONS}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot, including deletions; state is not an approval date.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
