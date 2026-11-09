"""Medio Cudeyo planning inventory, linked by the municipal transparency portal."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL_SOURCE = 'https://transparencia.mediocudeyo.es/normativa/normativa-sobre-urbanismo-y-medio-ambiente/'
SOURCE = 'https://aplicacionesweb.cantabria.es/aucan/public/zona/costacentral/mediocudeyo'
INVENTORY = 'https://aplicacionesweb.cantabria.es/aucan/public/planes?idMunicipio=42'
DOWNLOAD = 'https://aplicacionesweb.cantabria.es/aucan/public/documento/download.do/'
LIMITATIONS = [
    'Only the AUCAN Actual branch; No Vigente historical planning is excluded.',
    'Amendments are separate instruments linked to their parent; supporting documents are grouped.',
    'Dates are the agreement and BOC publication in inventory headings, not website upload dates.',
    'Actual is an archive classification, not an independent certification of legal validity; cancellation notices are retained.',
    'No public works inventory or granted licences extracted. No verified vector geometry or coordinates.',
    'Document links retained in full; binary documents are not all downloaded or text-parsed.',
    'The shared entity policy marks these records pending (no verified expediente number); they are not publication-ready.',
]


def _children(node: dict) -> list[dict]:
    children = node.get('nodes')
    if children is None:
        return []
    if not isinstance(children, list):
        raise ValueError('Unexpected AUCAN children (possible pagination/schema change)')
    return children


def _validate(nodes: list[dict]) -> None:
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get('text'), str):
            raise ValueError('Invalid AUCAN node')
        if any(k in node for k in ('next', 'nextPage', 'hasMore', 'pagination')):
            raise ValueError('AUCAN pagination requires review')
        children = _children(node)
        if node.get('type') == 'folder':
            if node.get('id') is not None:
                raise ValueError('Unexpected document-bearing folder')
        elif type(node.get('id')) is not int or node['id'] <= 0 or children:
            raise ValueError('Invalid AUCAN document identifier')
        _validate(children)


def _documents(nodes: list[dict], path: tuple[str, ...] = ()) -> list[dict]:
    docs = {}
    for node in nodes:
        route = (*path, node['text'].strip())
        if node.get('type') == 'folder':
            for doc in _documents(_children(node), route):
                key = doc['id_documento']
                if key in docs:
                    docs[key]['rutas'].extend(p for p in doc['rutas'] if p not in docs[key]['rutas'])
                else:
                    docs[key] = doc
        else:
            key = node['id']
            if key not in docs:
                docs[key] = {'id_documento': key, 'titulo': node['text'].strip(),
                             'url': DOWNLOAD + str(key), 'rutas': []}
            if list(route) not in docs[key]['rutas']:
                docs[key]['rutas'].append(list(route))
    return list(docs.values())


def _heading_date(title: str, label: str) -> str | None:
    match = re.search(label + r'\s+(\d{2}/\d{2}/\d{4})', title)
    return datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None


def parse_inventory(payload: Any) -> list[dict]:
    """Parse the complete tree, never a sliced first page or standalone news item."""
    if not isinstance(payload, list) or not payload:
        raise ValueError('AUCAN must return a complete nonempty tree array')
    _validate(payload)
    if {n['text'] for n in payload} - {'Actual', 'No Vigente'}:
        raise ValueError('Unknown AUCAN inventory branch')
    current = [n for n in payload if n['text'] == 'Actual']
    if len(current) != 1:
        raise ValueError('Missing or ambiguous Actual branch')
    rows = {}

    def instrument(node: dict, category: str, parent: str | None = None) -> None:
        title = node['text'].strip()
        if not re.match(r'^(PGOU |Plan Parcial |Catálogo de Edificaciones |Modificación Puntual )', title):
            raise ValueError('Unreviewed planning instrument: ' + title)
        sections = _children(node)
        # Amendments have their own heading and dates. Never duplicate their files
        # as a second project or mix their agreement date into the parent plan.
        main = [n for n in sections if n['text'] != 'Modificaciones puntuales']
        docs = _documents(main, (title,))
        if not docs:
            raise ValueError('Planning instrument has no documents: ' + title)
        identity = re.sub(r'\s*\((?:CROTU|Ayto\.)\s+\d{2}/\d{2}/\d{4};\s*BOC\s+\d{2}/\d{2}/\d{4}\)\s*$', '', title)
        key = 'medio-cudeyo-proy-' + hashlib.sha256((str(parent or '') + '/' + identity).encode()).hexdigest()[:16]
        if key in rows:
            raise ValueError('Duplicate planning instrument: ' + identity)
        approval = _heading_date(title, r'(?:CROTU|Ayto\.)')
        publication = _heading_date(title, 'BOC')
        if not approval or not publication:
            raise ValueError('Unreviewed instrument heading/date semantics: ' + title)
        notices = sorted({part for doc in docs for route in doc['rutas'] for part in route
                          if any(word in part.upper() for word in ('ANULACI', 'PENDIENTE'))})
        definitive = any(n['text'] == 'Aprobación definitiva' for n in main)
        rows[key] = {
            'id': key, 'municipio': 'Medio Cudeyo', 'codigo_ine': '39042',
            'provincia': 'Cantabria', 'titulo': title,
            'tipo': 'modificacion_planeamiento' if parent else 'planeamiento_urbanistico',
            'categoria_fuente': category, 'clasificacion_archivo': 'Actual',
            'fase': 'aprobación definitiva' if definitive else None,
            'fecha_publicacion': publication, 'fecha_acuerdo': approval,
            'fecha_aprob': approval if definitive else None, 'fecha': None,
            'procedencia_fechas': 'Encabezado del instrumento AUCAN: CROTU/Ayto. y BOC',
            'url': SOURCE, 'source': 'gobierno_cantabria', 'origen': 'aucan_planeamiento_municipal',
            'source_urls': [MUNICIPAL_SOURCE, SOURCE, INVENTORY],
            'documentos': docs, 'instrumento_padre_id': parent, 'advertencias_fuente': notices,
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False,
        }
        for section in sections:
            if section['text'] == 'Modificaciones puntuales':
                for amendment in _children(section):
                    instrument(amendment, category, key)

    for category in _children(current[0]):
        if category['text'] not in {'Planeamiento general', 'Planeamiento desarrollo', 'Otros documentos'}:
            raise ValueError('Unknown AUCAN planning category')
        for node in _children(category):
            instrument(node, category['text'])
    if not rows:
        raise ValueError('No current planning instruments found')
    return list(rows.values())


class MedioCudeyoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        tmp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        captures = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-medio-cudeyo/1.0'

            def fetch(url: str, name: str):
                response = session.get(url, timeout=(15, 60))
                response.raise_for_status()
                if captures:
                    (captures / name).write_bytes(response.content)
                return response

            municipal = BeautifulSoup(fetch(MUNICIPAL_SOURCE, 'municipal-source.html').content, 'html.parser')
            if not any(a['href'].split('#')[0] == SOURCE for a in municipal.select('a[href]')):
                raise ValueError('Municipal link to AUCAN inventory missing')
            html = fetch(SOURCE, 'aucan-source.html').text
            soup = BeautifulSoup(html, 'html.parser')
            if not soup.find('h1', string=re.compile(r'^\s*Medio Cudeyo\s*$')):
                raise ValueError('AUCAN municipality mismatch')
            if not re.search(r"\$\.get\('/aucan/public/planes',\s*\{\s*idMunicipio:\s*'42'\s*\}", html):
                raise ValueError('AUCAN tree endpoint changed')
            rows = parse_inventory(fetch(INVENTORY, 'aucan-inventory.json').json())
        return {**self._write(out_jsonl, rows), 'source_urls': [MUNICIPAL_SOURCE, SOURCE, INVENTORY],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete refresh of the current branch; no historical/incremental claims.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**self._write(out_jsonl, []), 'status': 'disabled',
                'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
