"""Current official Proxectos inventory: named works and planning documents."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://portodoson.gal'
INVENTORY = BASE + '/category/obras/proxectos/'
MONTHS = {m: n for n, m in enumerate(
    'xaneiro febreiro marzo abril maio xuño xullo agosto setembro outubro novembro decembro'.split(), 1)}
LIMITATIONS = [
    'Partial municipal coverage: only the current Proxectos category, not the Obras news archive or all planning instruments.',
    'Standalone property acquisition excluded: no physical intervention established by its project sheet.',
    'Publication dates are CMS post dates; approval dates only from explicit approval narrative.',
    'Linked documents retained; no licence grants, verified coordinates or inferred execution status.',
    'Updates refresh the complete source snapshot; no historical change log or deletion inference.',
]


def official_url(href, source):
    url = urljoin(source, href)
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'portodoson.gal' or parts.query or parts.fragment:
        raise ValueError(f'Unexpected municipal URL: {url}')
    return url


def parse_inventory(html, source=INVENTORY):
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    for card in soup.select('.item.category-proxectos'):
        a = card.select_one('h2 > a[href]')
        if not a:
            raise ValueError('Project card without detail link')
        links.append(official_url(a['href'], source))
    if not links:
        raise ValueError('Municipal Proxectos inventory empty or markup changed')
    pages = set()
    for a in soup.select('a[href]'):
        target = urljoin(source, a['href'])
        pagination = (re.search(r'/category/obras/proxectos/page/\d+/?', target)
                      or 'next' in a.get('rel', [])
                      or a in soup.select('.pagination a, a.page-numbers, .nav-previous a, .nav-next a'))
        if pagination:
            target = official_url(a['href'], source)
            if not re.fullmatch(re.escape(INVENTORY) + r'(?:page/\d+/)?', target):
                raise ValueError(f'Unrecognized pagination URL: {target}')
            if target != source:
                pages.add(target)
    return list(dict.fromkeys(links)), sorted(pages)


def publication_date(text):
    match = re.search(r'\b(\w+)\s+(\d{1,2}),\s+(\d{4})', text.lower())
    if not match or match[1] not in MONTHS:
        raise ValueError('Missing or unrecognized post publication date')
    return date(int(match[3]), MONTHS[match[1]], int(match[2])).isoformat()


def parse_project(html, source):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1.entry-title')
    body = soup.select_one('.entry[itemprop="text"]')
    if not heading or not body:
        raise ValueError('Municipal project detail missing')
    title = heading.get_text(' ', strip=True)
    is_plan = bool(re.match(r'^Aprobación definitiva PEID\b', title, re.I))
    is_work = bool(re.match(r'^Humanización do núcleo\b', title, re.I))
    if not (is_plan or is_work):
        return None
    text = '\n'.join(p.get_text(' ', strip=True) for p in body.select('p') if p.get_text(strip=True))
    documents = {}
    for a in body.select('a[href]'):
        if urlsplit(urljoin(source, a['href'])).path.lower().endswith('.pdf'):
            target = official_url(a['href'], source)
            label = a.get_text(' ', strip=True)
            if target not in documents or (label and label.lower() != 'descarga'):
                documents[target] = label or urlsplit(target).path.rsplit('/', 1)[-1]
    if not text or not documents:
        raise ValueError(f'Named project without narrative or supporting PDF: {source}')
    meta = soup.select_one('.meta .post-date')
    if not meta:
        raise ValueError('Missing publication metadata')
    row = {
        'id': 'porto-do-son-proy-' + hashlib.sha256(source.encode()).hexdigest()[:16],
        'municipio': 'Porto do Son', 'codigo_ine': '15071', 'provincia': 'A Coruña',
        'titulo': title, 'tipo': 'PEID' if is_plan else 'obra de humanización',
        'descripcion': text, 'url': source, 'inventory_url': INVENTORY,
        'documentos': [{'titulo': label, 'url': url, 'source_url': source} for url, label in documents.items()],
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_proxectos',
        'fecha_publicacion': publication_date(meta.get_text(' ', strip=True)),
        'publication_ready': False, 'geometry_status': 'unavailable',
    }
    if is_plan:
        approval = re.search(r'aprobado definitivamente polo Pleno municipal,.*?o (\d{1,2}) de (\w+) de (\d{4})', text, re.I | re.S)
        if not approval or approval[2].lower() not in MONTHS:
            raise ValueError('PEID approval narrative no longer recognized')
        row['fecha_aprob'] = date(int(approval[3]), MONTHS[approval[2].lower()], int(approval[1])).isoformat()
        row['fase'] = 'aprobación definitiva'
        row['fecha_aprob_source_url'] = source
    return row


class PortoDoSonAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='porto-do-son', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        response = requests.get(url, timeout=45, headers={
            'User-Agent': self.config.get('user_agent', 'Mozilla/5.0 (compatible; municipal-inventory/1.0)')})
        response.raise_for_status()
        if official_url(response.url, url) != url:
            raise ValueError(f'Unexpected redirect from {url} to {response.url}')
        if 'text/html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML municipal source')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            folder = Path(capture_dir)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    def backfill_proyectos(self, out_jsonl):
        pending, visited, details = [INVENTORY], set(), {}
        fingerprints = set()
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            links, pages = parse_inventory(self._fetch(url), url)
            fingerprint = tuple(sorted(links))
            if fingerprint in fingerprints:
                raise ValueError('Repeated inventory page: pagination may be broken')
            fingerprints.add(fingerprint)
            visited.add(url)
            details.update(dict.fromkeys(links))
            pending.extend(page for page in pages if page not in visited)
        rows, excluded = [], []
        for url in details:
            row = parse_project(self._fetch(url), url)
            if row:
                rows.append(row)
            else:
                excluded.append({'url': url, 'reason': 'Outside supported PEID / named humanization works scope'})
        if not rows:
            raise ValueError('No usable municipal projects found')
        out = Path(out_jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': sorted(visited | set(details)),
                'inventory_pages': len(visited), 'detail_pages': len(details), 'excluded': excluded,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        out = Path(out_jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
