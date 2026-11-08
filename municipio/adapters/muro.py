"""Muro (Mallorca): document-backed detail studies from municipal inventories."""
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

BASE = 'https://ajmuro.net'
INVENTORIES = (
    BASE + '/ca/arxius-i-documents/pla-general-dordenacio-urbana',
    BASE + '/ca/arxius-i-documents/exposicio-publica',
)
LIMITATIONS = [
    'Partial coverage: only explicitly titled Estudi de Detall instruments in the two municipal document inventories.',
    'Publicly accessible historical documents do not establish current validity, approval or a granted building licence.',
    'Portal document dates have unspecified semantics; kept on documents, never used as agreement or publication dates.',
    'No verified geometry; coordinates remain null. SITMUN viewer, news, minutes and procurement are outside extraction scope.',
]


def official_url(page, href):
    url = urljoin(page, href).split('#')[0]
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'ajmuro.net':
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def parse_listing(html, page):
    soup = BeautifulSoup(html, 'html.parser')
    listing = soup.select_one('main .taxonomy-term-files')
    if listing is None:
        raise ValueError(f'Missing municipal inventory: {page}')
    cards = []
    for a in listing.select('a[href]'):
        heading = a.find('h3')
        if not heading:
            continue
        title = heading.get_text(' ', strip=True)
        count = re.search(r'\b(\d+)\s+documents?\b', a.get_text(' ', strip=True))
        cards.append({'titulo': title, 'url': official_url(page, a['href']),
                      'count': int(count[1]) if count else None})
    pages = []
    for a in soup.select('main a[href]'):
        if 'page=' in a['href']:
            url = official_url(page, a['href'])
            if urlsplit(url).path != urlsplit(page).path:
                raise ValueError('Pagination escaped inventory path')
            pages.append(url)
    return cards, list(dict.fromkeys(pages))


def parse_documents(html, page):
    soup = BeautifulSoup(html, 'html.parser')
    docs = {}
    for a in soup.select('main section.multimedia--documents a[href]'):
        url = official_url(page, a['href'])
        if not urlsplit(url).path.startswith('/sites/cilma_muro/files/'):
            raise ValueError('Unexpected document storage path')
        block = a.parent
        heading = block.find('h3')
        if heading is None:
            raise ValueError('Document lacks title')
        dates = re.findall(r'\b\d{2}/\d{2}/\d{4}\b', block.get_text(' ', strip=True))
        if len(dates) > 1:
            raise ValueError('Ambiguous document metadata date')
        doc_date = datetime.strptime(dates[0], '%d/%m/%Y').date().isoformat() if dates else None
        docs[url] = {'titulo': heading.get_text(' ', strip=True), 'url': url,
                     'pagina_fuente': page, 'fecha_documento_portal': doc_date,
                     'fecha_documento_semantica': 'unspecified portal file metadata date'}
    return list(docs.values())


def make_record(card, inventory, docs):
    if not re.search(r'\bestudi de detall\b', card['titulo'], re.I):
        raise ValueError('Not an explicitly identified detail study')
    if not docs or len(docs) != card['count']:
        raise ValueError('Instrument document count mismatch')
    public = '/exposicio-publica' in inventory
    reference = re.search(r'\bEXP\.\s*(\d+/\d{4})\b', card['titulo'], re.I)
    return {
        'id': 'muro-proy-' + hashlib.sha256(card['url'].encode()).hexdigest()[:16],
        'municipio': 'Muro', 'provincia': 'Illes Balears', 'codigo_ine': '07039',
        'titulo': card['titulo'], 'tipo': 'estudio de detalle',
        'expediente': reference[1] if reference else None,
        'fase': 'exposición pública' if public else None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': card['url'], 'url_documento': docs[0]['url'], 'documentos': docs,
        'source': 'ayuntamiento', 'origen': 'archivo_municipal_planeamiento',
        'source_inventory': inventory, 'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'coverage': 'partial',
        'estado_vigencia': 'no verificado',
    }


class MuroAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='muro', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        official_url(BASE, url)
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-muro/1.0'}) as response:
            response.raise_for_status()
            official_url(BASE, response.url)
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError(f'Expected HTML: {url}')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('HTML exceeds source size limit')
                chunks.append(chunk)
            data = b''.join(chunks)
        capture = self.config.get('evidence_dir')
        if capture:
            target = Path(capture)
            target.mkdir(parents=True, exist_ok=True)
            (target / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(data)
        return data.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        fetched, cache, rows = [], {}, {}

        def fetch(url):
            if url not in cache:
                cache[url] = self._fetch(url)
                fetched.append(url)
            return cache[url]

        for inventory in INVENTORIES:
            pending, visited, cards = [inventory], set(), {}
            while pending:
                page = pending.pop(0)
                if page in visited:
                    continue
                if len(visited) >= 100:
                    raise ValueError('Pagination safety limit reached; no partial output written')
                visited.add(page)
                items, pages = parse_listing(fetch(page), page)
                for item in items:
                    if re.search(r'\bestudi de detall\b', item['titulo'], re.I):
                        cards[item['url']] = item
                pending.extend(p for p in pages if p not in visited)
            for card in cards.values():
                html = fetch(card['url'])
                docs = parse_documents(html, card['url'])
                if not docs:
                    children, pages = parse_listing(html, card['url'])
                    if pages:
                        raise ValueError('Paginated instrument folder requires review')
                    for child in children:
                        child_docs = parse_documents(fetch(child['url']), child['url'])
                        if not child_docs or len(child_docs) != child['count']:
                            raise ValueError('Child document count mismatch')
                        docs.extend(child_docs)
                docs = list({d['url']: d for d in docs}.values())
                record = make_record(card, inventory, docs)
                if card['url'] in rows:
                    raise ValueError('Duplicate instrument across inventories requires reconciliation')
                rows[card['url']] = record
        if not rows:
            raise ValueError('No document-backed detail studies found')
        self._write(out_jsonl, list(rows.values()))
        return {'status': 'ok', 'rows': len(rows), 'source_urls': fetched,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Re-read the entire small inventory; local state never hides older files.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
