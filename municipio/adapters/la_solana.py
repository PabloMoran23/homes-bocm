"""Current La Solana transparency inventories; one row per planning instrument."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.lasolana.es'
SOURCES = (
    BASE + '/portal-de-transparencia-instrumentos-de-desarrollo-y-complementarios/',
    BASE + '/portal-de-transparencia-plan-general-de-ordenacion-urbana-pgou/',
)
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def normalise(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def parse_inventory(html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    contents = soup.select('.als-post-content')
    if len(contents) != 1:
        raise ValueError('Expected one municipal inventory content container')
    content = contents[0]
    if (soup.select('link[rel~=next], .page-links, .pagination, .nav-links')
            or content.select('a[rel~=next]')):
        raise ValueError('Pagination detected; review traversal before extracting')
    for a in content.select('a[href]'):
        if normalise(a.get_text(' ', strip=True)) in {'siguiente', 'next', 'ver mas'}:
            raise ValueError('Possible inventory continuation')
    publication = None
    times = soup.select('.elementor-post-info__item--type-date time')
    if len(times) == 1:
        match = re.fullmatch(r'(\d{1,2}) de (\w+) de (\d{4})', times[0].get_text(strip=True))
        if match and match[2] in MONTHS:
            publication = date(int(match[3]), MONTHS.index(match[2]) + 1, int(match[1])).isoformat()
    instruments = {}
    plans = []
    for a in content.select('a[href]'):
        target = urljoin(source_url, a['href'])
        if not urlparse(target).path.lower().endswith('.pdf'):
            continue
        if urlparse(target).hostname != 'www.lasolana.es':
            raise ValueError('Unexpected document host')
        title = a.get_text(' ', strip=True)
        key = normalise(title)
        document = {'titulo': title, 'url': target, 'source_url': source_url}
        if key.startswith('plano '):
            plans.append(document)
            continue
        if not (key.startswith(('plan de ordenacion municipal', 'modificacion puntual', 'segunda modificacion'))):
            raise ValueError('Unrecognised inventory document: ' + title)
        instruments.setdefault(key, {'titulo': title, 'documentos': []})['documentos'].append(document)
    # The separately listed drawing belongs to the ordinance amendment, not the POM amendment.
    for document in plans:
        candidates = [v for k, v in instruments.items()
                      if k.startswith('segunda modificacion puntual de las ordenanzas municipales de edificacion')
                      and normalise(document['titulo']) == 'plano ' + k.removeprefix('segunda ')]
        if len(candidates) != 1:
            raise ValueError('Drawing cannot be assigned uniquely to an instrument')
        candidates[0]['documentos'].append(document)
    rows = []
    for key, instrument in instruments.items():
        row = {
            'id': 'la-solana-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'La Solana', 'codigo_ine': '13079', 'provincia': 'Ciudad Real',
            **instrument, 'tipo': 'planeamiento_urbanistico',
            'url': instrument['documentos'][0]['url'], 'inventory_url': source_url,
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'publication_ready': False, 'geometry_status': 'unavailable',
        }
        if publication:
            row['fecha_publicacion'] = publication
            row['fecha_publicacion_provenance'] = {'url': source_url, 'scope': 'pagina_del_inventario'}
        rows.append(row)
    if not rows:
        raise ValueError('Inventory has no supported planning instruments')
    return rows


class LaSolanaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = {}
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-la-solana/1.0 (public planning inventory)'
            for source in SOURCES:
                response = session.get(source, timeout=45)
                response.raise_for_status()
                if response.url.rstrip('/') != source.rstrip('/'):
                    raise ValueError('Unexpected inventory redirect')
                for row in parse_inventory(response.text, source):
                    if row['id'] in rows:
                        raise ValueError('Overlapping inventories require explicit consolidation')
                    rows[row['id']] = row
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows.values()), encoding='utf-8')
        temporary.replace(output)
        return {'count': len(rows), 'written': len(rows), 'source_urls': list(SOURCES),
                'coverage': 'current_transparency_planning_inventories', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
