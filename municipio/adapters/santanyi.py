"""Current municipal NNSS amendment inventory; one record per instrument."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://ajsantanyi.net/ca/arxius-i-documents/modificacions-puntuals-nnss'
LIMITATIONS = [
    'Partial coverage: municipal NNSS amendment inventory only, not all municipal works or planning.',
    'Document web dates are upload/display dates, not agreement or gazette publication dates.',
    'PDF/ZIP contents and legal status are not parsed; linked documents retained with provenance.',
    'No verified geometry or coordinates; publication_ready=false. Licences disabled.',
    'Separate NNSS revision archive and external MUIB register are outside this snapshot.',
]


def parse_page(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('main .layout-content')
    if content is None or content.select_one('h1') is None:
        raise ValueError('Missing municipal inventory content')
    folders, documents = [], []
    for a in content.select('.taxonomy-term-files a[href]'):
        heading = a.select_one('h3')
        if heading:
            count = re.search(r'(\d+)\s+documents?\b', a.get_text(' ', strip=True))
            if not count:
                raise ValueError('Folder without document count')
            folders.append({'url': urljoin(url, a['href']), 'title': heading.get_text(' ', strip=True),
                            'count': int(count[1])})
    for a in content.select('article a[download][href]'):
        card = a.parent
        heading = card.select_one('h3')
        if heading is None:
            raise ValueError('Download without document title')
        target = urljoin(url, a['href'])
        if urlsplit(target).hostname != 'ajsantanyi.net' or not urlsplit(target).path.startswith('/sites/cilma_santanyi/files/'):
            raise ValueError('Unexpected municipal document location')
        match = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', card.get_text(' ', strip=True))
        web_date = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None
        documents.append({'titulo': heading.get_text(' ', strip=True), 'url': target,
                          'source_page': url, 'fecha_web_documento': web_date})
    pages = {urljoin(url, a['href']) for a in soup.select('a[rel~=next][href], .pager a[href], nav[aria-label*="agin"] a[href]')}
    if not folders and not documents:
        raise ValueError('Inventory page contains no folders or documents')
    return folders, documents, sorted(pages)


def group_instruments(folders, documents):
    groups = {}
    for folder in folders.values():
        match = re.match(r'^MOD\s+(\d+)\b', folder['title'], re.I)
        if match:
            number = match[1]
            if number in groups:
                raise ValueError('Multiple folders for one amendment require explicit reconciliation')
            groups[number] = {'folder': folder, 'documents': []}
        elif not re.match(r'^BOIB\b', folder['title'], re.I):
            raise ValueError('Unrecognized folder; refusing incomplete coverage')
    if not groups:
        raise ValueError('No named NNSS amendment instruments')
    for folder_url, docs in documents.items():
        folder = folders[folder_url]
        mod = re.match(r'^MOD\s+(\d+)\b', folder['title'], re.I)
        if len({d['url'] for d in docs}) != folder['count']:
            raise ValueError('Document count differs from inventory; possible missing pagination')
        for doc in docs:
            match = re.search(r'\bMP\s+(\d+)\b', doc['titulo'], re.I)
            number = mod[1] if mod else match[1] if match else None
            if number not in groups:
                raise ValueError('Cannot associate document with an instrument')
            groups[number]['documents'].append(doc)
    rows = []
    for number, group in sorted(groups.items(), key=lambda pair: int(pair[0])):
        folder = group['folder']
        docs = {d['url']: d for d in group['documents']}
        if not docs:
            raise ValueError('Instrument without documents')
        rows.append({
            'id': 'santanyi-nnss-mp-' + number, 'municipio': 'Santanyí', 'codigo_ine': '07057',
            'provincia': 'Illes Balears', 'titulo': 'Modificació puntual ' + number + ' de les NNSS de Santanyí',
            'tipo': 'modificación puntual de normas subsidiarias', 'fase': None,
            'descripcion': folder['title'], 'numero_modificacion': number,
            'url': folder['url'], 'inventory_url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_planeamiento', 'documentos': list(docs.values()),
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'unavailable', 'limitations': LIMITATIONS,
        })
    return rows


class SantanyiAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://ajsantanyi.net')

    def _fetch(self, url):
        with requests.get(url, timeout=40, stream=True, headers={
            'User-Agent': 'municipio-santanyi/1.0'
        }) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname != 'ajsantanyi.net':
                raise ValueError('Unexpected inventory redirect')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 4_000_000:
                    raise ValueError('Inventory exceeds response size limit')
            raw = bytes(body)
        if self.config.get('capture_dir'):
            dest = Path(self.config['capture_dir'])
            dest.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha256(url.encode()).hexdigest()[:16]
            (dest / (key + '.html')).write_bytes(raw)
            (dest / (key + '.url')).write_text(url, encoding='utf-8')
        return raw.decode('utf-8')

    def backfill_proyectos(self, out_jsonl: Path):
        folders, docs, visited = {}, {}, set()

        def crawl(start):
            queue, found_folders, found_docs = [start], [], []
            while queue:
                url = queue.pop(0)
                if url in visited:
                    continue
                parts = urlsplit(url)
                if parts.hostname != 'ajsantanyi.net' or not (parts.path == urlsplit(start).path):
                    raise ValueError('Pagination leaves current inventory page')
                if len(visited) >= 200:
                    raise ValueError('Pagination safety limit reached; no partial output')
                visited.add(url)
                fs, ds, pages = parse_page(self._fetch(url), url)
                found_folders.extend(fs)
                found_docs.extend(ds)
                queue.extend(p for p in pages if p not in visited)
            return found_folders, found_docs

        discovered, root_docs = crawl(SOURCE)
        if root_docs:
            raise ValueError('Unexpected ungrouped root documents')
        for folder in discovered:
            target = folder['url']
            if not target.startswith(SOURCE + '/') or urlsplit(target).query:
                raise ValueError('Unexpected folder location')
            if target in folders and folders[target] != folder:
                raise ValueError('Conflicting folder metadata')
            folders[target] = folder
        for target in folders:
            nested, found = crawl(target)
            if nested:
                raise ValueError('Nested inventory requires explicit grouping')
            docs[target] = list({d['url']: d for d in found}.values())
        rows = group_instruments(folders, docs)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'live_records': len(rows), 'source_urls': sorted(visited),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
