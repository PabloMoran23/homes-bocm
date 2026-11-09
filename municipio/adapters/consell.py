"""Consell's municipal planning document inventory, grouped by instrument."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://ajconsell.net'
SOURCE = BASE + '/ca/urbanisme'
LIMITATIONS = [
    'Partial coverage: municipal Urbanisme document inventory only; no exhaustive works, news, BOIB or licence history.',
    'Portal attachment dates are upload/display dates, not agreement or BOIB publication dates. Legal dates and current legal validity are not inferred.',
    'No verified geometry or coordinates; publication_ready=false. Updates replace the complete inventory snapshot.',
]


def official_url(base, href):
    url = urldefrag(urljoin(base, href))[0]
    p = urlparse(url)
    if p.scheme != 'https' or p.hostname not in {'ajconsell.net', 'www.ajconsell.net'}:
        raise ValueError(f'Unexpected non-municipal URL: {url}')
    return url.replace('https://www.ajconsell.net', BASE, 1)


def title_of(soup):
    h = soup.select_one('main .layout-content h1')
    return h.get_text(' ', strip=True) if h else ''


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    if title_of(soup) != 'Urbanisme':
        raise ValueError('Urbanisme inventory title/markup changed')
    nav = soup.select_one('main aside nav')
    if not nav:
        raise ValueError('Missing municipal section inventory')
    root = next((a for a in nav.select('a[href]') if urlparse(urljoin(SOURCE, a['href'])).path == '/ca/urbanisme'), None)
    active = next((s for s in nav.select('span[aria-current="page"]') if s.get_text(' ', strip=True).endswith('Urbanisme')), None)
    parent = (root or active)
    listing = parent.parent.find('ul', recursive=False) if parent else None
    if not listing:
        raise ValueError('Missing planning instruments')
    records = {}
    for a in listing.select('li > a[href]'):
        title = a.get_text(' ', strip=True).removeprefix('chevron_right').strip()
        if not re.match(r'^(Adaptació|Modificaci[oó]|Catàleg|Normes Subsidiàries)', title):
            raise ValueError(f'Unreviewed Urbanisme entry: {title}')
        url = official_url(SOURCE, a['href'])
        records[url] = title
    if not records:
        raise ValueError('No named planning instruments')
    return records


def parse_page(html, url):
    """Return documents and all folder/pager links; never cap a listing silently."""
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('main .layout-content')
    title = title_of(soup)
    if not content or not title:
        raise ValueError(f'Not a municipal document page (possible home redirect): {url}')
    listing = content.select_one('.taxonomy-term-files')
    article = content.select_one('article.basic-page-detail, article.node-file-or-document, article.link-detail')
    if not listing and not article:
        raise ValueError(f'Unknown document page markup: {url}')
    links = []
    if listing:
        for a in listing.select('a[href]'):
            if a.select_one('h3'):
                links.append(official_url(url, a['href']))
    for a in content.select('nav a[href], a[rel~=next]'):
        # Drupal zero-based page links, including all numbered pages/last.
        if 'page=' in a['href']:
            links.append(official_url(url, a['href']))
        elif 'next' in a.get('rel', []):
            raise ValueError('Unrecognized pagination URL')
    docs = []
    for a in content.select('.multimedia--documents a[download][href]'):
        card = a.parent
        h = card.select_one('h3')
        if not h:
            raise ValueError('Document card lacks title')
        dates = re.findall(r'\b\d{2}/\d{2}/\d{4}\b', card.get_text(' ', strip=True))
        displayed = datetime.strptime(dates[0], '%d/%m/%Y').date().isoformat() if len(dates) == 1 else None
        docs.append({'titulo': h.get_text(' ', strip=True), 'url': official_url(url, a['href']),
                     'source_page': url, 'fecha_portal': displayed,
                     'fecha_portal_significado': 'fecha mostrada junto al archivo; no es fecha de acuerdo ni publicación BOIB'})
    if article and 'link-detail' in article.get('class', []):
        for a in article.select('a[href][target]'):
            docs.append({'titulo': title, 'url': a['href'], 'source_page': url,
                         'tipo': 'referencia_externa', 'disponibilidad': 'enlace legado no verificado; no descargado'})
    # The parking instrument has its technical package under a related Documentació card.
    if article:
        for a in article.select('a[href]'):
            h = a.parent.select_one('h3')
            if h and h.get_text(' ', strip=True) == 'Documentació':
                links.append(official_url(url, a['href']))
        if not docs and not links:
            raise ValueError(f'Document detail has no attachments: {url}')
    return title, docs, list(dict.fromkeys(links))


class ConsellAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = self.session.get(url, timeout=40)
        response.raise_for_status()
        final = official_url(url, response.url)
        if urlparse(final).path != urlparse(url).path:
            raise ValueError(f'Unexpected redirect: {url} -> {final}')
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError(f'Expected HTML inventory page: {url}')
        html = response.text
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            filename = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
            (directory / filename).write_text(html, encoding='utf-8')
            self.captures.append({'url': url, 'file': filename,
                                  'sha256': hashlib.sha256(html.encode()).hexdigest()})
        self.source_urls.append(url)
        return html

    def collect(self):
        self.source_urls, self.captures = [], []
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'municipio-consell/1.0 (public planning inventory)'
        limitations = list(LIMITATIONS)
        rows = []
        try:
            inventory = parse_inventory(self._fetch(SOURCE))
            for url, title in inventory.items():
                # The www alias served home during discovery. Canonical non-www
                # works; report an explicit gap if the legacy route regresses.
                initial = self._fetch(url)
                if 'cataleg-de-proteccio-' in url and not title_of(BeautifulSoup(initial, 'html.parser')):
                    limitations.append(f'Unavailable legacy heritage catalogue (home page returned): {url}')
                    continue
                pending, visited, documents, references = [url], set(), {}, {}
                provenance = []
                while pending:
                    page = pending.pop(0)
                    if page in visited:
                        continue
                    if len(visited) >= 400:
                        raise ValueError('Instrument exceeds 400 pages; refusing partial extraction')
                    visited.add(page)
                    page_title, docs, links = parse_page(initial if page == url else self._fetch(page), page)
                    provenance.append({'url': page, 'titulo': page_title})
                    if not docs and not links:
                        limitations.append(f'Empty published folder: {page}')
                    for doc in docs:
                        if doc.get('tipo') == 'referencia_externa':
                            references.setdefault(doc['url'], doc)
                            limitations.append(f'Legacy external reference retained without fetching: {doc["url"]} (source: {page})')
                            continue
                        existing = documents.setdefault(doc['url'], {**doc, 'source_pages': []})
                        if doc['source_page'] not in existing['source_pages']:
                            existing['source_pages'].append(doc['source_page'])
                    pending.extend(link for link in links if link not in visited)
                if not documents:
                    raise ValueError(f'Instrument has no actual documents: {url}')
                rows.append({
                    'id': 'consell-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                    'municipio': 'Consell', 'codigo_ine': '07016', 'provincia': 'Illes Balears',
                    'titulo': title, 'tipo': 'planeamiento_urbanistico',
                    'url': url, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
                    'origen': 'inventario_municipal_planeamiento',
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'documentos': list(documents.values()), 'referencias': list(references.values()),
                    'paginas_fuente': provenance,
                    'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                    'coverage': 'document inventory; does not establish latest legal status',
                })
        finally:
            self.session.close()
        if not rows:
            raise ValueError('No usable municipal planning instruments')
        return rows, limitations

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows, limitations = self.collect()
        self._write(out_jsonl, rows)
        report = {'status': 'ok', 'live_records': len(rows), 'rows': len(rows),
                  'documents': sum(len(r['documentos']) for r in rows),
                  'source_urls': self.source_urls, 'limitations': limitations,
                  'captures': self.captures, 'extracted_at': datetime.now().astimezone().isoformat()}
        if self.config.get('capture_dir'):
            (Path(self.config['capture_dir']) / 'validation.json').write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return report

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
