"""Municipal planning inventory published by the Government of Cantabria (AUCAN)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://aplicacionesweb.cantabria.es'
SOURCE = BASE + '/aucan/public/zona/costacentral/marinadecudeyo'
INVENTORY = BASE + '/aucan/public/planes?idMunicipio=40'
DOWNLOAD = BASE + '/aucan/public/documento/download.do/'
METADATA = re.compile(r'\s*\((CRU|Ayto\.) (.+?); BOC (.+?)\)$')
LIMITATIONS = [
    'Cobertura del archivo AUCAN: planeamiento actual y no vigente; no es un registro de obras ni de licencias.',
    'No incluye el avance del nuevo PGOU ni documentos municipales que no figuren en AUCAN.',
    'Fechas CRU/Ayto. y BOC del inventario; fechas múltiples conservadas en bruto sin elegir una.',
    'No se verifica la vigencia jurídica ni se resuelven discrepancias entre carpeta y documento.',
    'Sin geometría vectorial verificada; no se geocodifican planos PDF.',
]


def _single_date(value: str) -> str | None:
    if not re.fullmatch(r'\d{2}/\d{2}/\d{4}', value):
        return None
    day, month, year = map(int, value.split('/'))
    return date(year, month, day).isoformat()


def parse_inventory(tree: Any) -> list[dict[str, Any]]:
    """Walk the complete nested response, assigning each document to its nearest instrument."""
    if not isinstance(tree, list) or not tree:
        raise ValueError('Expected complete AUCAN tree, not pagination metadata or empty inventory')
    rows: dict[str, dict] = {}
    doc_maps: dict[str, dict] = {}

    def walk(nodes, path=(), owner=None, ancestors=()):
        if not isinstance(nodes, list):
            raise ValueError('Invalid tree children')
        for node in nodes:
            if not isinstance(node, dict) or not isinstance(node.get('text'), str):
                raise ValueError('Invalid tree node')
            text = node['text'].strip()
            children = node.get('nodes')
            if children is not None and not isinstance(children, list):
                raise ValueError('Unexpanded or paginated children')
            branch = (*path, text)
            metadata = METADATA.search(text)
            current_owner, current_ancestors = owner, ancestors
            if node.get('type') == 'folder':
                if node.get('id') is not None or node.get('selectable') is True:
                    raise ValueError('Unexpected selectable/lazy folder')
                if metadata:
                    title = text[:metadata.start()]
                    if not re.match(r'^(Revisión del Plan General|Plan General|Modificación Puntual|Catálogo de Edificaciones|MP nº)', title):
                        raise ValueError('Unreviewed instrument type: ' + text)
                    current_ancestors = (*ancestors, title)
                    key = hashlib.sha256('/'.join(current_ancestors).encode()).hexdigest()[:20]
                    if key in rows:
                        raise ValueError('Duplicate instrument identity')
                    current_owner = key
                    rows[key] = {
                        'id': 'marina-de-cudeyo-aucan-' + key,
                        'municipio': 'Marina de Cudeyo', 'codigo_ine': '39040',
                        'provincia': 'Cantabria', 'titulo': title,
                        'tipo': 'planeamiento_urbanistico',
                        'fecha': None, 'fecha_acuerdo': _single_date(metadata[2]),
                        'fecha_publicacion': _single_date(metadata[3]),
                        'fechas_fuente': {'organo_acuerdo': metadata[1], 'acuerdo': metadata[2], 'publicacion_boc': metadata[3]},
                        'fecha_publicacion_procedencia': 'BOC indicado por AUCAN; no fecha de carga del portal',
                        'estado_fuente': branch[0], 'ruta_fuente': list(branch),
                        'titulo_fuente': text, 'instrumento_padre': rows[owner]['id'] if owner else None,
                        'url': SOURCE, 'source': 'gobierno_cantabria', 'source_dataset': INVENTORY,
                        'origen': 'archivo_planeamiento_urbanistico_aucan',
                        'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                        'geometry_status': 'unavailable', 'publication_ready': False,
                    }
                    doc_maps[key] = {}
                walk(children or [], branch, current_owner, current_ancestors)
            else:
                identifier = node.get('id')
                if (type(identifier) is not int or identifier <= 0 or children
                        or node.get('selectable') is not True or owner is None):
                    raise ValueError('Unassigned or unsupported document node')
                docs = doc_maps[owner]
                if identifier not in docs:
                    docs[identifier] = {'id_origen': identifier, 'titulo': text,
                                        'url': DOWNLOAD + str(identifier), 'rutas_fuente': []}
                docs[identifier]['rutas_fuente'].append(list(branch))

    walk(tree)
    if not rows:
        raise ValueError('No verified planning instruments')
    for key, row in rows.items():
        row['documentos'] = list(doc_maps[key].values())
        if not row['documentos']:
            raise ValueError('Instrument has no own documents: ' + row['titulo'])
    return list(rows.values())


class MarinaDeCudeyoAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, capture):
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-marina-de-cudeyo/1.0'}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 10_000_000:
                    raise ValueError('AUCAN response exceeds reviewed size; refusing truncation')
                chunks.append(chunk)
            body = b''.join(chunks)
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture).write_bytes(body)
        return body

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        html = self._fetch(SOURCE, 'aucan.html').decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.find('h1')
        if (not heading or heading.get_text(strip=True) != 'Marina de Cudeyo'
                or not re.search(r"idMunicipio:\s*'40'", html)):
            raise ValueError('Municipality identity or AUCAN inventory endpoint changed')
        # The public UI requests this entire tree once: no page/size arguments,
        # lazy loading or document-by-document inventory requests.
        tree = json.loads(self._fetch(INVENTORY, 'planes.json'))
        rows = parse_inventory(tree)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, INVENTORY],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
