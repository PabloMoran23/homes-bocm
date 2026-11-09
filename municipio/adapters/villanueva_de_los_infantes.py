"""Municipal planning table: one record per instrument/version, with its documents."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://infantes.org/planes-de-ordenacion-urbanistica-instrumentos-de-apoyo-y-ordenanzas-de-edificacion/'
TITLE = re.compile(r'^(?:Revisión normas subsidiarias|Catálogo de bienes protegidos|M\.P\.?\s*N[º°o]|Texto refundido.*NN\.SS\.|Plan Parcial)(?=\s|$)', re.I)
HEADERS = ['Instrumentos de planeamiento', 'Fecha de publicación', 'Normativa', 'Planos']


def clean(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    # This is a full static table today. Fail if it becomes paginated, rather
    # than returning just the first page. Do not impose a record limit.
    if soup.select('a[rel~=next], .pagination, .page-numbers, .uael-table-pagination, .dataTables_paginate'):
        raise ValueError('Pagination detected; review traversal before extraction')
    tables = [t for t in soup.select('table') if [clean(h) for h in t.select('thead th')] == HEADERS]
    if len(tables) != 1:
        raise ValueError('Expected one municipal planning inventory table')
    table = tables[0]
    if any(table.get(k, 'no') != 'no' for k in ('data-show-entry', 'data-searchable')):
        raise ValueError('Table now has dynamic controls; review completeness')
    records = {}
    for tr in table.select('tbody tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 4:
            raise ValueError('Unexpected planning row structure')
        title = clean(cells[0])
        if not TITLE.match(title):
            continue  # Heritage declaration and standalone ordinances are not projects.
        docs = {}
        for i, cell in enumerate(cells):
            for a in cell.select('a[href]'):
                target = urljoin(url, a['href'])
                parsed = urlparse(target)
                if parsed.scheme != 'https' or parsed.hostname != 'infantes.org' or not parsed.path.startswith('/wp-content/uploads/'):
                    raise ValueError(f'Unexpected document URL: {target}')
                doc = docs.setdefault(target, {'url': target, 'referencias': []})
                reference = {'columna': HEADERS[i], 'texto': clean(a)}
                if reference not in doc['referencias']:
                    doc['referencias'].append(reference)
        if not docs:
            raise ValueError(f'Instrument lacks source documents: {title}')
        # Some CMS cells are displaced: the consolidated text's publication
        # reference sits in Planos. Scan bibliographic references, not title dates.
        references = [clean(c) for c in cells[1:] if re.search(r'\b(?:DOCM|BOP|BOE)\b', clean(c))]
        dates = sorted({datetime.strptime(d, '%d/%m/%Y').date().isoformat()
                        for ref in references for d in re.findall(r'\b\d{2}/\d{2}/\d{4}\b', ref)})
        key = 'villanueva-de-los-infantes-plan-' + hashlib.sha256(title.casefold().encode()).hexdigest()[:16]
        record = {
            'id': key, 'municipio': 'Villanueva de los Infantes',
            'codigo_ine': '13093', 'provincia': 'Ciudad Real', 'titulo': title,
            'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
            'origen': 'inventario_planeamiento', 'url': next(iter(docs)),
            'inventory_url': url, 'documentos': list(docs.values()),
            'celdas_fuente': dict(zip(HEADERS, map(clean, cells))),
            'referencias_publicacion': references, 'fechas_publicacion': dates,
            'publication_ready': False, 'geometry_status': 'unavailable',
        }
        if len(dates) == 1:
            record['fecha_publicacion'] = dates[0]
        if 'DEROGADA' in title.upper():
            record['vigencia_segun_inventario'] = 'derogada'
        if key in records and records[key] != record:
            raise ValueError('Conflicting duplicate instrument rows')
        records[key] = record
    if not records:
        raise ValueError('No supported planning instruments found')
    return list(records.values())


class VillanuevaDeLosInfantesAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={'User-Agent': 'municipal-planning-inventory/1.0'})
        response.raise_for_status()
        if response.url != SOURCE:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'planeamiento.html').write_text(response.text, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE],
                'coverage': 'current_planning_table_including_explicit_historical_version',
                'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh: no chronological cutoff; CMS ordering is not incremental.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
