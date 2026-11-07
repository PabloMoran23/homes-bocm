"""La Llagosta: current municipal public-exhibition inventory, not licences."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.llagosta.cat'
INVENTORY = BASE + '/ajuntament-seu-electronica/informacio-oficial/exposicio-publica'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
LIMITATIONS = [
    'Partial coverage: current municipal public-exhibition inventory only; no historical completeness or licence register.',
    'Initial approval is not final approval, execution or a granted licence.',
    'Dates without an explicit year remain null; publication and agreement dates are separate.',
    'Documents are retained as links within each instrument; PDF contents are not parsed.',
    'No verified instrument geometry: coordinates remain null and publication_ready is false.',
]


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def eligible(title):
    return bool(re.search(r'\b(projecte|proyecto|pla director|pla estrategic|planol de delimitacio)\b', normalized(title)))


def parse_inventory(html, url=INVENTORY):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None or not main.select('li.article-item'):
        raise ValueError('Missing municipal inventory rows')
    # No pagination is present in the verified inventory. Fail closed if added.
    for a in main.select('a[href]'):
        h = a['href']
        if ('next' in a.get('rel', []) or re.search(r'(?:[?&](?:page|pagina|pag|offset|start)=)', h, re.I)
                or normalized(a.get_text(' ', strip=True)) in ('seguent', 'siguiente', 'next')):
            raise ValueError('Inventory pagination requires review; refusing truncated extraction')
    if main.select('[class*="pagination"], [class*="paginacio"]'):
        raise ValueError('Inventory pagination requires review')
    entries = {}
    for item in main.select('li.article-item'):
        a = item.select_one('a[href]')
        if not a or not eligible(a.get_text(' ', strip=True)):
            continue
        target = urljoin(url, a['href']).split('#')[0]
        p = urlsplit(target)
        if p.hostname != 'www.llagosta.cat' or not p.path.startswith(urlsplit(INVENTORY).path + '/') or not p.path.endswith('.html'):
            raise ValueError('Unexpected project detail URL')
        raw_date = item.select_one('.date')
        if not raw_date:
            raise ValueError('Missing publication date')
        pub = date(*map(int, reversed(raw_date.get_text(strip=True).split('/')))).isoformat()
        entries[target] = {'url': target, 'titulo': a.get_text(' ', strip=True), 'fecha_publicacion': pub}
    if not entries:
        raise ValueError('No project or spatial-plan entries found')
    return list(entries.values())


def agreement_date(text):
    m = re.search(r'data\s+(\d{1,2})\s+d(?:e\s+|[’\x27])([\wç]+)\s+de\s+(\d{4})', text, re.I)
    if not m:
        return None
    if m[2].lower() not in MONTHS:
        raise ValueError('Unrecognized agreement month')
    return date(int(m[3]), MONTHS[m[2].lower()], int(m[1])).isoformat()


def parse_detail(html, entry):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#readspeakerPage')
    title = content.select_one('h1') if content else None
    body = content.select_one('.ddbbtext') if content else None
    if not title or title.get_text(' ', strip=True) != entry['titulo'] or body is None:
        raise ValueError('Project detail no longer matches inventory')
    description = body.get_text(' ', strip=True)
    documents = {}
    for a in soup.select('#page-documents a[href]'):
        target = urljoin(entry['url'], a['href'])
        if urlsplit(target).scheme not in ('https', 'http'):
            raise ValueError('Invalid document URL')
        documents[target] = {'titulo': a.get_text(' ', strip=True), 'url': target, 'source_url': entry['url']}
    if not documents:
        raise ValueError('Project has no linked documentary evidence')
    initial = bool(re.search(r'aprov(?:ar|at) inicial', normalized(description)))
    return {
        **entry, 'id': 'la-llagosta-proy-' + hashlib.sha256(entry['url'].encode()).hexdigest()[:16],
        'municipio': 'La Llagosta', 'codigo_ine': '08105', 'provincia': 'Barcelona',
        'tipo': 'proyecto de obra' if re.search(r'projecte|proyecto', normalized(entry['titulo'])) else 'plan espacial',
        'fase': 'aprobación inicial' if initial else None,
        'fecha': None, 'fecha_acuerdo': agreement_date(description), 'fecha_aprob': None,
        'descripcion': description, 'documentos': list(documents.values()),
        'url_documento': next(iter(documents)), 'inventory_url': INVENTORY,
        'source': 'ayuntamiento', 'origen': 'exposicion_publica_municipal',
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class LaLlagostaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-la-llagosta/1.0'})
        response.raise_for_status()
        if urlsplit(response.url).hostname != 'www.llagosta.cat' or 'html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Unexpected source redirect or content type')
        response.encoding = 'utf-8'
        captures = self.config.get('capture_dir')
        if captures:
            folder = Path(captures)
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html.gz'
            (folder / name).write_bytes(gzip.compress(response.content))
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        entries = parse_inventory(self._fetch(INVENTORY))
        rows = [parse_detail(self._fetch(e['url']), e) for e in entries]
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [INVENTORY] + [e['url'] for e in entries], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
