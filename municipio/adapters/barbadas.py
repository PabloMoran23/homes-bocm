"""Barbadás planning inventory linked by the municipality to official SIOTUGA."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = ROOT + 'inventario.php?inv=1&idconcello=32008'
QUERY = ROOT + 'assets/inventario/query_document.php'
DETAIL = ROOT + 'assets/inventario/getIOTPU.php'
CLASSES = {14: 'planeamiento general', 13: 'planeamiento de desarrollo'}
LIMITATIONS = [
    'Partial coverage: SIOTUGA general/development planning inventory only; not all municipal works.',
    'Historical section, supramunicipal territorial plans and environmental assessments excluded.',
    'Inventory classification does not independently establish present legal validity.',
    'No granted-licence register extracted; no verified vector geometry or coordinates.',
    'Document links retained as published; individual file availability is not exhaustively checked.',
]


def _text(value: Any) -> str:
    return ' '.join(str(value or '').split())


def _date(value: Any) -> str | None:
    if value is None or value == '':
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Unexpected SIOTUGA date format')
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload: Any) -> list[dict[str, Any]]:
    # SIOTUGA sends the entire array; DataTables paginates it in the browser.
    # Reject envelopes (including future server-side pagination), never slice.
    if payload is None:
        return []
    if not isinstance(payload, list) or len(payload) > 1000:
        raise ValueError('Unexpected or oversized SIOTUGA inventory; review pagination')
    rows = {}
    for item in payload:
        if not isinstance(item, dict) or not str(item.get('id', '')).isdigit():
            raise ValueError('Invalid planning instrument identifier')
        if not _text(item.get('docnome')) or not _text(item.get('figura')):
            raise ValueError('Missing planning instrument title/type')
        key = str(item['id'])
        if key in rows and rows[key] != item:
            raise ValueError('Conflicting duplicate instrument')
        rows[key] = item
    return list(rows.values())


def parse_detail(item: dict[str, Any], payload: Any, category: int) -> dict[str, Any]:
    if not isinstance(payload, dict) or category not in CLASSES:
        raise ValueError('Missing SIOTUGA planning detail')
    general = payload.get('datos_xerais') or {}
    if (str(general.get('id')) != str(item['id'])
            or general.get('menutitle') != 'Barbadás'
            or general.get('folder') != 'BARBADAS'
            or general.get('filesroot') != 'documentos/urbanismo/'):
        raise ValueError('Instrument identity/municipality mismatch')
    if (_text(general.get('denominacion')) != _text(item['docnome'])
            or _text(general.get('figura')) != _text(item['figura'])):
        raise ValueError('Inventory/detail title or type mismatch')
    for field in ('fechaaddef', 'fechadog', 'fechabop', 'fechanormativabop'):
        if _date(general.get(field)) != _date(item.get(field)):
            raise ValueError('Inventory/detail date mismatch')
    documents = {}
    elements = payload.get('elementos')
    if not isinstance(elements, list):
        raise ValueError('Missing planning document groups')
    for group in elements:
        if not isinstance(group, dict) or not isinstance(group.get('componentes'), list):
            raise ValueError('Invalid document group')
        for component in group['componentes']:
            filename = component.get('pathesperado', '')
            if not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:pdf|jpg|jpeg|png|zip)', filename, re.I):
                raise ValueError('Unexpected planning document path')
            url = urljoin(ROOT, general['filesroot'] + general['folder'] + '/documents/' + filename)
            documents.setdefault(url, {
                'id': str(component['id']), 'titulo': _text(component.get('descripcion')),
                'grupo': _text(group.get('description')), 'url': url,
                'source_url': DETAIL, 'source_params': {'iddoc': str(item['id']), 'idp': 0, 'lang': 'gl_ES'},
            })
    if not documents:
        raise ValueError('Instrument has no source documents')
    title = _text(item['docnome'])
    figura = _text(item['figura'])
    return {
        'id': 'barbadas-plan-' + str(item['id']), 'siotuga_id': str(item['id']),
        'municipio': 'Barbadás', 'codigo_ine': '32008', 'provincia': 'Ourense',
        'titulo': title if title.casefold().startswith(figura.casefold()) else figura + ' — ' + title,
        'tipo': figura, 'fase': 'aprobación definitiva' if general.get('fechaaddef') else None,
        'fecha': None, 'fecha_acuerdo': None, 'fecha_aprob': _date(general.get('fechaaddef')),
        'fecha_publicacion': None, 'fecha_publicacion_dog': _date(general.get('fechadog')),
        'fecha_publicacion_bop': _date(general.get('fechabop')),
        'fecha_publicacion_normativa_bop': _date(general.get('fechanormativabop')),
        'fecha_texto_refundido': _date(general.get('fechatextodef')),
        'incidencias_juridicas': payload.get('incidencias_iuris'),
        'incidencias_juridicas_inventario': item.get('incidencias_iuris'),
        'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'siotuga_inventario_planeamiento',
        'organismo_fuente': 'Xunta de Galicia — SIOTUGA (enlazado por el Concello)',
        'inventory_category': CLASSES[category],
        'source_url': QUERY, 'source_method': 'POST',
        'source_params': {'id': '32008', 'idclase': category},
        'detail_url': DETAIL, 'detail_params': {'iddoc': str(item['id']), 'idp': 0, 'lang': 'gl_ES'},
        'documentos': list(documents.values()),
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'unavailable; raster plans are retained as document links',
    }


class BarbadasAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug: str, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.barbadas.es')
        if slug != 'barbadas' or str(self.config.get('ine_code', '32008')) != '32008':
            raise ValueError('This adapter is exclusively for Barbadás INE 32008')

    def _fetch(self, session, url, name, data=None):
        with session.request('POST' if data is not None else 'GET', url, data=data,
                             timeout=35, stream=True) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'siotuga.xunta.gal':
                raise ValueError('Unexpected SIOTUGA redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 8_000_000:
                    raise ValueError('Source exceeds reviewed size; no truncated extraction')
                chunks.append(chunk)
            body = b''.join(chunks)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_bytes(body)
        return body.decode('utf-8-sig')

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-barbadas/1.0 (public planning inventory)'
            html = self._fetch(session, SOURCE, 'inventory-page.html')
            soup = BeautifulSoup(html, 'html.parser')
            token = soup.select_one('input#token[value]')
            option = soup.select_one('select#idconcello option[value="32008"]')
            if not token or not option or option.get_text(strip=True) != 'Barbadás':
                raise ValueError('SIOTUGA municipality form missing or changed')
            rows = {}
            for category in CLASSES:
                data = {'id': '32008', 'idclase': category, 'token': token['value']}
                items = parse_inventory(json.loads(self._fetch(session, QUERY, f'inventory-{category}.json', data)))
                for item in items:
                    key = str(item['id'])
                    if key in rows:
                        raise ValueError('Instrument repeated across inventory categories')
                    detail = json.loads(self._fetch(session, DETAIL, f'detail-{key}.json', {
                        'iddoc': key, 'idp': 0, 'lang': 'gl_ES', 'token': token['value'],
                    }))
                    rows[key] = parse_detail(item, detail, category)
            if not rows:
                raise ValueError('No usable planning instruments; review source')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows.values()), encoding='utf-8')
        temp.replace(output)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, QUERY, DETAIL],
                'coverage': 'complete arrays for municipal planning classes 14 and 13; partial municipal coverage',
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Refresh all supported inventory sections; no date-based skipping.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
