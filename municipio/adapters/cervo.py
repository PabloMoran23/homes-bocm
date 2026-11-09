"""Cervo's approved municipal planning inventory in Xunta's public SIOTUGA."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
SOURCE = BASE + 'inventario.php?inv=1&idconcello=27013'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
# Deliberately exclude historical class 16 and territorial (multi-municipal) plans.
CLASSES = {14: 'planeamento_xeral', 13: 'planeamento_desenvolvemento', 18: 'delimitacion_nucleo_rural'}
LIMITATIONS = [
    'Partial coverage: approved municipal planning in SIOTUGA classes 14, 13 and 18 only; historical class 16 and territorial instruments excluded.',
    'No pending plans, works inventory or granted licences; the 2026 Parque da Veiga environmental consultation is outside this approved-plan inventory.',
    'Approval is the catalogue fechaaddef, not a licence grant; BOP, DOG and normative publication dates retained separately. Municipal web publication and agreement dates unknown.',
    'Catalogue document links retained; some instrument details explicitly have no digitised documents. PDF/map contents are not interpreted as separate projects or proof of completed works.',
    'No verified instrument geometry extracted. WMS cartography exists but is not a linked legal vector boundary; no coordinates inferred.',
]


def _date(value):
    if value in (None, ''):
        return None
    return date.fromisoformat(value).isoformat()


class CervoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(payload, class_id):
        if class_id not in CLASSES:
            raise ValueError('Unsupported inventory class')
        if payload is None:
            return []  # The public endpoint uses JSON null for an empty class.
        if not isinstance(payload, list):
            raise ValueError('Expected complete JSON array; pagination/schema change requires review')
        records = {}
        for row in payload:
            if not isinstance(row, dict) or not str(row.get('id', '')).isdigit():
                raise ValueError('Missing SIOTUGA instrument ID')
            if not row.get('docnome', '').strip() or not row.get('figura'):
                raise ValueError('Instrument title/type missing')
            for key in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
                _date(row.get(key))
            ident = str(row['id'])
            if ident in records and records[ident] != row:
                raise ValueError('Conflicting instrument ID')
            records[ident] = row
        return list(records.values())

    @staticmethod
    def parse_detail(row, payload, class_id):
        if not isinstance(payload, dict) or not isinstance(payload.get('datos_xerais'), dict):
            raise ValueError('Missing instrument detail')
        general = payload['datos_xerais']
        ident = str(row['id'])
        if str(general.get('id')) != ident or general.get('folder') != 'CERVO' or general.get('menutitle') != 'Cervo':
            raise ValueError('Instrument identity/municipality mismatch')
        if general.get('denominacion', '').strip() != row['docnome'].strip() or general.get('figura') != row['figura']:
            raise ValueError('Instrument title/type changed between inventory and detail')
        for key in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
            if _date(general.get(key)) != _date(row.get(key)):
                raise ValueError('Date changed between inventory and detail')
        if general.get('filesroot') != 'documentos/urbanismo/':
            raise ValueError('Unexpected document root')
        docs = {}
        elements = payload['elementos']
        if elements is None:
            elements = []  # Explicit null: valid catalogue record, no digitised attachments.
        if not isinstance(elements, list):
            raise ValueError('Document groups missing')
        for group in elements:
            for component in group['componentes']:
                path = component['pathesperado']
                if not path or path.startswith('/') or '..' in path.split('/') or urlparse(path).scheme:
                    raise ValueError('Unexpected document path')
                url = urljoin(BASE, 'documentos/urbanismo/CERVO/documents/' + quote(path, safe='/'))
                doc = {'id_origen': str(component['id']), 'titulo': component['descripcion'],
                       'grupo': group['description'], 'url': url}
                key = (str(component['id']), group['description'])
                if key in docs and docs[key] != doc:
                    raise ValueError('Conflicting document metadata')
                docs[key] = doc
        return {
            'id': 'cervo-siotuga-' + ident, 'id_origen': ident,
            'municipio': 'Cervo', 'codigo_ine': '27013', 'provincia': 'Lugo',
            'titulo': row['docnome'].strip(), 'tipo': row['figura'],
            'categoria': 'planeamiento_urbanistico', 'source_entity_type': 'expediente',
            'fase': 'aprobación definitiva', 'fecha': None,
            'fecha_acuerdo': None, 'fecha_publicacion': None,
            'fecha_aprob': _date(row.get('fechaaddef')),
            'fecha_publicacion_bop': _date(row.get('fechabop')),
            'fecha_publicacion_dog': _date(row.get('fechadog')),
            'fecha_publicacion_normativa_bop': _date(row.get('fechanormativabop')),
            'incidencias_juridicas': row.get('incidencias_iuris'),
            'incidencias_juridicas_detalle': payload.get('incidencias_iuris'),
            'url': SOURCE, 'source': 'siotuga', 'source_dataset': SOURCE,
            'origen': CLASSES[class_id], 'documentos': list(docs.values()),
            'documentos_status': 'linked' if docs else 'unavailable_in_catalogue',
            'provenance': {'inventory': {'url': QUERY, 'method': 'POST', 'parameters': {'id': '27013', 'idclase': class_id}},
                           'detail': {'url': DETAIL, 'method': 'POST', 'parameters': {'iddoc': ident, 'idp': 0, 'lang': 'gl_ES'}}},
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        capture = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        if capture:
            capture.mkdir(parents=True, exist_ok=True)

        def save(name, content):
            if capture:
                (capture / name).write_text(content, encoding='utf-8')

        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-cervo/1.0 (public planning inventory)'
            page = session.get(SOURCE, timeout=30)
            page.raise_for_status()
            page.encoding = 'utf-8'
            soup = BeautifulSoup(page.text, 'html.parser')
            selected = soup.select_one('#idconcello option[value="27013"]')
            token = soup.select_one('#token')
            if not selected or selected.get_text(strip=True) != 'Cervo' or not token or not token.get('value'):
                raise ValueError('Public inventory form missing or municipality changed')
            # Anonymous form nonce supplied by the public website, not credentials.
            nonce = token['value']
            token['value'] = '[public form nonce omitted]'
            save('inventory.html', str(soup))

            def post(url, parameters, name):
                response = session.post(url, data={**parameters, 'token': nonce}, timeout=30)
                response.raise_for_status()
                data = response.json()
                save(name, json.dumps(data, ensure_ascii=False, indent=2))
                return data

            inventories = {}
            for class_id in CLASSES:
                payload = post(QUERY, {'id': '27013', 'idclase': class_id}, f'class-{class_id}.json')
                for row in self.parse_inventory(payload, class_id):
                    ident = str(row['id'])
                    if ident in inventories:
                        raise ValueError('Instrument appears in multiple classes; review grouping')
                    inventories[ident] = (class_id, row)
            if not inventories:
                raise ValueError('No usable planning instruments; review before replacing output')
            rows = []
            for ident, (class_id, row) in inventories.items():
                detail = post(DETAIL, {'iddoc': ident, 'idp': 0, 'lang': 'gl_ES'}, f'detail-{ident}.json')
                rows.append(self.parse_detail(row, detail, class_id))
        rows.sort(key=lambda row: row['id'])
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, QUERY, DETAIL],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot; no date cursor that could lose amended old instruments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
