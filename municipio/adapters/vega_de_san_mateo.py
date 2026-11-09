"""Municipal document inventory: one record per instrument, not per plan sheet."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.vegadesanmateo.es/urbanismo/documentos-urbanismo'
HOSTS = {'www.vegadesanmateo.es', 'vegadesanmateo.es'}


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('article .field--name-body')
    if body is None:
        raise ValueError('Municipal planning body missing')
    # This is a single-page inventory. Refuse changed pagination rather than
    # reporting only the first page as a complete inventory.
    if soup.select('a[rel~=next], .pager a[href], .pagination a[href]'):
        raise ValueError('Pagination detected: crawler must be reviewed')
    for a in body.select('a[href]'):
        if re.search(r'[?&]page=', a['href']) or a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', '»', '›'}:
            raise ValueError('Pagination detected: crawler must be reviewed')
    records = []
    current = None
    seen = set()
    for table in body.select('table'):
        header = table.select_one('th[colspan]')
        if header is None:
            if table.select('a[href]'):
                raise ValueError('Document table without section heading')
            continue
        section = header.get_text(' ', strip=True)
        if re.match(r'^(TEXTO REFUNDIDO DE LA ADAPTACIÓN BÁSICA DEL P\.G\.O\.|PLAN PARCIAL\s+\S)', section, re.I):
            key = hashlib.sha256(section.casefold().encode()).hexdigest()[:16]
            current = {
                'id': 'vega-de-san-mateo-plan-' + key,
                'municipio': 'Vega de San Mateo', 'codigo_ine': '35033',
                'provincia': 'Las Palmas', 'titulo': section,
                'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
                'origen': 'inventario_documental_municipal', 'inventory_url': url,
                'publication_ready': False, 'geometry_status': 'unavailable',
                'documentos': [],
            }
            records.append(current)
        elif not re.match(r'^(1000-|2000-|5000-|PLANOS DE INFORMACIÓN$|PLANOS DE ORDENACIÓN$)', section, re.I):
            # Unknown tables may introduce another instrument; do not attach
            # their documents to the preceding plan.
            raise ValueError('Unrecognised inventory section: ' + section)
        if current is None:
            raise ValueError('Document section precedes instrument')
        for tr in table.select('tr'):
            cells = tr.find_all('td', recursive=False)
            for a in tr.select('a[href]'):
                target = urljoin(url, a['href'])
                parsed = urlparse(target)
                if parsed.hostname not in HOSTS or parsed.scheme not in {'http', 'https'} or not parsed.path.lower().endswith('.pdf'):
                    raise ValueError('Unexpected planning document URL: ' + target)
                if not cells or not cells[0].get_text(' ', strip=True):
                    raise ValueError('Document without descriptive name')
                # Preserve original municipal URLs, including the HTTP scheme.
                identity = (current['id'], target)
                if identity in seen:
                    continue
                seen.add(identity)
                current['documentos'].append({
                    'titulo': cells[0].get_text(' ', strip=True),
                    'seccion': section, 'url': target, 'source_url': url,
                })
    if not records or any(not row['documentos'] for row in records):
        raise ValueError('No complete named instruments in municipal inventory')
    for row in records:
        row['url'] = row['documentos'][0]['url']
    return records


def _write(path: Path, rows: list[dict]) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    temporary.replace(path)
    return {'count': len(rows), 'written': len(rows)}


class VegaDeSanMateoAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'municipal-document-inventory/1.0',
        })
        response.raise_for_status()
        if urlparse(response.url).hostname not in HOSTS:
            raise ValueError('Inventory redirected outside municipal domain')
        rows = parse_inventory(response.text, response.url)
        return {**_write(out_jsonl, rows), 'coverage': 'municipal_document_inventory_only',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**_write(out_jsonl, []), 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
