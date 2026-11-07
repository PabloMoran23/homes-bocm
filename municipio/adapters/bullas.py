"""PGMO document package linked by Bullas' official Urbanismo page."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.bullas.es/areas-municipales/urbanismo/'


def parse_inventory(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    links = {}
    for a in soup.select('a[href]'):
        title = a.get_text(' ', strip=True)
        if re.fullmatch(r'APROBACIÓN PROVISIONAL PGMO\.?', title, re.I):
            target = urljoin(url, a['href'])
            if urlparse(target).hostname not in {'bit.ly', 'drive.google.com'}:
                raise ValueError('Unreviewed PGMO document host')
            links[target] = title
    if len(links) != 1:
        raise ValueError('Expected one official PGMO package link')
    target, label = next(iter(links.items()))
    return {
        'id': 'bullas-pgmo', 'municipio': 'Bullas', 'codigo_ine': '30012',
        'provincia': 'Murcia', 'titulo': 'Plan General Municipal de Ordenación de Bullas',
        'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
        'origen': 'inventario_urbanismo', 'url': url, 'inventory_url': url,
        'enlace_paquete': target, 'rotulo_fuente': label,
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


def parse_folder(html: str, url: str) -> list[dict]:
    """Require the entire declared table; fail on lazy loading/pagination."""
    soup = BeautifulSoup(html, 'html.parser')
    grid = soup.select_one('table[role="grid"][aria-rowcount]')
    if grid is None:
        raise ValueError('Drive public folder table missing')
    for a in soup.select('a[rel~=next], button[aria-label]'):
        if a.get('rel') or re.search(r'next|siguiente|más elementos|load more', a.get('aria-label', ''), re.I):
            raise ValueError('Paginated folder requires review')
    rows = grid.select('tr[data-id]')
    if len(rows) != int(grid['aria-rowcount']) or len(rows) >= 50:
        raise ValueError('Incomplete or potentially paginated Drive folder')
    docs = {}
    for row in rows:
        name = row.select_one('strong')
        ident = row['data-id']
        if name is None or not re.fullmatch(r'[\w-]+', ident, re.ASCII):
            raise ValueError('Unrecognized Drive item')
        title = name.get_text(' ', strip=True)
        is_pdf = title.lower().endswith('.pdf')
        # This package contains PDF files and folders only; reject new formats.
        if not is_pdf and row.select_one('svg title') is not None:
            raise ValueError('Unsupported document format')
        target = (f'https://drive.google.com/file/d/{ident}/view' if is_pdf
                  else f'https://drive.google.com/drive/folders/{ident}')
        docs[target] = {'titulo': title, 'url': target,
                        'tipo': 'pdf' if is_pdf else 'carpeta', 'inventory_url': url}
    if not docs:
        raise ValueError('Empty PGMO folder')
    return list(docs.values())


class BullasAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url: str, name: str):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'Mozilla/5.0 (municipal-document-inventory)'})
        response.raise_for_status()
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / f'{name}.html').write_text(response.text, encoding='utf-8')
        return response

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl: Path):
        page = self._fetch(SOURCE, 'urbanismo-live')
        if urlparse(page.url).hostname not in {'bullas.es', 'www.bullas.es'}:
            raise ValueError('Unexpected municipal redirect')
        record = parse_inventory(page.text, page.url)
        root = self._fetch(record['enlace_paquete'], 'pgmo-live')
        if not re.fullmatch(r'/drive/folders/[\w-]+', urlparse(root.url).path) or urlparse(root.url).hostname != 'drive.google.com':
            raise ValueError('Expected public PGMO folder')
        record['paquete_url'] = root.url
        docs = {}
        pending = [(root.url, root.text)]
        visited = set()
        while pending:
            url, html = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Folder traversal limit exceeded; no partial output written')
            visited.add(url)
            for doc in parse_folder(html, url):
                if doc['url'] in docs:
                    continue
                docs[doc['url']] = doc
                if doc['tipo'] == 'carpeta':
                    child = self._fetch(doc['url'], 'folder-' + doc['url'].rsplit('/', 1)[-1])
                    if child.url != doc['url']:
                        raise ValueError('Unexpected child folder redirect')
                    pending.append((child.url, child.text))
        record['documentos'] = list(docs.values())
        record['coverage'] = 'Paquete PGMO enlazado en Urbanismo, incluidas subcarpetas; no inventario municipal exhaustivo.'
        return {**self._write(out_jsonl, [record]), 'documents': len(docs), 'folders': len(visited)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
