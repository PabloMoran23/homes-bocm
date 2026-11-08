"""Public municipal PhocaDownload planning inventory, grouped by instrument."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://villamedianadeiregua.org'
SOURCE = BASE + '/index.php/normativa/category/40-plan-general-municipal'
LIMITATIONS = [
    'Partial municipal coverage: only the published municipal PGM document tree; not a complete or current regional planning register.',
    'No granted licences, procurement notices, news or PRTR projects are extracted.',
    'Dates and legal phase are not inferred from document titles, PDF filenames or crawl time; PDF contents are not parsed.',
    'PDF and CAD links are retained, but no verified geometry is extracted; publication_ready is false.',
]


def category_id(url):
    match = re.fullmatch(r'/index.php/normativa/category/(\d+)-[^/]+', urlsplit(url).path)
    if urlsplit(url).netloc != urlsplit(BASE).netloc or not match:
        raise ValueError('Unexpected inventory URL: ' + url)
    return match[1]


def parse_page(html, url):
    """Parse only the download component, excluding menus and unrelated links."""
    category_id(url)
    soup = BeautifulSoup(html, 'html.parser')
    box = soup.select_one('#phoca-dl-category-box')
    if not box or not box.select_one('.pd-ctitle'):
        raise ValueError('Missing municipal planning inventory at ' + url)
    if category_id(url) == '40' and box.select_one('.pd-ctitle').get_text(' ', strip=True) != 'PLAN GENERAL MUNICIPAL':
        raise ValueError('Municipal PGM heading changed')
    docs = {}
    for block in box.select('.pd-filebox'):
        title = block.select_one('.pd-title')
        links = {urljoin(url, a['href']) for a in block.select('a[href]')
                 if 'download' in parse_qs(urlsplit(a['href']).query)}
        if title is None or len(links) != 1:
            raise ValueError('Ambiguous download block at ' + url)
        link = links.pop()
        if category_id(link) != category_id(url):
            raise ValueError('Cross-category document')
        key = parse_qs(urlsplit(link).query)['download'][0].split(':')[0]
        if not key.isdigit():
            raise ValueError('Missing PhocaDownload identity')
        doc = {'id': key, 'titulo': title.get_text(' ', strip=True), 'url': link,
               'source_url': url, 'categoria': box.select_one('.pd-ctitle').get_text(' ', strip=True)}
        if key in docs and docs[key] != doc:
            raise ValueError('Conflicting document identity')
        docs[key] = doc
    children = []
    for block in box.select('.pd-subcategory'):
        a, count = block.select_one('a[href]'), block.select_one('small')
        if a is None or count is None or not re.fullmatch(r'\(\d+\)', count.get_text(strip=True)):
            raise ValueError('Missing subcategory count')
        child = urljoin(url, a['href'])
        category_id(child)
        children.append((child, int(count.get_text(strip=True)[1:-1])))
    pages = set()
    for a in box.select('.pagination a[href], #pg-pagination a[href]'):
        page = urljoin(url, a['href'])
        if urlsplit(page).path != urlsplit(url).path:
            raise ValueError('Pagination escaped category')
        category_id(page)
        query = parse_qs(urlsplit(page).query)
        if not set(query) <= {'start', 'limitstart', 'limit'}:
            raise ValueError('Unknown pagination parameters')
        if any(not v.isdigit() for values in query.values() for v in values):
            raise ValueError('Invalid pagination offset')
        pages.add(page)
    return list(docs.values()), children, sorted(pages)


def collect_inventory(fetch):
    """Traverse category and pagination links; reconcile declared document totals."""
    queue = [(SOURCE, 'pgm')]
    visited, categories, expected, groups = set(), {}, {}, {}
    while queue:
        url, group = queue.pop(0)
        if url in visited:
            continue
        if len(visited) >= 200:
            raise ValueError('Inventory exceeds reviewed crawl bound; no partial output written')
        visited.add(url)
        docs, children, pages = parse_page(fetch(url), url)
        cid = category_id(url)
        category_docs = categories.setdefault(cid, set())
        target = groups.setdefault(group, {})
        for doc in docs:
            category_docs.add(doc['id'])
            old = target.get(doc['id'])
            if old and (old['url'], old['titulo']) != (doc['url'], doc['titulo']):
                raise ValueError('Conflicting document on pagination')
            target.setdefault(doc['id'], doc)
        queue.extend((page, group) for page in pages)
        for child, count in children:
            child_id = category_id(child)
            if child_id not in {str(n) for n in range(41, 51)}:
                raise ValueError('New category requires instrument grouping review: ' + child)
            if child_id in expected and expected[child_id] != count:
                raise ValueError('Conflicting category totals')
            expected[child_id] = count
            child_group = {'45': 'modificaciones', '46': 'desarrollo'}.get(child_id, group)
            queue.append((child, child_group))
    for cid, count in expected.items():
        if len(categories.get(cid, ())) != count:
            raise ValueError(f'Incomplete category {cid}: expected {count} downloads')
    rows = []
    for group, docs in sorted(groups.items()):
        if not docs:
            continue
        documents = sorted(docs.values(), key=lambda d: int(d['id']))
        if group == 'pgm':
            title = 'Plan General Municipal de Villamediana de Iregua'
            identity = 'pgm-40'
        else:
            # Each reviewed derived category has exactly one named instrument and
            # its announcement. New instruments require explicit grouping review.
            instruments = [d for d in documents if re.match(r'^(?:MODIFICACI[ÓO]N PUNTUAL|Refundido de la Modificaci[óo]n Puntual)', d['titulo'], re.I)]
            notices = [d for d in documents if d['titulo'].upper().startswith('ANUNCIO')]
            if len(instruments) != 1 or len(notices) != len(documents) - 1:
                raise ValueError('Derived instrument grouping needs review: ' + group)
            title = instruments[0]['titulo']
            identity = 'documento-' + instruments[0]['id']
        rows.append({
            'id': 'villamediana-de-iregua-proy-' + identity,
            'municipio': 'Villamediana de Iregua', 'codigo_ine': '26168', 'provincia': 'La Rioja',
            'titulo': title, 'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE if group == 'pgm' else instruments[0]['source_url'],
            'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento_municipal',
            'documentos': documents,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'limitaciones': LIMITATIONS,
        })
    if not rows or not groups.get('pgm'):
        raise ValueError('No real PGM documents found')
    return rows, sorted(visited)


class VillamedianaDeIreguaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        session = requests.Session()
        session.headers['User-Agent'] = 'municipio-villamediana-de-iregua/1.0'

        def fetch(url):
            with session.get(url, timeout=(15, 45), stream=True) as response:
                response.raise_for_status()
                if urlsplit(response.url).netloc != urlsplit(BASE).netloc:
                    raise ValueError('Unexpected redirect outside municipal inventory')
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > 4_000_000:
                        raise ValueError('Inventory response exceeds size bound')
                html = bytes(content).decode('utf-8')
            if captures:
                path = Path(captures)
                path.mkdir(parents=True, exist_ok=True)
                offset = parse_qs(urlsplit(url).query)
                suffix = offset.get('start', offset.get('limitstart', ['0']))[0]
                (path / f'category-{category_id(url)}-{suffix}.html').write_text(html, encoding='utf-8')
            return html

        try:
            rows, urls = collect_inventory(fetch)
        finally:
            session.close()
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temp = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': urls, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot; a publication date watermark would skip undated files.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
