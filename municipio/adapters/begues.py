"""Numbered Begues general-plan amendments from the full municipal inventory."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.begues.cat/ajuntament/informacio-oficial/urbanisme/projectes-urbanistics/'
MONTHS = dict(zip('gener febrer marc abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
LIMITATIONS = [
    'Partial coverage: numbered general-plan amendments only; other planning, works and regional plans excluded.',
    'Municipal notices are historical stages, not a complete register of currently effective planning.',
    'Document links retained; PDF contents and geometries are not extracted or independently verified.',
    'No granted-licence register extracted. No inferred agreement dates or coordinates.',
]


def norm(text):
    return unicodedata.normalize('NFKD', text.replace('’', "'")).encode('ascii', 'ignore').decode().lower()


def amendment_number(title):
    text = norm(title)
    if 'modificacio' not in text or text.startswith('conveni'):
        return None
    match = re.search(r'\b(?:pla general(?: d.ordenacio)?|pgou?)\s*(?:num\.?\s*)?(\d+)\b', text)
    return int(match[1]) if match else None


def agreement_date(description):
    """Only dates in explicit approval sentences; never document/page timestamps."""
    found = set()
    for sentence in re.split(r'[.\n]', norm(description)):
        if not re.search(r'\baprova[td][a-z]*\b', sentence):
            continue
        if not re.search(r'\b(?:ple|junta|decret|acord)\b', sentence):
            continue
        numeric = re.findall(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', sentence)
        named = re.findall(r"\b(\d{1,2})\s+(?:de\s+|d['’])([a-z]+)\s+de\s+(\d{4})\b", sentence)
        for day, month, year in numeric + [(d, str(MONTHS[m]), y) for d, m, y in named if m in MONTHS]:
            found.add(date(int(year), int(month), int(day)).isoformat())
    return next(iter(found)) if len(found) == 1 else None


def phase(text):
    text = norm(text)
    for token, label in [('definitiv', 'aprobación definitiva'), ('provisional', 'aprobación provisional'), ('inicial', 'aprobación inicial')]:
        if re.search(r'aprova\w*\s+' + token, text):
            return label
    return None


def checked_page(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'www.begues.cat' or not parsed.path.startswith(urlparse(SOURCE).path):
        raise ValueError(f'Unexpected municipal source URL: {url}')
    return url


def parse_inventory(html, source_url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#readspeakerPage')
    if not content or not content.select_one('h1') or content.h1.get_text(strip=True) != 'Projectes urbanístics':
        raise ValueError('Missing official project inventory')
    totals = {int(m[1]) for node in content.select('.paginacio .info')
              if (m := re.fullmatch(r'(\d+) pàgines', node.get_text(strip=True)))}
    if len(totals) != 1:
        raise ValueError('Missing or ambiguous pagination total')
    total = totals.pop()
    current = content.select('.paginacio a[aria-current=page]')
    expected = int(parse_qs(urlparse(source_url).query).get('pag', ['1'])[0])
    if not current or any(int(parse_qs(urlparse(urljoin(source_url, a.get('href', ''))).query).get('pag', ['1'])[0]) != expected for a in current):
        raise ValueError('Server returned a different inventory page')
    if not 1 <= total <= 200:
        raise ValueError('Pagination exceeds reviewed bound; no partial output written')
    for link in content.select('.paginacio a[href]'):
        target = checked_page(urljoin(source_url, link['href']))
        number = int(parse_qs(urlparse(target).query).get('pag', ['1'])[0])
        if not 1 <= number <= total:
            raise ValueError('Inconsistent pagination link')
    blocks = content.select('.articlelist .article-item')
    if not blocks:
        raise ValueError('Empty inventory page')
    entries = []
    for block in blocks:
        link, stamp = block.select_one('.tplDefault > a[href]'), block.select_one('.date')
        if not link or not stamp:
            raise ValueError('Changed inventory entry markup')
        title = link.get_text(' ', strip=True)
        number = amendment_number(title)
        if number is not None:
            entries.append({'numero_modificacion': number, 'titulo': title,
                            'url': checked_page(urljoin(source_url, link['href'])),
                            'fecha_publicacion': datetime.strptime(stamp.get_text(strip=True), '%d/%m/%Y').date().isoformat()})
    return total, entries, len(blocks)


def parse_detail(html, entry):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.select_one('#readspeakerPage h1')
    if not title or amendment_number(title.get_text(' ', strip=True)) != entry['numero_modificacion']:
        raise ValueError('Detail is not the expected numbered amendment')
    body = soup.select_one('#readspeakerPage .ddbbtext')
    description = body.get_text(' ', strip=True) if body else ''
    documents = {}
    for link in soup.select('#page-documents a[href], #readspeakerPage .ddbbtext a[href]'):
        url = urljoin(entry['url'], link['href'].strip())
        if urlparse(url).scheme not in ('https', 'http'):
            continue
        documents[url] = {'titulo': link.get_text(' ', strip=True), 'url': url, 'source_url': entry['url']}
    if not documents:
        raise ValueError(f'Amendment lacks documentary links: {entry["url"]}')
    return {**entry, 'descripcion': description, 'fase': phase(description + ' ' + entry['titulo']),
            'fecha_acuerdo': agreement_date(description), 'documentos': list(documents.values())}


def group_amendments(events):
    grouped = {}
    for event in events:
        grouped.setdefault(event['numero_modificacion'], []).append(event)
    rows = []
    for number, stages in sorted(grouped.items()):
        stages = sorted(stages, key=lambda e: (e['fecha_publicacion'], e['url']), reverse=True)
        latest = stages[0]
        documents = {}
        for stage in stages:
            for doc in stage['documentos']:
                key = doc['url']
                item = documents.setdefault(key, {'titulo': doc['titulo'], 'url': key, 'source_urls': []})
                if stage['url'] not in item['source_urls']:
                    item['source_urls'].append(stage['url'])
        rows.append({'id': f'begues-proy-pgo-{number}', 'municipio': 'Begues', 'codigo_ine': '08020',
                     'provincia': 'Barcelona', 'titulo': latest['titulo'], 'numero_modificacion': number,
                     'tipo': 'modificacion_planeamiento_general', 'fase': latest['fase'],
                     'fecha': None, 'fecha_publicacion': latest['fecha_publicacion'],
                     'fecha_acuerdo': latest['fecha_acuerdo'], 'fecha_aprob': None,
                     'descripcion': latest['descripcion'], 'url': latest['url'],
                     'source': 'ayuntamiento', 'origen': 'projectes_urbanistics',
                     'source_urls': [s['url'] for s in stages], 'documentos': list(documents.values()),
                     'publicaciones': stages, 'lat': None, 'lon': None, 'geometry': None,
                     'publication_ready': False,
                     'coverage': 'Latest published municipal stage; current legal validity not established'})
    if not rows:
        raise ValueError('No usable numbered planning amendments')
    return rows


class BeguesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.begues.cat')

    def _fetch(self, url):
        checked_page(url)
        with requests.get(url, timeout=40, stream=True, headers={'User-Agent': 'municipio-begues/1.0'}) as response:
            response.raise_for_status()
            checked_page(response.url)
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Source response exceeds 4 MB; no partial output')
            html = data.decode('utf-8')
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (hashlib.sha256(url.encode()).hexdigest()[:20] + '.html')).write_text(html, encoding='utf-8')
        self.source_urls.append(url)
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        total, entries, count = parse_inventory(self._fetch(SOURCE))
        seen = {e['url'] for e in entries}
        for page in range(2, total + 1):
            url = SOURCE + f'?pag={page}'
            page_total, extra, size = parse_inventory(self._fetch(url), url)
            if page_total != total or seen.intersection(e['url'] for e in extra):
                raise ValueError('Pagination changed or repeated entries; retry complete snapshot')
            seen.update(e['url'] for e in extra)
            entries.extend(extra)
            count += size
        events = [parse_detail(self._fetch(e['url']), e) for e in entries]
        rows = group_amendments(events)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_pages': total, 'inventory_entries': count,
                'planning_notices': len(events), 'source_urls': self.source_urls, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
