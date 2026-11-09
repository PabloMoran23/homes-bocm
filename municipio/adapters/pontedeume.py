"""Planning instruments published on Pontedeume's public notice board.

Coverage is the complete exposed listing, not a historical planning register.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://sede.pontedeume.gal/sxc/es/informacion/tablon/index.html'
HOST = 'sede.pontedeume.gal'
LIST_PATH = '/sxc/es/informacion/tablon/index.html'
LIMITATIONS = [
    'Only the complete exposed notice-board listing (currently capped by the source at 100 notices); not the historical planning register.',
    'Only explicit urban planning instruments with a source expediente and attached documents; no licence grants or procurement records.',
    'Publication dates are board dates, not agreement or approval dates. PDF contents are not parsed.',
    'No verified geometry; no inference of present legal validity or construction execution.',
]


def norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def official_url(base, href):
    url = urljoin(base, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != HOST:
        raise ValueError(f'Unexpected off-site URL: {url}')
    return url


def parse_listing(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    blocks = soup.select('.noticia')
    if not blocks:
        raise ValueError('Notice listing missing or empty; review source')
    notices = []
    for block in blocks:
        link = block.select_one('h3 a[href]')
        date = block.select_one('p.fecha')
        paragraphs = block.select('p:not(.fecha)')
        # Some old notices have no link/title; they remain counted in coverage.
        if not link or not paragraphs:
            continue
        title = paragraphs[-1].get_text(' ', strip=True)
        text = norm(title)
        instrument = re.search(r'\b(?:pxom|pgou|plan (?:xeral|general|parcial|especial)|estud[io]+ de detalle|proxecto de (?:urbanizacion|reparcelacion)|proyecto de (?:urbanizacion|reparcelacion))\b', text)
        excluded = re.search(r'\b(?:licitacion|contratacion|contrato|formulario|solicitud|solicitude|modelo|ordenanza|subvencions?|antifraude|anti-fraude|prevencion de riscos)\b', text)
        if not instrument or excluded:
            continue
        if not date:
            raise ValueError('Planning notice has no publication date')
        from datetime import datetime
        publication = datetime.strptime(date.get_text(strip=True), '%d/%m/%Y').date().isoformat()
        target = official_url(url, link['href'])
        if not urlparse(target).path.startswith('/sxc/es/informacion/tablon/'):
            raise ValueError('Unexpected notice path')
        notices.append({'titulo': title, 'url': target, 'fecha_publicacion': publication,
                        'inventory_url': url})
    pages = set()
    for link in soup.select('#pagination a[href], .pagination a[href]'):
        target = official_url(url, link['href'])
        parsed = urlparse(target)
        query = parse_qs(parsed.query)
        if parsed.path != LIST_PATH or set(query) != {'page'} or not query['page'][0].isdigit():
            raise ValueError('Unrecognized pagination; refusing partial extraction')
        page = int(query['page'][0])
        if page < 1:
            raise ValueError('Invalid page number')
        pages.add(f'{SOURCE}?page={page}')
    return notices, sorted(pages), len(blocks)


def parse_detail(html, notice):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('.article')
    if article is None:
        raise ValueError('Missing notice article')
    match = re.search(r'\bEXP\s*:\s*([\w/-]+)', article.get_text(' ', strip=True), re.I)
    if not match:
        raise ValueError('Planning notice lacks a verified expediente; review grouping')
    documents = {}
    for link in soup.select('.listado-pag a[href]'):
        target = official_url(notice['url'], link['href'])
        if not urlparse(target).path.startswith('/sxc/export/sites/pontedeume/recursos/downloads/Tablon/'):
            raise ValueError('Unexpected document path')
        documents[target] = {
            'titulo': link.get('title') or link.get_text(' ', strip=True),
            'url': target,
            'tipo': 'justificante_publicacion' if '/SELLADO_' in target else 'documento_anuncio',
            'source_url': notice['url'],
        }
    if not any(d['tipo'] == 'documento_anuncio' for d in documents.values()):
        raise ValueError('Planning notice lacks substantive attached documents')
    return {**notice, 'expediente': match.group(1), 'documentos': list(documents.values())}


def group_instruments(notices):
    grouped = {}
    for notice in sorted(notices, key=lambda n: (n['fecha_publicacion'], n['url'])):
        ref = notice['expediente']
        if ref not in grouped:
            grouped[ref] = {
                'id': 'pontedeume-plan-' + hashlib.sha256(ref.encode()).hexdigest()[:16],
                'municipio': 'Pontedeume', 'codigo_ine': '15069', 'provincia': 'A Coruña',
                'expediente': ref, 'tipo': 'planeamiento_urbanistico',
                'source': 'ayuntamiento', 'origen': 'tablon_municipal',
                'publication_ready': False, 'geometry_status': 'unavailable',
                'coverage': 'exposed_notice_board_only', 'anuncios': [], 'documentos': [],
            }
        row = grouped[ref]
        # The latest source title is retained verbatim; every notice keeps its own date.
        row.update({k: notice[k] for k in ('titulo', 'url', 'fecha_publicacion', 'inventory_url')})
        row['anuncios'].append({k: notice[k] for k in ('titulo', 'url', 'fecha_publicacion', 'inventory_url')})
        for document in notice['documentos']:
            if document not in row['documentos']:
                row['documentos'].append(document)
    if not grouped:
        raise ValueError('No usable planning instruments in exposed listing')
    return list(grouped.values())


class PontedeumeAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=45, headers={'User-Agent': 'municipio-pontedeume/1.0'})
        response.raise_for_status()
        official_url(url, response.url)
        if response.url != url:
            raise ValueError('Unexpected source redirect')
        response.encoding = 'utf-8'
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            folder = Path(capture_dir)
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
            (folder / name).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        # Canonical page 1 prevents duplicate fetch of the bare listing URL.
        pending = {SOURCE + '?page=1'}
        visited, candidates = set(), {}
        signatures = set()
        count = 0
        advertised_count = None
        while pending:
            url = min(pending)
            pending.remove(url)
            if url in visited:
                continue
            if len(visited) >= 200:
                raise ValueError('Pagination exceeds safety bound; no partial output written')
            html = self._fetch(url)
            notices, pages, blocks = parse_listing(html, url)
            # Catch servers ignoring page parameters, including pages without candidates.
            soup = BeautifulSoup(html, 'html.parser')
            advertised = soup.select_one('.avisoNoticia')
            if advertised:
                match = re.search(r'(\d+) anuncios', advertised.get_text(' ', strip=True))
                if match:
                    advertised_count = int(match.group(1))
            signature = tuple(b.get_text(' ', strip=True) for b in soup.select('.noticia'))
            if signature in signatures:
                raise ValueError('Repeated listing page; pagination may have been ignored')
            signatures.add(signature)
            visited.add(url)
            count += blocks
            pending.update(set(pages) - visited)
            for notice in notices:
                candidates[notice['url']] = notice
        if advertised_count is not None and count != advertised_count:
            raise ValueError(f'Listing advertised {advertised_count} notices but exposed {count}; review coverage')
        details = [parse_detail(self._fetch(n['url']), n) for n in candidates.values()]
        rows = group_instruments(details)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'listing_pages': len(visited),
                'notices_scanned': count, 'source_urls': sorted(visited | set(candidates)),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh: a rolling board cannot provide a reliable date-only increment.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public licence-grant register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
