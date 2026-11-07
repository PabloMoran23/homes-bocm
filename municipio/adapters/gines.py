"""Gines: grouped planning documents from the municipal transparency inventory."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE_URL = 'https://transparencia.gines.es/es/'
LIMITATIONS = [
    'Partial coverage: only the PGOU and non-structural modifications listed in municipal transparency.',
    'Excludes the separate new PGOM website and the 2025 PGOU innovation notice.',
    'Inventory grouping does not establish current legal validity or individual granted licences.',
    'No inferred approval/publication dates, phases or coordinates; PDF contents are not parsed.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # These galleries are unpaginated today. Fail visibly if this changes.
    if soup.select('a[rel~=next], .pagination a[href], .paginacion a[href], [class*=pager] a[href]'):
        raise ValueError('Pagination detected: review inventory coverage before extraction')
    return soup


def discover_inventories(html, url=BASE_URL):
    """Select the two verified inventory categories; ignore duplicate legal-norms PGOU."""
    found = {}
    for a in _soup(html).select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        if parsed.hostname != 'transparencia.gines.es':
            continue
        path = parsed.path
        if '/indicador/' not in path:
            continue
        if 'P.G.O.U.-APROBADO-DEFINITIVAMENTE-' in path and path.endswith('2014.-00001/'):
            found['pgou'] = target
        elif path.endswith('/Modificaciones-al-P.G.O.U.-de-Gines-que-no-afectan-a-su-ordenacion-estructural./'):
            found['modificaciones'] = target
    if set(found) != {'pgou', 'modificaciones'}:
        raise ValueError('Required Gines planning inventories missing')
    return found


def parse_inventory(html, url, kind):
    soup = _soup(html)
    heading = soup.find('h1')
    title = heading.get_text(' ', strip=True) if heading else ''
    if kind not in {'pgou', 'modificaciones'}:
        raise ValueError('Unknown inventory kind')
    if ('P.G.O.U.' not in title or
            (kind == 'modificaciones' and not title.startswith('Modificaciones al'))):
        raise ValueError('Unexpected planning inventory heading')
    gallery = soup.select_one('.sg-download-gallery')
    if gallery is None:
        raise ValueError('Planning document gallery missing')
    documents = {}
    for a in gallery.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        label = a.get_text(' ', strip=True)
        if (parsed.hostname != 'transparencia.gines.es' or
                not parsed.path.startswith('/export/sites/gines/es/transparencia/.galleries/') or
                not parsed.path.lower().endswith('.pdf') or not label):
            raise ValueError('Unexpected gallery document: review source')
        documents[target] = {'titulo': label, 'url': target, 'source_url': url}
    if not documents:
        raise ValueError('Empty planning gallery')
    return {
        'id': 'gines-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Gines', 'codigo_ine': '41047', 'provincia': 'Sevilla',
        'titulo': title, 'tipo': 'instrumento de planeamiento',
        'url': url, 'inventory_url': BASE_URL, 'source': 'ayuntamiento',
        'origen': 'inventario_planeamiento', 'documentos': list(documents.values()),
        'coverage': 'municipal_document_inventory_partial',
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class GinesAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'

            def fetch(url, name):
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if urlparse(response.url).hostname != 'transparencia.gines.es':
                    raise ValueError('Unexpected inventory redirect')
                if captures:
                    folder = Path(captures)
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / name).write_bytes(response.content)
                return response.content, response.url

            html, url = fetch(BASE_URL, 'transparencia-index.html')
            inventories = discover_inventories(html, url)
            rows = []
            for kind, target in inventories.items():
                html, final_url = fetch(target, f'{kind}.html')
                rows.append(parse_inventory(html, final_url, kind))
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [BASE_URL, *inventories.values()],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Snapshot refresh, not an append-only incremental history.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
