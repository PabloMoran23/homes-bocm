"""Current municipal works cards, a partial snapshot rather than a licence register."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.benahadux.es/'
COVERAGE = 'partial_current_homepage_works_inventory'


def official_url(base: str, href: str) -> str:
    url = urldefrag(urljoin(base, href))[0]
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'www.benahadux.es':
        raise ValueError(f'Unexpected municipal URL: {url}')
    return url


def parse_inventory(html: str, url: str) -> tuple[list[str], list[str]]:
    soup = BeautifulSoup(html, 'html.parser')
    view = soup.select_one('.view-obras-en-curso')
    if view is None:
        raise ValueError('Municipal works inventory missing')
    links = []
    for anchor in view.select('article.node--type-obras-y-proyectos h3 a[href]'):
        target = official_url(url, anchor['href'])
        if not urlsplit(target).path.startswith('/obras/'):
            raise ValueError('Unexpected works detail path')
        if target not in links:
            links.append(target)
    if not links:
        raise ValueError('No works in municipal inventory')
    # Fetch every numbered/next page, including pagers without rel=next.
    pages = list(dict.fromkeys(official_url(url, a['href']) for a in
                              view.select('.pager a[href], a[rel~=next]')))
    if view.select_one('.views-infinite-scroll-content-wrapper, .pager__item--load-more, .use-ajax'):
        raise ValueError('Unsupported dynamic works pagination; refusing partial traversal')
    return links, pages


def parse_project(html: str, url: str, inventory_urls: list[str]) -> dict:
    official_url(SOURCE, url)
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.node--type-obras-y-proyectos.node--view-mode-full')
    if article is None:
        raise ValueError('Not a municipal works detail')
    title = article.select_one('h1.project-detail__title')
    body = article.select_one('.field--name-field-text-long-format')
    excerpt = article.select_one('.field--name-field-extracto')
    state = article.select_one('.field--name-field-estados .field__item')
    if not title or not title.get_text(strip=True) or not body or not body.get_text(strip=True) or not state:
        raise ValueError('Incomplete municipal works detail')
    documents = {}
    for anchor in article.select('a[href]'):
        if urlsplit(urljoin(url, anchor['href'])).path.lower().endswith('.pdf'):
            target = official_url(url, anchor['href'])
            documents[target] = {'url': target, 'titulo': anchor.get_text(' ', strip=True),
                                 'source_url': url}
    start = article.select_one('.field--name-field-fecha-de-inicio time[datetime]')
    start_date = None
    if start:
        start_date = datetime.fromisoformat(start['datetime'].replace('Z', '+00:00')).date().isoformat()
    # Keep source fields separate. A planned start is neither an agreement nor publication.
    return {
        'id': 'benahadux-obra-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Benahadux', 'codigo_ine': '04024', 'provincia': 'Almería',
        'titulo': title.get_text(' ', strip=True), 'tipo': 'obra pública municipal',
        'fase': state.get_text(' ', strip=True), 'fecha_inicio': start_date,
        'fecha_inicio_source_label': 'Fecha de inicio',
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'descripcion': body.get_text(' ', strip=True),
        'resumen': excerpt.get_text(' ', strip=True) if excerpt else None,
        'url': url, 'inventory_urls': inventory_urls, 'documentos': list(documents.values()),
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_obras',
        'coverage': COVERAGE, 'publication_ready': False,
        'geometry_status': 'unavailable',
    }


class BenahaduxAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='benahadux', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def _fetch(self, url):
        official_url(SOURCE, url)
        response = requests.get(url, timeout=45, headers={
            'User-Agent': 'municipio-benahadux/1.0 (public works inventory)'})
        response.raise_for_status()
        official_url(SOURCE, response.url)
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected HTML source')
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (directory / name).write_text(response.text, encoding='utf-8')
        return response.text

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        pending, seen, details = [SOURCE], set(), {}
        while pending:
            url = pending.pop(0)
            if url in seen:
                continue
            if len(seen) >= 100:
                raise ValueError('Inventory pagination exceeds safety bound; no output written')
            links, pages = parse_inventory(self._fetch(url), url)
            seen.add(url)
            for link in links:
                details.setdefault(link, []).append(url)
            pending.extend(page for page in pages if page not in seen)
        rows = [parse_project(self._fetch(url), url, inventories)
                for url, inventories in details.items()]
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'coverage': COVERAGE,
                'source_urls': sorted(seen | set(details)), 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
