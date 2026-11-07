"""Baiona's municipal planning document inventories (not a licence register)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.baiona.gal/concejalia-de-urbanismo-vivienda-infraestructuras-y-patrimonio/'
PAGES = {
    'pxom': 'plan-general-de-ordenacion-municipal',
    'pepchab': 'plan-especial-do-conxunto-historico-artistico',
    'tramites': 'tramites-administrativos-de-urbanismo',
}
LIMITATIONS = [
    'Partial coverage: municipal PXOM and PEPCHAB document inventories only; no comprehensive works, amendments or licence register.',
    'No approval, agreement or publication dates inferred from page metadata or PDF filenames.',
    'PEPCHAB landing page is under construction; its municipal normative PDF is indexed on the procedures page.',
    'Document links and their original labels are retained; PDF contents are not parsed or all downloads verified.',
    'PXOM labels 2.0 and 3.4 currently link to the same PDF; both labels are retained without correcting the source.',
    'No verified record geometry; no invented coordinates. Legacy SIOTUGA link is retained as a reference, not crawled.',
]


def official(url):
    p = urlparse(url)
    return p.scheme == 'https' and p.hostname == 'www.baiona.gal'


def parse_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None:
        raise ValueError('Missing municipal main content')
    if soup.select('[rel~=next], .pagination a, a.page-numbers'):
        raise ValueError('Pagination detected; review traversal before accepting output')
    for a in main.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'seguinte', 'next', '»'}:
            raise ValueError('Pagination detected')
    return soup, main


def discover_pages(html, url=SOURCE):
    soup, _ = parse_page(html)
    pages = {}
    for a in soup.select('a[href]'):
        target = urljoin(url, a['href']).split('#')[0]
        if not official(target):
            continue
        for key, tail in PAGES.items():
            if urlparse(target).path.rstrip('/').endswith('/' + tail):
                pages.setdefault(key, target)
    if pages.keys() != PAGES.keys():
        raise ValueError('Municipal navigation no longer exposes all reviewed inventories')
    return pages


def add_documents(record, container, page_url):
    for a in container.select('a[href]'):
        target = urljoin(page_url, a['href'])
        if not official(target) or not urlparse(target).path.lower().endswith('.pdf'):
            continue
        doc = next((d for d in record['documentos'] if d['url'] == target), None)
        if doc is None:
            doc = {'url': target, 'referencias': []}
            record['documentos'].append(doc)
        reference = {'titulo': a.get_text(' ', strip=True), 'source_url': page_url}
        if reference not in doc['referencias']:
            doc['referencias'].append(reference)


def parse_inventories(pages, html_by_key):
    records = {}
    for key in ('pxom', 'pepchab'):
        _, main = parse_page(html_by_key[key])
        heading = main.select_one('h1')
        if not heading or not heading.get_text(' ', strip=True).startswith('Plan '):
            raise ValueError('Missing planning instrument heading')
        record = {
            'id': 'baiona-plan-' + key, 'municipio': 'Baiona', 'codigo_ine': '36003',
            'provincia': 'Pontevedra', 'titulo': heading.get_text(' ', strip=True),
            'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
            'origen': 'inventario_documental_planeamiento', 'url': pages[key],
            'source_urls': [pages[key]], 'documentos': [], 'referencias_externas': [],
            'geometry_status': 'unavailable', 'publication_ready': False,
        }
        add_documents(record, main, pages[key])
        records[key] = record
    _, main = parse_page(html_by_key['tramites'])
    found = set()
    for section in main.select('section.elementor-top-section'):
        heading = section.select_one('h4.wgl-infobox_title')
        title = heading.get_text(' ', strip=True) if heading else ''
        key = {'PEPCHAB': 'pepchab', 'Normativa PXOM': 'pxom'}.get(title)
        if key is None:
            continue  # Licence/application forms are never granted licences or projects.
        found.add(key)
        record = records[key]
        add_documents(record, section, pages['tramites'])
        if pages['tramites'] not in record['source_urls']:
            record['source_urls'].append(pages['tramites'])
        for a in section.select('a[href]'):
            target = urljoin(pages['tramites'], a['href'])
            if urlparse(target).hostname == 'www.planeamentourbanistico.xunta.es':
                ref = {'titulo': a.get_text(' ', strip=True), 'url': target,
                       'source_url': pages['tramites']}
                if ref not in record['referencias_externas']:
                    record['referencias_externas'].append(ref)
    if found != {'pxom', 'pepchab'} or any(not r['documentos'] for r in records.values()):
        raise ValueError('Reviewed instrument documentation missing')
    return list(records.values())


class BaionaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        if not official(url):
            raise ValueError('Unexpected source host')
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'})
        response.raise_for_status()
        if not official(response.url) or 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Unexpected municipal response')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            folder = Path(capture_dir)
            folder.mkdir(parents=True, exist_ok=True)
            stem = hashlib.sha256(url.encode()).hexdigest()[:16]
            (folder / (stem + '.html')).write_text(response.text, encoding='utf-8')
            (folder / (stem + '.json')).write_text(json.dumps({
                'requested_url': url, 'response_url': response.url,
                'status_code': response.status_code}, indent=2), encoding='utf-8')
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pages = discover_pages(self._fetch(SOURCE))
        rows = parse_inventories(pages, {key: self._fetch(url) for key, url in pages.items()})
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'source_urls': [SOURCE, *pages.values()],
                'limitations': LIMITATIONS, 'coverage': 'municipal_planning_document_inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        # Small unpaginated inventories: fully refresh; do not infer new approvals.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
