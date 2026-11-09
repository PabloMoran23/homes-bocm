"""Planning instruments linked by Guitiriz's official urbanism inventory."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://concellodeguitiriz.com/urbanismo/'
LIMITATIONS = [
    'Partial municipal coverage: only the PXOM and development-planning inventory on /urbanismo/.',
    'No granted licences, procurement, news, environmental programmes or historical archive.',
    'Document links are retained; availability and contents of the entire PXOM ZIP are not verified.',
    'No approval/publication dates, legal validity, implementation phase or coordinates inferred.',
]


def normalize(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFC', value).split())


def document(anchor, source_url):
    url = urljoin(source_url, anchor['href'])
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {
        'concellodeguitiriz.com', 'www.concellodeguitiriz.com', 'www.dropbox.com', 'dropbox.com'
    }:
        raise ValueError(f'Unexpected document destination: {url}')
    if not parsed.path.lower().endswith(('.pdf', '.zip')):
        raise ValueError(f'Expected a planning document: {url}')
    return {'titulo': normalize(anchor.get_text(' ', strip=True)), 'url': url,
            'source_url': source_url, 'provenance': 'enlace_publicado_por_el_concello'}


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find('h1')
    if not heading or normalize(heading.get_text(' ', strip=True)).lower() != 'urbanismo e medio ambiente':
        raise ValueError('Missing municipal urbanism inventory heading')
    # This is a flat inventory. Fail explicitly if pagination appears; never return page one only.
    if soup.select('.pagination, .page-numbers, .nav-links, a[rel~=next]'):
        raise ValueError('Pagination detected: extend inventory traversal before extraction')
    for anchor in soup.select('a[href]'):
        if normalize(anchor.get_text(' ', strip=True)).lower() in {
            'seguinte', 'seguinte páxina', 'siguiente', 'next', 'ver máis', 'cargar máis'
        } and anchor['href'] not in {'', '#'}:
            raise ValueError('Additional inventory page detected')

    general = [a for a in soup.select('a[href]')
               if normalize(a.get_text(' ', strip=True)) == 'Acceso ao Plan Xeral']
    development = next((h for h in soup.select('h3') if normalize(h.get_text(' ', strip=True))
                        == 'Plantexamento de desenvolvemento'), None)
    if not general or development is None:
        raise ValueError('Missing general/development planning inventory')
    section = development.find_parent(class_='vc_column_container')
    if section is None:
        raise ValueError('Missing development planning container')

    instruments = [('Plan Xeral de Ordenación Municipal de Guitiriz', 'plan_xeral', general)]
    cards = section.select('.btn-caja')
    if not cards:
        raise ValueError('No development instrument cards')
    for card in cards:
        anchors = card.select('a[href]')
        if not anchors:
            raise ValueError('Development instrument without document links')
        title = normalize(anchors[0].get_text(' ', strip=True))
        if not re.match(r'^(Estudo (?:de )?Detalle|Plan (?:Especial|Parcial)|Modificaci[oó]n|Proxecto de (?:urbanizaci[oó]n|reparcelaci[oó]n))\b', title, re.I):
            raise ValueError(f'Unreviewed development instrument: {title}')
        instruments.append((title, 'planeamiento_desarrollo', anchors))

    rows = {}
    for title, kind, anchors in instruments:
        identity = normalize(title).casefold()
        key = 'guitiriz-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16]
        row = rows.setdefault(key, {
            'id': key, 'municipio': 'Guitiriz', 'codigo_ine': '27022', 'provincia': 'Lugo',
            'titulo': title, 'tipo': kind, 'url': source_url, 'inventory_url': source_url,
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento', 'documentos': [],
            'publication_ready': False, 'geometry_status': 'unavailable',
        })
        for anchor in anchors:
            doc = document(anchor, source_url)
            if doc['url'] not in {d['url'] for d in row['documentos']}:
                row['documentos'].append(doc)
    return list(rows.values())


class GuitirizAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; GuitirizPlanningInventory/1.0)'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in {'concellodeguitiriz.com', 'www.concellodeguitiriz.com'}:
            raise ValueError('Unexpected inventory redirect')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Inventory did not return HTML')
        rows = parse_inventory(response.text, response.url)
        if self.config.get('evidence_dir'):
            evidence = Path(self.config['evidence_dir'])
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / 'urbanismo.html').write_text(response.text, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [response.url],
                'coverage': 'current_general_and_development_planning_links',
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Snapshot refresh: no unsupported incremental cursor or date assumptions.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
