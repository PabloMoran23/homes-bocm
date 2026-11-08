"""Current official Urbanismo inventory; document bundles, never licence grants."""
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

SOURCE = 'https://www.lacisterniga.es/normativa-urbanistica-pt?page=0'


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn')


def official_url(value, base):
    url = urljoin(base, value)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'www.lacisterniga.es', 'lacisterniga.es'}:
        raise ValueError(f'Unexpected official source URL: {url}')
    return url


def selected(title):
    text = normalized(title)
    return bool(re.match(r'^(?:aprobacion (?:inicial|definitiva) (?:del? )?)?proyecto\b', text)
                or re.match(r'^documentos modificacion puntual\b', text)
                or re.match(r'^aprobacion definitiva plan parcial\b', text))


def parse_inventory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    articles = soup.select('main article.node--type-documents')
    if not articles:
        raise ValueError('Urbanismo inventory markup missing or empty')
    entries = []
    for article in articles:
        a = article.select_one('h2 a[href]')
        if a is None or not a.get_text(strip=True):
            raise ValueError('Inventory article without title/link')
        target = official_url(a['href'], url)
        if not urlparse(target).path.startswith('/doc/'):
            raise ValueError('Unexpected inventory detail path')
        entries.append({'titulo': a.get_text(' ', strip=True), 'url': target})
    next_links = soup.select('main li.pager__item--next a[href]')
    if len(next_links) > 1:
        raise ValueError('Ambiguous pagination')
    next_url = official_url(next_links[0]['href'], url) if next_links else None
    current = int(parse_qs(urlparse(url).query).get('page', ['0'])[0])
    if next_url:
        p = urlparse(next_url)
        if p.path != '/normativa-urbanistica-pt' or int(parse_qs(p.query).get('page', ['-1'])[0]) != current + 1:
            raise ValueError('Unexpected pagination sequence')
    for a in soup.select('main nav.pager a[href]'):
        page = int(parse_qs(urlparse(urljoin(url, a['href'])).query).get('page', ['0'])[0])
        if page > current and not next_url:
            raise ValueError('Later pages exist without next link')
    return entries, next_url


def parse_detail(html, url, expected_title):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('main h1')
    content = soup.select_one('#block-mipueblo-content')
    if heading is None or heading.get_text(' ', strip=True) != expected_title or content is None:
        raise ValueError('Detail title/content changed')
    documents = []
    for a in content.select('.field--name-field-attached-files a[href]'):
        target = official_url(a['href'], url)
        if not urlparse(target).path.startswith('/sites/default/files/'):
            raise ValueError('Unexpected attachment path')
        documents.append({'titulo': a.get_text(' ', strip=True), 'url': target, 'source_url': url})
    if not documents:
        raise ValueError('Selected project has no attached documents')
    body = content.select_one('.field--name-body')
    ranges = content.select('.field--name-field-date-range')
    return {'titulo': expected_title, 'url': url,
            'descripcion': body.get_text(' ', strip=True) if body else None,
            # Drupal date-range is unlabelled: preserve it without interpreting
            # it as publication, agreement, approval or effective dates.
            'source_date_ranges': [e.get_text(' ', strip=True) for e in ranges],
            'source_date_values': [t.get('datetime') for e in ranges for t in e.select('time')],
            'documentos': documents}


def group_key(title):
    title = re.sub(r'^documentos\s+', '', normalized(title))
    title = re.sub(r'[_\s-]*parte\s+\d+\s*$', '', title)
    return re.sub(r'[^a-z0-9]+', ' ', title).strip()


def group_records(details):
    groups = {}
    for detail in details:
        key = group_key(detail['titulo'])
        if key not in groups:
            title = re.sub(r'^Documentos\s+', '', detail['titulo'], flags=re.I)
            title = re.sub(r'[_\s-]*Parte\s+\d+\s*$', '', title, flags=re.I).strip()
            groups[key] = {
                'id': 'cisterniga-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Cistérniga', 'codigo_ine': '47052', 'provincia': 'Valladolid',
                'titulo': title, 'tipo': 'proyecto o instrumento urbanístico',
                'url': detail['url'], 'inventory_url': SOURCE,
                'source': 'ayuntamiento', 'origen': 'inventario_urbanismo',
                'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'fichas': [], 'documentos': [],
            }
        row = groups[key]
        row['fichas'].append({k: v for k, v in detail.items() if k != 'documentos'})
        known = {d['url'] for d in row['documentos']}
        row['documentos'].extend(d for d in detail['documentos'] if d['url'] not in known)
    if not groups:
        raise ValueError('No usable documented projects in the current inventory')
    return list(groups.values())


class CisternigaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(url, timeout=45)
        response.raise_for_status()
        official_url(response.url, url)
        if urlparse(response.url).path != urlparse(url).path:
            raise ValueError('Unexpected source redirect')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected an HTML inventory/detail')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            dest = Path(capture_dir)
            dest.mkdir(parents=True, exist_ok=True)
            (dest / (hashlib.sha256(url.encode()).hexdigest()[:20] + '.html')).write_bytes(response.content)
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        seen, entries, details, sources = set(), {}, [], []
        url = SOURCE
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-cisterniga/1.0 (public planning inventory)'
            while url:
                if url in seen:
                    raise ValueError('Inventory pagination cycle')
                seen.add(url)
                page_entries, next_url = parse_inventory(self._fetch(session, url), url)
                sources.append(url)
                entries.update({e['url']: e for e in page_entries})
                url = next_url
            for entry in entries.values():
                if selected(entry['titulo']):
                    details.append(parse_detail(self._fetch(session, entry['url']), entry['url'], entry['titulo']))
                    sources.append(entry['url'])
        rows = group_records(details)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'inventory_pages': len(seen),
                'inventory_entries': len(entries), 'selected_details': len(details),
                'source_urls': sources, 'coverage': 'current Urbanismo document inventory only',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        raise RuntimeError('Licencias disabled: forms/applications are not grants')

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
