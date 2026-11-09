"""Mondariz municipal planning inventory, published by Xunta's SIOTUGA."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = BASE + 'inventario?inv=1&idconcello=36030'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
CLASSES = {14: 'planeamento_xeral', 13: 'planeamento_desenvolvemento', 18: 'delimitacion_nucleo_rural'}


def source_date(value):
    if value in (None, ''):
        return None
    return date.fromisoformat(value).isoformat()


class MondarizAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='mondariz', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://mondariz.sedelectronica.gal')

    @staticmethod
    def parse_inventory(payload: Any) -> list[dict]:
        # The portal receives complete JSON arrays and paginates in DataTables
        # locally. A new server-side envelope must not become a partial snapshot.
        if payload is None:
            return []
        if not isinstance(payload, list):
            raise ValueError('Expected complete SIOTUGA array, not a pagination envelope')
        rows = {}
        for row in payload:
            if not isinstance(row, dict) or not str(row.get('id', '')).isdigit():
                raise ValueError('Invalid SIOTUGA inventory row')
            if not row.get('figura') or not row.get('docnome'):
                raise ValueError('Missing instrument title/type')
            source_date(row.get('fechaaddef'))
            key = str(row['id'])
            if key in rows and rows[key] != row:
                raise ValueError('Conflicting instrument identity')
            rows[key] = row
        return list(rows.values())

    @staticmethod
    def parse_project(row: dict, detail: dict, inventory_class: int) -> dict:
        info = detail['datos_xerais']
        if (str(info['id']) != str(row['id']) or info.get('menutitle') != 'Mondariz'
                or info.get('folder') != 'MONDARIZ'):
            raise ValueError('Detail does not belong to this Mondariz instrument')
        for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
            if info.get(field) != row.get(field):
                raise ValueError('Inventory/detail dates disagree')
        docs = {}
        for group in detail.get('elementos') or []:
            for component in group['componentes']:
                url = urljoin(BASE, info['filesroot'] + info['folder'] + '/documents/' + component['pathesperado'])
                if (urlparse(url).hostname != 'siotuga.xunta.gal'
                        or not urlparse(url).path.startswith('/siotuga/documentos/urbanismo/MONDARIZ/documents/')):
                    raise ValueError('Unexpected document provenance')
                docs[url] = {'url': url, 'titulo': component['descripcion'], 'grupo': group['description']}
        return {
            'id': 'mondariz-siotuga-' + str(row['id']),
            'municipio': 'Mondariz', 'codigo_ine': '36030', 'provincia': 'Pontevedra',
            'titulo': row['figura'].strip() + ': ' + row['docnome'].strip(),
            'tipo': row['figura'], 'fase': 'aprobación definitiva' if row.get('fechaaddef') else None,
            'fecha': None, 'fecha_acuerdo': None,
            'fecha_aprob': source_date(row.get('fechaaddef')),
            'fecha_publicacion': source_date(row.get('fechadog')),
            'fecha_publicacion_fuente': 'DOG' if row.get('fechadog') else None,
            'fecha_publicacion_bop': source_date(row.get('fechabop')),
            'fecha_publicacion_normativa_bop': source_date(row.get('fechanormativabop')),
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'siotuga_xunta',
            'organismo_publicador': 'Xunta de Galicia — SIOTUGA',
            'siotuga_id': str(row['id']), 'inventario_clase': CLASSES[inventory_class],
            'procedencia': {'inventario': QUERY, 'parametros_inventario': {'id': '36030', 'idclase': inventory_class},
                            'ficha': DETAIL, 'parametros_ficha': {'iddoc': str(row['id']), 'idp': 0, 'lang': 'gl_ES'}},
            'documentos': list(docs.values()),
            'documentacion_status': 'enlaces_disponibles' if docs else 'sin_documentos_en_ficha',
            'incidencias_juridicas': detail.get('incidencias_iuris'),
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        }

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        captures = self.config.get('evidence_dir')
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-mondariz/1.0'

            def fetch(url, name, data=None):
                response = session.get(url, timeout=40) if data is None else session.post(url, data=data, timeout=40)
                response.raise_for_status()
                source_urls.append(url)
                if captures:
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / name).write_bytes(response.content)
                return response

            page = BeautifulSoup(fetch(SOURCE, 'inventory.html').content, 'html.parser')
            selected = page.select_one('option[value="36030"]')
            token = page.select_one('input#token')
            if not selected or selected.get_text(strip=True) != 'Mondariz' or not token:
                raise ValueError('Missing municipality selector/public form token')
            rows = {}
            counts = {}
            for cls in CLASSES:
                payload = fetch(QUERY, f'class-{cls}.json', {'id': '36030', 'idclase': cls, 'token': token['value']}).json()
                inventory = self.parse_inventory(payload)
                counts[str(cls)] = len(inventory)
                for row in inventory:
                    detail = fetch(DETAIL, f"detail-{row['id']}.json", {'iddoc': row['id'], 'idp': 0, 'lang': 'gl_ES', 'token': token['value']}).json()
                    project = self.parse_project(row, detail, cls)
                    if project['id'] in rows:
                        raise ValueError('Instrument appears in multiple inventory classes')
                    rows[project['id']] = project
        if not rows:
            raise ValueError('No usable Mondariz planning instruments')
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temporary = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows.values()), encoding='utf-8')
        temporary.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(dict.fromkeys(source_urls)), 'inventory_counts': counts,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        # No forms or notices are converted into granted licences.
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
