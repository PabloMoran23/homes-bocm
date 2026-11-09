"""Celanova planning snapshot from the municipal-linked public SIOTUGA inventory."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = BASE + 'inventario.php?inv=1&idconcello=32024'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
CLASSES = {14: 'general', 13: 'desarrollo', 16: 'historico', 18: 'delimitacion_nucleos'}
FIGURES = {'Plan Xeral de Ordenación Urbana', 'Modificación Puntual',
           'Plan Parcial', 'Plan Especial', 'Estudio de Detalle'}
LIMITATIONS = [
    'Snapshot of SIOTUGA municipal planning classes 14, 13, 16 and 18 only; '
    'not a complete municipal project, public-works or licence register.',
    'Regional territorial/sectoral instruments (IOT) are outside this adapter scope.',
    'Some inventory entries have metadata but no digitised attachments. '
    'Linked files are retained, not OCR-parsed or exhaustively downloaded.',
    'No verified vector geometry or coordinates; publication_ready is false.',
    'Approval, BOP, DOG and normative-publication dates retain their source meanings; '
    'no agreement date or generic publication date is inferred.',
]


def clean(value: Any) -> str:
    return ' '.join(str(value or '').split())


def source_date(value: Any) -> str | None:
    if value in (None, ''):
        return None
    return date.fromisoformat(value).isoformat()


class CelanovaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='celanova', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    @staticmethod
    def parse_inventory(payload: Any) -> list[dict]:
        # The site's DataTables pagination is client-side over this whole array.
        # Reject envelopes (including new server pagination), never slice results.
        if payload is None:
            return []
        if not isinstance(payload, list):
            raise ValueError('Expected full SIOTUGA array; pagination/schema changed')
        seen = set()
        for row in payload:
            if not isinstance(row, dict) or not str(row.get('id', '')).isdigit():
                raise ValueError('Invalid SIOTUGA inventory row')
            if row['id'] in seen:
                raise ValueError('Repeated inventory identifier')
            seen.add(row['id'])
            if clean(row.get('figura')) not in FIGURES or not clean(row.get('docnome')):
                raise ValueError('Unsupported or unnamed planning instrument')
            source_date(row.get('fechaaddef'))
        return payload

    @staticmethod
    def parse_detail(row: dict, detail: Any, category: str) -> dict:
        if not isinstance(detail, dict) or not isinstance(detail.get('datos_xerais'), dict):
            raise ValueError('Missing SIOTUGA dossier metadata')
        g = detail['datos_xerais']
        if (str(g.get('id')) != str(row['id']) or clean(g.get('menutitle')) != 'Celanova'
                or g.get('folder') != 'CELANOVA'):
            raise ValueError('Dossier does not belong to Celanova or requested ID')
        for inventory_key, detail_key in [('docnome', 'denominacion'), ('figura', 'figura'),
                                          ('fechaaddef', 'fechaaddef')]:
            if clean(row.get(inventory_key)) != clean(g.get(detail_key)):
                raise ValueError('Inventory and dossier disagree')
        title = clean(g['denominacion'])
        figure = clean(g['figura'])
        approval = source_date(g.get('fechaaddef'))
        if not approval:
            raise ValueError('Expected approved planning inventory entry')
        documents = {}
        for element in detail.get('elementos') or []:
            for component in element.get('componentes') or []:
                path = component['pathesperado']
                url = urljoin(BASE, g['filesroot'] + g['folder'] + '/documents/' + path)
                parsed = urlparse(url)
                if (parsed.scheme != 'https' or parsed.netloc != 'siotuga.xunta.gal'
                        or not parsed.path.startswith('/siotuga/documentos/urbanismo/CELANOVA/documents/')):
                    raise ValueError('Unexpected document location')
                documents[url] = {'titulo': clean(component.get('descripcion')),
                                  'grupo': clean(element.get('description')), 'url': url,
                                  'source_document_id': str(row['id'])}
        dates = {k: source_date(g.get(k)) for k in
                 ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop', 'fechatextodef')}
        key = '\n'.join([figure.casefold(), title.casefold(), approval])
        return {
            'id': 'celanova-proy-' + hashlib.sha256(key.encode()).hexdigest()[:20],
            'municipio': 'Celanova', 'provincia': 'Ourense', 'codigo_ine': '32024',
            'titulo': figure + ' — ' + title, 'tipo': 'planeamiento_urbanistico',
            'figura': figure, 'fase': 'aprobación definitiva',
            'fecha': None, 'fecha_aprob': approval, 'fecha_acuerdo': None,
            'fecha_publicacion': None,
            'url': SOURCE, 'source': 'ayuntamiento', 'organismo_fuente': 'Xunta de Galicia — SIOTUGA',
            'origen': 'inventario_planeamiento_municipal',
            'categorias_inventario': [category], 'source_ids': [str(row['id'])],
            'publicaciones': [{'medio': label, 'fecha': dates[field], 'source_document_id': str(row['id'])}
                              for field, label in [('fechabop', 'BOP'), ('fechadog', 'DOG'),
                                                   ('fechanormativabop', 'BOP normativa')]
                              if dates[field]],
            'procedencia': [{'source_document_id': str(row['id']), 'endpoint': DETAIL,
                             'request': {'iddoc': str(row['id']), 'idp': 0, 'lang': 'gl_ES'},
                             'fechas_fuente': dates,
                             'incidencias_iuris': detail.get('incidencias_iuris')}],
            'documentos': list(documents.values()),
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'limitaciones': LIMITATIONS,
        }

    @staticmethod
    def group_records(records: list[dict]) -> list[dict]:
        grouped = {}
        for row in records:
            existing = grouped.get(row['id'])
            if existing is None:
                grouped[row['id']] = row
                continue
            for field in ('source_ids', 'categorias_inventario', 'procedencia', 'publicaciones'):
                existing[field].extend(v for v in row[field] if v not in existing[field])
            urls = {d['url'] for d in existing['documentos']}
            existing['documentos'].extend(d for d in row['documentos'] if d['url'] not in urls)
        return sorted(grouped.values(), key=lambda r: r['id'])

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        capture = self.config.get('evidence_dir')
        source_urls = [SOURCE, QUERY, DETAIL]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-celanova/1.0'

            def fetch(url, name, data=None):
                with session.request('POST' if data is not None else 'GET', url,
                                     data=data, timeout=40, stream=True) as response:
                    response.raise_for_status()
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > 8_000_000:
                            raise ValueError('SIOTUGA response exceeds limit; no partial snapshot written')
                        chunks.append(chunk)
                    content = b''.join(chunks)
                if capture:
                    folder = Path(capture)
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / name).write_bytes(content)
                return content

            soup = BeautifulSoup(fetch(SOURCE, 'live-inventario.html'), 'html.parser')
            option = soup.select_one('#idconcello option[value="32024"]')
            token = soup.select_one('#token')
            if not option or clean(option.get_text()) != 'Celanova' or not token:
                raise ValueError('Public inventory form changed or municipality absent')
            # Public anonymous form nonce, obtained exactly as the site's JS does.
            nonce = token['value']
            records = []
            for class_id, category in CLASSES.items():
                payload = json.loads(fetch(QUERY, f'live-class-{class_id}.json',
                                          {'id': '32024', 'idclase': class_id, 'token': nonce}))
                for row in self.parse_inventory(payload):
                    detail = json.loads(fetch(DETAIL, f"live-detail-{row['id']}.json",
                                              {'iddoc': row['id'], 'idp': 0,
                                               'lang': 'gl_ES', 'token': nonce}))
                    records.append(self.parse_detail(row, detail, category))
        rows = self.group_records(records)
        if not rows:
            raise ValueError('No usable Celanova planning instruments')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_entries': len(records),
                'source_urls': source_urls, 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
