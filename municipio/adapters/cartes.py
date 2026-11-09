"""Cartes planning instruments from the official Cantabria AUCAN document tree."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

PAGE = 'https://aplicacionesweb.cantabria.es/aucan/public/zona/costacentral/cartes'
SOURCE = 'https://aplicacionesweb.cantabria.es/aucan/public/planes?idMunicipio=18'
DOWNLOAD = 'https://aplicacionesweb.cantabria.es/aucan/public/documento/download.do/'
LIMITATIONS = [
    'Partial municipal coverage: AUCAN planning archive only; not works or granted licences.',
    'Actual is the archive classification, not independent verification of legal validity.',
    'Unlabelled document dates are retained verbatim, not interpreted as approval/publication.',
    'No verified vector geometry or coordinates; publication_ready is false.',
]


def _labelled_date(title, label):
    match = re.search(label + r'\s+(\d{2}/\d{2}/\d{4})', title)
    return datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None


def parse_inventory(tree):
    """Consume the entire nested response; never flatten individual PDFs into projects."""
    if not isinstance(tree, list) or not tree:
        raise ValueError('Expected complete AUCAN tree array, not a paginated envelope')

    def validate(nodes):
        if not isinstance(nodes, list):
            raise ValueError('Invalid child list')
        for node in nodes:
            if not isinstance(node, dict) or not isinstance(node.get('text'), str):
                raise ValueError('Invalid AUCAN node')
            if any(k in node for k in ('next', 'nextPage', 'hasMore', 'lazyLoad', 'totalPages')):
                raise ValueError('Pagination/lazy loading requires crawler review')
            if node.get('type') == 'folder':
                validate(node.get('nodes') or [])
            elif type(node.get('id')) is not int or node['id'] <= 0 or node.get('nodes'):
                raise ValueError('Invalid document leaf')
    validate(tree)
    if any(n['text'] not in {'Actual', 'En Trámite', 'No Vigente'} for n in tree):
        raise ValueError('Unreviewed archive classification')

    rows = {}

    def emit(instrument, ancestry):
        docs = {}
        modifications = []

        def collect(node, path):
            children = node.get('nodes') or []
            if node.get('type') != 'folder':
                url = DOWNLOAD + str(node['id'])
                docs.setdefault(url, {'id': node['id'], 'titulo': node['text'], 'url': url,
                                      'ruta': path, 'inventory_url': SOURCE})
                return
            if node['text'].casefold() == 'modificaciones puntuales':
                modifications.extend((child, path + [node['text']]) for child in children)
                return
            for child in children:
                collect(child, path + [node['text']])

        collect(instrument, ancestry)
        title = instrument['text']
        if docs:
            if not re.match(r'^(Normas Subsidiarias|Plan Especial|Catálogo de Edificaciones|Modificación Puntual)\b', title, re.I):
                raise ValueError('Unreviewed instrument: ' + title)
            identity = ' / '.join(ancestry + [title])
            key = 'cartes-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16]
            if key in rows:
                raise ValueError('Duplicate instrument path')
            definitive = any((child.get('text') or '').casefold() == 'aprobación definitiva'
                             for child in instrument.get('nodes') or [])
            rows[key] = {
                'id': key, 'municipio': 'Cartes', 'codigo_ine': '39018', 'provincia': 'Cantabria',
                'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'fase': 'aprobación definitiva' if definitive else None,
                'clasificacion_archivo': ancestry[0], 'ruta_inventario': ancestry,
                'fecha': None, 'fecha_acuerdo': _labelled_date(title, r'(?:CRU|CROTU|Ayto\.|Cons\. Gob\.)'),
                'fecha_publicacion': _labelled_date(title, 'BOC'), 'fecha_aprob': None,
                'url': PAGE, 'inventory_url': SOURCE, 'url_documento': next(iter(docs)),
                'documentos': list(docs.values()), 'source': 'gobierno_cantabria',
                'origen': 'aucan_planeamiento_municipal',
                'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                'publication_ready': False, 'limitaciones': LIMITATIONS,
            }
        for child, path in modifications:
            emit(child, path)

    for classification in tree:
        for category in classification.get('nodes') or []:
            if category.get('type') != 'folder':
                raise ValueError('Unexpected category document')
            for instrument in category.get('nodes') or []:
                emit(instrument, [classification['text'], category['text']])
    if not rows:
        raise ValueError('No documented planning instruments found')
    return list(rows.values())


class CartesAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        capture = self.config.get('capture_dir')
        headers = {'User-Agent': 'municipio-cartes/1.0 (public planning inventory)'}

        def fetch(url, filename):
            response = requests.get(url, timeout=40, headers=headers)
            response.raise_for_status()
            if response.url != url:
                raise ValueError('Unexpected official-source redirect')
            if len(response.content) > 5_000_000:
                raise ValueError('Source size exceeds reviewed bound')
            if capture:
                path = Path(capture)
                path.mkdir(parents=True, exist_ok=True)
                (path / filename).write_bytes(response.content)
            return response

        page = fetch(PAGE, 'aucan-cartes.html').text
        soup = BeautifulSoup(page, 'html.parser')
        if not any(h.get_text(strip=True) == 'Cartes' for h in soup.select('h1')):
            raise ValueError('Missing Cartes municipality heading')
        if not re.search(r"idMunicipio:\s*'18'", page) or '/aucan/public/planes' not in page:
            raise ValueError('Municipality/API binding changed')
        if re.search(r'\b(?:pagination|loadMore|nextPage)\b', page, re.I):
            raise ValueError('Inventory pagination requires review')
        rows = parse_inventory(fetch(SOURCE, 'aucan-planes.json').json())
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(output)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [PAGE, SOURCE],
                'documents': sum(len(r['documentos']) for r in rows), 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # The non-paginated archive is refreshed in full, including every classification.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
