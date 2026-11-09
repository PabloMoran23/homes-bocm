"""Chantada planning instruments from the public SIOTUGA municipal inventory."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL_SOURCE = 'https://www.concellodechantada.org/servizos/urbanismo/plan-xeral-de-ordenacion-urbanistica/'
BASE = 'https://siotuga.xunta.gal/siotuga/'
INVENTORY = BASE + 'inventario.php?inv=1&idconcello=27016'
QUERY = BASE + 'assets/inventario/query_document.php'
DETAIL = BASE + 'assets/inventario/getIOTPU.php'
CLASSES = {14: 'planeamento_xeral', 13: 'planeamento_desenvolvemento',
           16: 'planeamento_historico', 18: 'delimitacion_nucleo_rural'}


def source_date(value):
    if value is None or value == '':
        return None
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload, category):
    """The portal returns the whole category as an array, not a server-side page."""
    if category not in CLASSES:
        raise ValueError('Unsupported inventory category')
    if payload is None:
        return []  # SIOTUGA uses JSON null for an empty category.
    if not isinstance(payload, list):
        raise ValueError('Inventory schema changed; check pagination/envelope')
    result = {}
    for item in payload:
        if not isinstance(item, dict) or not str(item.get('id', '')).isdigit():
            raise ValueError('Invalid planning identifier')
        if not item.get('docnome', '').strip() or not item.get('figura', '').strip():
            raise ValueError('Missing instrument title/type')
        identifier = str(item['id'])
        if identifier in result and result[identifier] != item:
            raise ValueError('Conflicting duplicate instrument')
        result[identifier] = item
        for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
            source_date(item.get(field))
    return list(result.values())


def parse_instrument(item, detail, categories):
    general = detail.get('datos_xerais', {})
    identifier = str(item['id'])
    if str(general.get('id')) != identifier or general.get('menutitle', '').strip() != 'Chantada':
        raise ValueError('Detail identifier/municipality mismatch')
    for field in ('fechaaddef', 'fechabop', 'fechadog', 'fechanormativabop'):
        if source_date(general.get(field)) != source_date(item.get(field)):
            raise ValueError('Detail/inventory date mismatch')
    root = urljoin(BASE, general['filesroot'] + general['folder'] + '/documents/')
    if urlparse(root).hostname != 'siotuga.xunta.gal' or '/CHANTADA/documents/' not in root:
        raise ValueError('Unexpected document repository')
    documents = {}
    for element in detail.get('elementos') or []:
        for component in element['componentes']:
            url = urljoin(root, component['pathesperado'])
            if not url.startswith(root):
                raise ValueError('Document outside municipal repository')
            document = documents.setdefault(url, {
                'url': url, 'titulo': component['descripcion'].strip(),
                'grupos': [], 'source_url': DETAIL, 'siotuga_id': identifier,
            })
            if element['description'] not in document['grupos']:
                document['grupos'].append(element['description'])
    if not documents:
        raise ValueError('Instrument lacks linked source documents')
    return {
        'id': 'chantada-siotuga-' + identifier,
        'municipio': 'Chantada', 'codigo_ine': '27016', 'provincia': 'Lugo',
        'titulo': item['docnome'].strip(), 'tipo': item['figura'].strip(),
        'url': INVENTORY, 'inventory_url': INVENTORY,
        'url_documento': next(iter(documents)),
        'source': 'ayuntamiento', 'organismo_fuente': 'Xunta de Galicia — SIOTUGA',
        'origen': 'inventario_planeamiento_municipal', 'siotuga_id': identifier,
        'categorias_inventario': [CLASSES[c] for c in sorted(categories)],
        'fecha_aprob': source_date(item.get('fechaaddef')),
        # Preserve both publication channels rather than choosing one as generic fecha.
        'fecha_publicacion_bop': source_date(item.get('fechabop')),
        'fecha_publicacion_dog': source_date(item.get('fechadog')),
        'fecha_publicacion_normativa_bop': source_date(item.get('fechanormativabop')),
        'incidencias_juridicas': detail.get('incidencias_iuris'),
        'documentos': list(documents.values()),
        'provenance': {'municipal_source': MUNICIPAL_SOURCE, 'inventory_endpoint': QUERY,
                       'inventory_parameters': {'id': '27016', 'idclase': sorted(categories)},
                       'detail_endpoint': DETAIL, 'detail_parameters': {'iddoc': identifier, 'idp': '0', 'lang': 'gl_ES'}},
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class ChantadaAyuntamientoAdapter(AyuntamientoAdapter):
    def _capture(self, name, content):
        if self.config.get('evidence_dir'):
            folder = Path(self.config['evidence_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(content)

    @staticmethod
    def _write(path, records):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
        tmp.replace(path)
        return {'status': 'ok', 'rows': len(records)}

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-chantada/1.0 (public planning inventory)'

            def fetch(url, data=None, capture=''):
                response = (session.get(url, timeout=45) if data is None else
                            session.post(url, data=data, timeout=45))
                response.raise_for_status()
                if urlparse(response.url).hostname != urlparse(url).hostname:
                    raise ValueError('Unexpected source redirect')
                self._capture(capture, response.content)
                return response

            municipal = fetch(MUNICIPAL_SOURCE, capture='municipal-pxou.html')
            soup = BeautifulSoup(municipal.content, 'html.parser')
            if not any('idconcello=27016' in a['href'] and 'siotuga' in a['href']
                       for a in soup.select('a[href]')):
                raise ValueError('Municipal SIOTUGA provenance link missing')
            response = fetch(INVENTORY, capture='inventory.html')
            soup = BeautifulSoup(response.content, 'html.parser')
            # Anonymous public form nonce, obtained anew; no login or credentials.
            nonce = soup.select_one('input#token')
            if not nonce or not nonce.get('value'):
                raise ValueError('Public inventory form changed')
            common = {'token': nonce['value']}
            items, groups = {}, {}
            for category in CLASSES:
                response = fetch(QUERY, {**common, 'id': '27016', 'idclase': category},
                                 f'class-{category}.json')
                for item in parse_inventory(response.json(), category):
                    identifier = str(item['id'])
                    if identifier in items and items[identifier] != item:
                        raise ValueError('Conflicting instrument across categories')
                    items[identifier] = item
                    groups.setdefault(identifier, set()).add(category)
            if not items:
                raise ValueError('No planning instruments in current municipal inventory')
            records = []
            for identifier, item in items.items():
                response = fetch(DETAIL, {**common, 'iddoc': identifier, 'idp': '0', 'lang': 'gl_ES'},
                                 f'detail-{identifier}.json')
                detail = response.json()
                if not isinstance(detail, dict):
                    raise ValueError('Invalid instrument detail')
                records.append(parse_instrument(item, detail, groups[identifier]))
        return {**self._write(out_jsonl, records), 'coverage': 'SIOTUGA municipal planning categories 14,13,16,18',
                'source_urls': [MUNICIPAL_SOURCE, INVENTORY, QUERY, DETAIL]}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot; no date filter or hidden pagination limit.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled',
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
