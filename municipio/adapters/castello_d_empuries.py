"""Snapshots of Castelló d'Empúries' two public planning inventories.

One record per instrument page, not per attachment. Document labels are source
claims; PDF contents and legal effective status are not inferred from them.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.castello.cat'
INVENTORIES = (
    BASE + '/serveis/urbanisme/planejament-urbanistic/',
    BASE + '/serveis/urbanisme/planejament-en-tramit/',
)
LIMITATIONS = [
    'Partial coverage: only instrument pages linked by the two municipal planning inventories; no historical completeness claim.',
    'Inventory categories are not legal status: even Planejament en Tràmit contains documents labelled definitive approval.',
    'PDF links and original labels retained; PDF contents, signatures and attachment availability not independently validated.',
    'Dates in document labels have unspecified semantics; agreement, approval and publication dates remain null.',
    'No verified geometry or coordinates; publication_ready is false. No granted-licence register extracted.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _official(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname == 'www.castello.cat'


def parse_inventory(html: str, url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('main .page__content')
    heading = soup.select_one('main h1')
    if content is None or heading is None or not _text(heading).lower().startswith('planejament'):
        raise ValueError('Missing municipal planning inventory structure')
    # Current Content Views grids render all items without pagination. If that
    # changes, stop explicitly rather than returning an incomplete first page.
    if content.select('.pt-cv-pagination, .pt-cv-pagination-wrapper, .pt-cv-more, '
                      '.pagination, .page-numbers, [data-totalpages], [data-total-pages], a[rel="next"]'):
        raise ValueError('Pagination detected: inventory traversal needs review')
    records = {}
    for a in content.select('h4.pt-cv-title a[href]'):
        target = urljoin(url, a['href'])
        title = _text(a)
        if not re.match(r'^(Modificació puntual|Pla |Projecte )', title, re.I):
            raise ValueError('Unexpected item in planning inventory: ' + title)
        if not _official(target) or not any(target.startswith(root) and target != root for root in INVENTORIES):
            raise ValueError('Unexpected instrument URL: ' + target)
        records[target] = {'url': target, 'titulo': title, 'inventory_url': url}
    if not records:
        raise ValueError('No named planning instruments in inventory')
    return list(records.values())


def parse_project(html: str, item: dict[str, str]) -> dict[str, Any]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('main h1')
    content = soup.select_one('main .page__content')
    if heading is None or content is None or _text(heading) != item['titulo']:
        raise ValueError('Instrument title missing or inconsistent with inventory: ' + item['url'])
    documents = {}
    for a in content.select('a[href]'):
        if a.find_parent(class_=re.compile(r'^ssba')):
            continue
        target = urljoin(item['url'], a['href'])
        if not _official(target) or not urlparse(target).path.lower().endswith(('.pdf', '.zip')):
            continue
        label = _text(a)
        if label.lower() in ('baixa', 'descarrega', 'download', ''):
            continue
        doc = documents.setdefault(target, {'url': target, 'labels': [], 'source_url': item['url']})
        if label not in doc['labels']:
            doc['labels'].append(label)
    if not documents:
        raise ValueError('No actual planning document links: ' + item['url'])
    title = _text(heading)
    kind = ('modificació puntual POUM' if title.lower().startswith('modificació')
            else 'projecte urbanístic' if title.lower().startswith('projecte') else 'instrument de planejament')
    return {
        'id': 'castello-d-empuries-plan-' + hashlib.sha256(item['url'].encode()).hexdigest()[:16],
        'municipio': "Castelló d'Empúries", 'codigo_ine': '17047', 'provincia': 'Girona',
        'titulo': title, 'tipo': kind, 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': item['url'], 'inventory_url': item['inventory_url'],
        'url_documento': next(iter(documents)), 'documentos': list(documents.values()),
        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class CastelloDEmpuriesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, session, url):
        with session.get(url, timeout=40, stream=True) as response:
            response.raise_for_status()
            # requests canonicalizes percent-escape casing (e.g. %c2%b7).
            if unquote(response.url) != unquote(url):
                raise ValueError('Unexpected source redirect: ' + response.url)
            chunks = []
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Source exceeds 4 MB HTML limit')
                chunks.append(chunk)
            body = b''.join(chunks)
            html = body.decode('utf-8')
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:20] + '.html')).write_bytes(body)
        return html

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        items = {}
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; municipal-planning-inventory/1.0)'
            for url in INVENTORIES:
                for item in parse_inventory(self._fetch(session, url), url):
                    items.setdefault(item['url'], item)
                source_urls.append(url)
            rows = []
            for item in items.values():
                rows.append(parse_project(self._fetch(session, item['url']), item))
                source_urls.append(item['url'])
        # Do not replace a previous complete snapshot on any HTTP/parser failure.
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'live_records': len(rows),
                'source_urls': source_urls, 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete refresh, no date cursor: a document may be added to an old plan.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
