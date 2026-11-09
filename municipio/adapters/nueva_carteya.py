"""Conservative inventory of physical facilities inaugurated on the municipal site."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://aytonuevacarteya.es/noticias.html'
HOST = 'aytonuevacarteya.es'


def official_url(base, href):
    parts = urlsplit(urljoin(base, href))
    if parts.hostname not in {HOST, 'www.' + HOST} or parts.scheme not in {'http', 'https'}:
        raise ValueError('Unexpected source host')
    return urlunsplit(('https', HOST, unquote(parts.path), parts.query, ''))


def parse_inventory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None:
        raise ValueError('Missing municipal news inventory')
    headings = main.select('h1 a[href], h2 a[href], h3 a[href]')
    if not headings:
        raise ValueError('Empty or changed news inventory')
    candidates = {}
    for a in headings:
        title = a.get_text(' ', strip=True)
        if re.match(r'^Inauguraci[oó]n\b', title, re.I) and re.search(
            r'\b(gimnasio|parque|ayuntamiento|centro|polideportivo|biblioteca|piscina)\b', title, re.I
        ):
            target = official_url(url, a['href'])
            candidates[target] = title
    pages = set()
    for a in main.select('.uk-pagination a[href]'):
        target = official_url(url, a['href'])
        parts = urlsplit(target)
        query = parse_qs(parts.query)
        if parts.path != '/noticias.html' or set(query) - {'start'}:
            raise ValueError('Changed pagination URL')
        offset = query.get('start', ['0'])
        if len(offset) != 1 or not offset[0].isdigit():
            raise ValueError('Invalid pagination offset')
        pages.add(SOURCE if int(offset[0]) == 0 else SOURCE + '?start=' + str(int(offset[0])))
    return candidates, pages


def parse_project(html, url, inventory_urls):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.uk-article')
    if article is None or article.select_one('h1') is None:
        raise ValueError('Missing project article')
    content = article.select_one('.tm-article-content')
    if content is None:
        raise ValueError('Missing project description')
    images = list(dict.fromkeys(
        official_url(url, img['src']) for img in content.select('img[src]')
        if img['src'].startswith('/images/')
    ))
    documents = {url: {'titulo': 'Noticia municipal de la actuación', 'url': url}}
    for a in content.select('a[href]'):
        if urlsplit(a['href']).path.lower().endswith('.pdf'):
            target = official_url(url, a['href'])
            documents[target] = {'titulo': a.get_text(' ', strip=True), 'url': target}
    for element in content.select('script, style, .css_buttons1, [data-uk-grid], .uk-modal'):
        element.decompose()
    description = content.get_text(' ', strip=True)
    # An invitation, service reopening or sports programme does not establish a built work.
    if not re.search(r'tuvo lugar la inauguraci[oó]n', description, re.I):
        return None
    title = article.select_one('h1').get_text(' ', strip=True)
    if not re.match(r'^Inauguraci[oó]n\b', title, re.I) or not re.search(
        r'\b(gimnasio|parque|ayuntamiento|centro|polideportivo|biblioteca|piscina)\b', title, re.I
    ):
        return None
    return {
        'id': 'nueva-carteya-obra-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Nueva Carteya', 'codigo_ine': '14046', 'provincia': 'Córdoba',
        'titulo': title, 'tipo': 'obra_publica', 'descripcion': description,
        'url': url, 'source': 'ayuntamiento', 'origen': 'noticia_municipal_inauguracion',
        'inventory_urls': sorted(inventory_urls), 'documentos': list(documents.values()),
        'imagenes': images, 'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'Noticias que confirman inauguraciones de equipamientos físicos; no registro de expedientes.',
    }


class NuevaCarteyaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(url, timeout=40)
        response.raise_for_status()
        if official_url(url, response.url) != url:
            raise ValueError('Unexpected source redirect')
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML source')
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (path / name).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pending, visited, candidates = {SOURCE}, set(), {}
        signatures = set()
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-nueva-carteya/1.0 (public municipal inventory)'
            while pending:
                if len(visited) >= 500:
                    raise ValueError('Pagination safety limit reached; refusing partial extraction')
                url = min(pending)
                pending.remove(url)
                html = self._fetch(session, url)
                # Detect servers ignoring offsets instead of accepting a false full crawl.
                soup = BeautifulSoup(html, 'html.parser')
                signature = tuple(a.get('href') for a in soup.select('main h1 a, main h2 a, main h3 a'))
                if signature in signatures:
                    raise ValueError('Repeated inventory page; pagination may be ignored')
                signatures.add(signature)
                found, pages = parse_inventory(html, url)
                visited.add(url)
                pending.update(pages - visited)
                for target in found:
                    candidates.setdefault(target, set()).add(url)
            rows = []
            for url, inventories in sorted(candidates.items()):
                row = parse_project(self._fetch(session, url), url, inventories)
                if row:
                    rows.append(row)
        if not rows:
            raise ValueError('No verified inaugurated physical works found')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'inventory_pages': len(visited),
                'source_urls': sorted(visited | set(candidates)), 'publication_ready': False,
                'coverage': 'partial: completed facility inaugurations reported by municipal news'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
