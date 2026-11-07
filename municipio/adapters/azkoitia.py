"""Azkoitia's published PGOU procedure, discovered through its planning inventory.

Deliberately partial coverage: no licence requests, announcements or future phase
lists are interpreted as granted licences or plan approvals.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://azkoitia.eus'
SOURCE = BASE + '/es/ayuntamiento/departamentos/urbanismo/planes-de-ordenacion-urbana-en-tramitacion'
MONTHS = dict(zip('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), range(1, 13)))
LIMITATIONS = [
    'Partial coverage: only PGOU procedures in the municipal planning-in-progress inventory; excludes other planning instruments, works and the general announcement archive.',
    'Agreement date is initiation of the procedure, not approval of the PGOU; publication date refers to the linked BOG announcement.',
    'No verified project geometry or coordinates; no granted-licence register extracted.',
    'Updates refresh the complete source snapshot; no historical removal reconciliation.',
]


def _municipal(url: str) -> bool:
    return urlparse(url).scheme == 'https' and urlparse(url).hostname in {'azkoitia.eus', 'www.azkoitia.eus'}


def parse_inventory(html: str, page_url: str = SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    inventory = soup.select_one('.article-list')
    if inventory is None:
        raise ValueError('Planning inventory missing (possibly blocked or changed markup)')
    projects = {}
    for article in inventory.select('article.item'):
        link = article.select_one('.entry-header h2 a[href]')
        if not link:
            raise ValueError('Inventory article missing its detail link')
        title = link.get_text(' ', strip=True)
        if not re.search(r'\bPGOU\b.*PLAN GENERAL DE ORDENACI[ÓO]N URBANA', title, re.I):
            continue
        url = urljoin(page_url, link['href'])
        match = re.search(r'/(\d+)-[^/]+$', urlparse(url).path)
        if not _municipal(url) or not urlparse(url).path.startswith(urlparse(SOURCE).path + '/') or not match:
            raise ValueError('Unexpected PGOU detail URL')
        projects[match[1]] = {'source_id': match[1], 'titulo': title, 'url': url}
    pages = set()
    for link in soup.select('.pagination a[href], a[rel~=next]'):
        url = urljoin(page_url, link['href'])
        if not _municipal(url) or urlparse(url).path.rstrip('/') != urlparse(SOURCE).path:
            raise ValueError('Unexpected inventory pagination URL')
        if url != page_url:
            pages.add(url)
    declared = re.search(r'P[áa]gina\s+\d+\s+de\s+(\d+)', soup.get_text(' ', strip=True), re.I)
    if declared and int(declared[1]) > 1 and not pages:
        raise ValueError('Pagination declared but no crawlable page links')
    return list(projects.values()), sorted(pages)


def parse_project(html: str, item: dict) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.item-page')
    if article is None:
        raise ValueError('PGOU detail article missing')
    text = article.get_text(' ', strip=True)
    agreement = re.search(
        r'El Pleno Municipal acordó el (\d{1,2}) de (\w+) de (\d{4}) '
        r'dar inicio al procedimiento de aprobación del Plan General de Ordenación Urbana del municipio', text)
    if not agreement or agreement[2] not in MONTHS:
        raise ValueError('Explicit PGOU initiation agreement missing; review source semantics')
    agreement_date = date(int(agreement[3]), MONTHS[agreement[2]], int(agreement[1])).isoformat()
    documents = {}
    publications = set()
    for link in article.select('a[href]'):
        url = urljoin(item['url'], link['href'])
        if not urlparse(url).path.lower().endswith('.pdf'):
            continue
        host = urlparse(url).hostname
        if urlparse(url).scheme != 'https' or host not in {'azkoitia.eus', 'www.azkoitia.eus', 'egoitza.gipuzkoa.eus'}:
            raise ValueError('Unreviewed PGOU document origin')
        title = link.get_text(' ', strip=True)
        doc = {'titulo': title, 'url': url, 'url_origen': item['url']}
        published = re.search(r'Anuncio publicado en el BOG de (\d{2})/(\d{2})/(\d{4})', title)
        if published:
            if host != 'egoitza.gipuzkoa.eus':
                raise ValueError('BOG announcement must link to the official bulletin')
            stamp = date(int(published[3]), int(published[2]), int(published[1])).isoformat()
            doc['fecha_publicacion'] = stamp
            publications.add(stamp)
        documents[url] = doc
    if len(publications) != 1 or not any('Programa de participación ciudadana' in d['titulo'] for d in documents.values()):
        raise ValueError('PGOU announcement or participation programme missing/ambiguous')
    narrative = next(p.get_text(' ', strip=True) for p in article.select('p') if 'El Pleno Municipal acordó' in p.get_text())
    return {
        'id': 'azkoitia-proy-' + item['source_id'], 'municipio': 'Azkoitia',
        'codigo_ine': '20017', 'provincia': 'Gipuzkoa', 'titulo': item['titulo'],
        'tipo': 'planeamiento_urbanistico', 'url': item['url'], 'source': 'ayuntamiento',
        'origen': 'pgou_en_tramitacion', 'url_inventario': SOURCE,
        'fecha': None, 'fecha_acuerdo': agreement_date,
        'tipo_acuerdo': 'inicio del procedimiento de aprobación del PGOU',
        'fecha_publicacion': next(iter(publications)), 'fecha_aprob': None,
        'descripcion': narrative, 'documentos': list(documents.values()),
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class AzkoitiaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; municipio-azkoitia/1.0)'})
        response.raise_for_status()
        if len(response.content) > 4_000_000:
            raise ValueError('Source exceeds reviewed response size')
        capture = self.config.get('capture_dir')
        if capture:
            import hashlib
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pending, visited, items = [SOURCE], set(), {}
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Pagination safety limit reached; no partial output written')
            page_items, pages = parse_inventory(self._fetch(url), url)
            visited.add(url)
            items.update((item['source_id'], item) for item in page_items)
            pending.extend(page for page in pages if page not in visited)
        if not items:
            raise ValueError('No verified PGOU procedures in inventory')
        rows = [parse_project(self._fetch(item['url']), item) for item in items.values()]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'live_records': len(rows),
                'source_urls': sorted(visited | {item['url'] for item in items.values()}),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
