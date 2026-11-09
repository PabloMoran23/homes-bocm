"""Snapshot of the municipality's public planning-document inventory."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'laalmunia.sedelectronica.es'
SOURCE = f'https://{HOST}/transparency/8eb6378f-9b57-4d4a-89e9-45deb4b01174/'
LIMITATIONS = [
    'Partial coverage: public planning inventory only; not all municipal works or historical proceedings.',
    'Dates and current legal phase are not established from document labels; all record dates and fase are null.',
    'Document links are retained as published; PDF contents and externally hosted Google Drive folders are not enumerated.',
    'Empty folders are reported but do not become instruments; no granted-licence register verified.',
    'No verified coordinates or geometry; publication_ready is false.',
]


def _official_folder(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname == HOST and bool(
        re.fullmatch(r'/transparency/[0-9a-f-]{36}/', parsed.path))


def parse_inventory(html: str, url: str) -> dict[str, Any]:
    """Parse one complete folder; Wicket action URLs must use the same session."""
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.TransparencyListPanel')
    if table is None or not _official_folder(url):
        raise ValueError('Missing official planning inventory table')
    # This source is a folder tree, not a paginated news feed. Refuse any
    # introduced pagination instead of returning only the first page.
    if soup.select('.navigator, .pagination, .paging, [rel="next"], .next'):
        raise ValueError('Pagination requires review; refusing incomplete inventory')
    folders, documents = [], []
    for cell in table.select('td.class_name'):
        folder = cell.select_one('a.exp')
        if folder:
            label = folder.get_text(' ', strip=True)
            count = re.search(r'\(\s*(\d+)\s*\)\s*$', label)
            action = re.search(r"wicketAjaxGet\('([^']+)'", folder.get('onclick', ''))
            if not count or not action:
                raise ValueError('Unrecognized folder count or Wicket action')
            action_url = urljoin(url, action[1])
            if urlparse(action_url).hostname != HOST:
                raise ValueError('Unexpected folder action host')
            folders.append({'titulo': label[:count.start()].strip(),
                            'count': int(count[1]), 'action_url': action_url})
            continue
        anchors = cell.select('a[href]')
        if len(anchors) != 1:
            raise ValueError('Unrecognized inventory document row')
        a = anchors[0]
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        if not a.get_text(strip=True) or parsed.scheme != 'https' or not (
            (parsed.hostname == HOST and parsed.path.startswith('/preview-document/'))
            or (parsed.hostname == 'drive.google.com' and parsed.path.startswith(('/file/d/', '/drive/folders/')))
        ):
            raise ValueError('Unrecognized document provenance')
        documents.append({'titulo': a.get_text(' ', strip=True), 'url': target,
                          'inventory_url': url,
                          'hosting': 'municipal_sede' if parsed.hostname == HOST else 'external_link_published_by_municipality'})
    return {'folders': folders, 'documents': documents}


def build_record(title: str, url: str, documents: list[dict[str, Any]], parents: list[str]) -> dict[str, Any]:
    if not documents or not re.search(r'PLAN GENERAL|PLAN PARCIAL|MODIFICACI[ÓO]N|MODIFCACIÓN', title, re.I):
        raise ValueError('Documents do not identify a planning instrument')
    return {
        'id': 'la-almunia-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'La Almunia de Doña Godina', 'codigo_ine': '50025', 'provincia': 'Zaragoza',
        'titulo': title, 'tipo': 'instrumento de planeamiento urbanístico',
        'url': url, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
        'origen': 'inventario_municipal_planeamiento', 'ruta_inventario': parents + [title],
        'documentos': documents, 'fecha': None, 'fecha_publicacion': None,
        'fecha_acuerdo': None, 'fecha_aprob': None, 'fase': None,
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'unavailable',
    }


class LaAlmuniaDeDonaGodinaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or f'https://{HOST}')

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows, visited, empty = [], set(), []
        captures = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-la-almunia/1.0'

            def fetch(url):
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if not _official_folder(response.url):
                    raise ValueError('Unexpected inventory redirect')
                if captures:
                    key = urlparse(response.url).path.rstrip('/').split('/')[-1]
                    (captures / f'{key}.html').write_text(response.text, encoding='utf-8')
                return response

            def visit(response, title, parents, expected=None):
                url = response.url
                if url in visited:
                    raise ValueError('Repeated folder/cycle in inventory')
                visited.add(url)
                page = parse_inventory(response.text, url)
                docs = page['documents']
                if docs:
                    rows.append(build_record(title, url, docs, parents))
                total = len(docs)
                for folder in page['folders']:
                    child = fetch(folder['action_url'])
                    total += visit(child, folder['titulo'], parents + [title], folder['count'])
                if expected is not None and total != expected:
                    raise ValueError(f'Incomplete inventory at {url}: expected {expected}, found {total}')
                if not total:
                    empty.append({'titulo': title, 'url': url})
                return total

            count = visit(fetch(SOURCE), 'Planes urbanísticos', [])
        if not rows:
            raise ValueError('No usable planning instruments in live inventory')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'document_links': count,
                'source_urls': sorted(visited), 'empty_folders': empty,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete snapshot: no date watermark, so undated additions are retained.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
