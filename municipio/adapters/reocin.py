"""Reocín's official Urbanismo menu and its instrument/document inventories.

One row per instrument, not per post or attachment. Dates on document posts are
publication dates only. Neither legal approval nor geometry is inferred.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://reocin.wpcomstaging.com/urbanismo/'
HOSTS = {'reocin.wpcomstaging.com', 'ayto-reocin.com', 'www.ayto-reocin.com'}
INSTRUMENT = re.compile(
    r'^(?:Modificaci[oó]n Puntual|Normas Subsidiarias|Plan General|Plan Parcial|'
    r'Plan Especial|Estudio de Detalle|Proyecto de (?:Urbanizaci[oó]n|Reparcelaci[oó]n))\b',
    re.I,
)


def official_url(base, href):
    url = urldefrag(urljoin(base, href))[0]
    parsed = urlparse(url)
    if parsed.scheme not in {'https', 'http'} or parsed.hostname not in HOSTS:
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None:
        raise ValueError('Missing municipal main content')
    # Fail closed if the reviewed single-page inventories acquire pagination.
    if main.select('.pagination, .elementor-pagination, .nav-links, [rel="next"], '
                   '.page-numbers, .e-load-more-anchor, [data-next-page]'):
        raise ValueError('Pagination requires review; refusing partial inventory')
    for a in main.select('a[href], button'):
        label = a.get_text(' ', strip=True).casefold()
        if label in {'siguiente', 'next', 'cargar más', 'ver más', 'load more'}:
            raise ValueError('Additional pages require review')
    return main


def parse_inventory(html, url=SOURCE):
    main = content(html)
    menu = main.select_one('#menu-menu-urbanismo')
    if menu is None:
        raise ValueError('Missing Urbanismo instrument menu')
    instruments = {}
    for a in menu.select('a[href]'):
        title = a.get_text(' ', strip=True)
        if not INSTRUMENT.match(title):
            continue
        target = official_url(url, a['href'])
        instruments.setdefault(target, {'titulo': title, 'url': target})
    if not instruments:
        raise ValueError('No supported planning instruments in municipal menu')
    return list(instruments.values())


def parse_document_posts(html, url):
    main = content(html)
    posts = {}
    for a in main.select('.elementor-post__title a[href]'):
        target = official_url(url, a['href'])
        posts.setdefault(target, {'titulo': a.get_text(' ', strip=True), 'url': target})
    if not posts:
        raise ValueError('Instrument has no document posts')
    return list(posts.values())


def parse_documents(html, url):
    main = content(html)
    body = main.select_one('.elementor-widget-theme-post-content, .entry-content')
    if body is None:
        raise ValueError('Missing document post body')
    title = main.select_one('h1')
    date = main.select_one('[itemprop="datePublished"] time')
    published = None
    if date:
        raw = date.get('datetime')
        published = (datetime.fromisoformat(raw.replace('Z', '+00:00')).date().isoformat()
                     if raw else datetime.strptime(date.get_text(strip=True), '%d/%m/%Y').date().isoformat())
    docs = {}
    for a in body.select('a[href]'):
        target = urljoin(url, a['href'])
        if not urlparse(target).path.lower().endswith(('.pdf', '.zip')):
            continue
        target = official_url(url, a['href'])
        doc = {'titulo': a.get_text(' ', strip=True) or (title.get_text(' ', strip=True) if title else 'Documento'),
               'url': target, 'source_page': url}
        if published:
            doc['fecha_publicacion'] = published
        docs.setdefault(target, doc)
    if not docs:
        raise ValueError('Document post has no PDF/ZIP attachment')
    return list(docs.values())


class ReocinAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        official_url(SOURCE, url)
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-reocin-inventory/1.0'})
        response.raise_for_status()
        official_url(SOURCE, response.url)
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            suffix = Path(urlparse(url).path).suffix
            suffix = suffix if suffix in {'.pdf', '.zip'} else '.html'
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + suffix
            (directory / name).write_bytes(response.content)
        return response

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        response = self._fetch(SOURCE)
        rows = []
        for instrument in parse_inventory(response.text, response.url):
            detail = self._fetch(instrument['url'])
            documents = {}
            posts = parse_document_posts(detail.text, detail.url)
            for post in posts:
                page = self._fetch(post['url'])
                for doc in parse_documents(page.text, page.url):
                    if doc['url'] in documents:
                        # Preserve every source-page association when an attachment repeats.
                        previous = documents[doc['url']]
                        if doc not in previous['publicaciones']:
                            previous['publicaciones'].append(doc)
                        continue
                    attachment = self._fetch(doc['url'])
                    is_pdf = urlparse(doc['url']).path.lower().endswith('.pdf')
                    if not attachment.content.startswith(b'%PDF-' if is_pdf else b'PK'):
                        raise ValueError('Attachment is not the advertised PDF/ZIP')
                    documents[doc['url']] = {
                        'titulo': doc['titulo'], 'url': doc['url'],
                        'sha256': hashlib.sha256(attachment.content).hexdigest(),
                        'publicaciones': [doc],
                    }
            rows.append({
                'id': 'reocin-plan-' + hashlib.sha256(instrument['url'].encode()).hexdigest()[:16],
                'municipio': 'Reocín', 'codigo_ine': '39060', 'provincia': 'Cantabria',
                **instrument, 'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
                'origen': 'inventario_municipal_urbanismo', 'inventory_url': SOURCE,
                'documentos': list(documents.values()), 'publication_ready': False,
                'geometry_status': 'unavailable',
            })
        return {**self._write(out_jsonl, rows), 'coverage': 'current_urbanismo_menu_partial',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # A complete fresh snapshot of this limited inventory; no deletion inference.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
