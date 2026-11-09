"""Neda municipal planning inventory in the Xunta's public SIOTUGA portal."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://siotuga.xunta.gal/siotuga/'
INVENTORY = ROOT + 'inventario?inv=1&idconcello=15055'
QUERY = ROOT + 'assets/inventario/query_document.php'
DETAIL = ROOT + 'assets/inventario/getIOTPU.php'
CLASSES = {14: 'planeamiento_general', 13: 'planeamiento_desarrollo',
           16: 'planeamiento_historico', 18: 'delimitacion_nucleo_rural'}


def parse_inventory(payload):
    """The public UI loads full arrays, then paginates locally with DataTables."""
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Expected complete SIOTUGA array, not a paginated envelope')
    for row in payload:
        if (not isinstance(row, dict) or not str(row.get('id', '')).isdigit()
                or not row.get('docnome') or not row.get('figura')):
            raise ValueError('Invalid SIOTUGA instrument')
    return payload


def parse_instrument(entry, detail, classes):
    general = detail['datos_xerais']
    identity = str(entry['id'])
    if (str(general['id']) != identity or general['menutitle'] != 'Neda'
            or general['folder'] != 'NEDA'):
        raise ValueError('Instrument identity/municipality mismatch')
    for field in ('denominacion', 'figura'):
        if not general.get(field):
            raise ValueError('Missing instrument title/type')
    row = {
        'id': 'neda-siotuga-' + identity, 'id_origen': identity,
        'municipio': 'Neda', 'codigo_ine': '15055', 'provincia': 'A Coruña',
        'titulo': general['denominacion'], 'tipo': general['figura'],
        'source': 'xunta_siotuga', 'origen': 'inventario_planeamiento_municipal',
        'source_dataset': INVENTORY, 'url': INVENTORY,
        'categorias_inventario': [CLASSES[c] for c in sorted(classes)],
        'historico': 16 in classes,
        'publication_ready': False, 'geometry_status': 'unavailable',
        'procedencia': {'url': DETAIL, 'metodo': 'POST',
                        'parametros': {'iddoc': identity, 'idp': '0', 'lang': 'gl_ES'}},
    }
    for original, target in [('fechaaddef', 'fecha_aprob'), ('fechabop', 'fecha_publicacion_bop'),
                             ('fechadog', 'fecha_publicacion_dog'),
                             ('fechanormativabop', 'fecha_publicacion_normativa_bop'),
                             ('fechatextodef', 'fecha_texto_refundido')]:
        value = general.get(original)
        if original in entry and entry[original] != value:
            raise ValueError('Inventory/detail date mismatch')
        if value:
            row[target] = date.fromisoformat(value).isoformat()
    row['incidencias_juridicas'] = detail.get('incidencias_iuris')
    documents = {}
    elements = detail['elementos']
    if elements is not None and not isinstance(elements, list):
        raise ValueError('Invalid document groups')
    for group in elements or []:
        for component in group['componentes']:
            path = component['pathesperado']
            if not path or '..' in path or urlparse(path).scheme or path.startswith('/'):
                raise ValueError('Unexpected document path')
            url = urljoin(ROOT, general['filesroot'] + general['folder'] + '/documents/' + path)
            if urlparse(url).hostname != 'siotuga.xunta.gal':
                raise ValueError('Unexpected document host')
            documents.setdefault(url, {'id_origen': str(component['id']),
                                      'titulo': component['descripcion'],
                                      'grupo': group['description'], 'url': url})
    row['documentos'] = list(documents.values())
    row['documentacion_status'] = 'enlaces_inventariados' if documents else 'sin_documentos_disponibles'
    return row


class NedaAyuntamientoAdapter(AyuntamientoAdapter):
    def _capture(self, name, response):
        directory = self.config.get('evidence_dir')
        if directory:
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)
            (path / name).write_bytes(response.content)

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-neda/1.0 (public planning inventory)'
            response = session.get(INVENTORY, timeout=40)
            response.raise_for_status()
            if urlparse(response.url).hostname != 'siotuga.xunta.gal':
                raise ValueError('Unexpected inventory redirect')
            self._capture('inventory.html', response)
            soup = BeautifulSoup(response.content, 'html.parser')
            option = soup.select_one('#idconcello option[value="15055"]')
            if option is None or option.get_text(strip=True) != 'Neda':
                raise ValueError('Municipality selector missing')
            token = soup.select_one('#token')['value']
            entries = {}
            for category in CLASSES:
                response = session.post(QUERY, data={'id': '15055', 'idclase': category, 'token': token}, timeout=40)
                response.raise_for_status()
                self._capture(f'class_{category}.json', response)
                for entry in parse_inventory(response.json()):
                    identity = str(entry['id'])
                    if identity in entries:
                        if entries[identity][0] != entry:
                            raise ValueError('Conflicting duplicate instrument')
                        entries[identity][1].add(category)
                    else:
                        entries[identity] = (entry, {category})
            if not entries:
                raise ValueError('No municipal planning instruments found')
            rows = []
            for identity, (entry, categories) in entries.items():
                response = session.post(DETAIL, data={'iddoc': identity, 'idp': '0', 'lang': 'gl_ES', 'token': token}, timeout=40)
                response.raise_for_status()
                self._capture(f'detail_{identity}.json', response)
                rows.append(parse_instrument(entry, response.json(), categories))
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'coverage': 'municipal_planning_inventory_including_history',
                'source_urls': [INVENTORY, QUERY, DETAIL], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh: no publication chronology is available for incremental cursors.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
