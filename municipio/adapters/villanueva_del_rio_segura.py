"""Discover the documented PGMO in the complete municipal Joomla archive."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.villanuevadelsegura.es'
INVENTORY = BASE + '/index.php'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def official_url(href, source):
    url = urljoin(source, href)
    p = urlparse(url)
    if p.hostname not in {'www.villanuevadelsegura.es', 'villanuevadelsegura.es', 'www.borm.es'}:
        raise ValueError('Unexpected source host: ' + url)
    return p._replace(scheme='https', netloc=('www.villanuevadelsegura.es' if p.hostname == 'villanuevadelsegura.es' else p.netloc), fragment='').geturl()


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    articles = soup.select('article.uk-article')
    if not articles:
        raise ValueError('Municipal archive markup missing')
    notices = {}
    for article in articles:
        a = article.select_one('.uk-article-title a[href]')
        if not a:
            raise ValueError('Archive article without detail link')
        title = a.get_text(' ', strip=True)
        if 'plan general municipal de ordenación' in title.lower():
            url = official_url(a['href'], INVENTORY)
            notices[url] = title
    offsets = set()
    for a in soup.select('ul.uk-pagination a[href]'):
        url = official_url(a['href'], INVENTORY)
        p = urlparse(url)
        qs = parse_qs(p.query)
        values = qs.get('start', qs.get('limitstart'))
        if p.path != '/index.php' or not values or len(values) != 1 or not values[0].isdigit():
            raise ValueError('Unsupported pagination: ' + url)
        offsets.add(int(values[0]))
    return notices, offsets


def parse_notice(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.uk-article')
    if article is None:
        raise ValueError('Missing PGMO article')
    heading = article.select_one('.uk-article-title')
    if not heading or 'plan general municipal de ordenación' not in heading.get_text(' ', strip=True).lower():
        raise ValueError('Not a PGMO notice')
    title = heading.get_text(' ', strip=True)
    text = article.get_text(' ', strip=True)
    docs = {}
    for a in article.select('a[href]'):
        href = a['href']
        if '/PGMO/' not in href and 'borm.es/services/anuncio/' not in href:
            continue
        target = official_url(href, url)
        label = a.get_text(' ', strip=True) or a.get('title') or title
        docs.setdefault(target, {'titulo': label, 'url': target, 'procedencia': url})
    if not docs:
        raise ValueError('PGMO notice without official documents')
    # Only the order explicitly dated in the municipal narrative establishes an
    # approval date. Filenames and crawl dates never establish publication dates.
    approval = None
    match = re.search(r'de fecha (\d{1,2}) de (\w+) de (\d{4}), relativa a aprobación definitiva parcial', text, re.I)
    if match:
        approval = date(int(match[3]), MONTHS.index(match[2].lower()) + 1, int(match[1])).isoformat()
    agreement = None
    match = re.search(r'sesión celebrada del (\d{2})\.(\d{2})\.(\d{2}), ha aprobado la subsanación', text)
    if match:
        agreement = date(2000 + int(match[3]), int(match[2]), int(match[1])).isoformat()
    return {'titulo': title, 'url': url, 'descripcion': text,
            'fecha_publicacion': None, 'fecha_aprob': approval, 'fecha_acuerdo': agreement,
            'documentos': list(docs.values())}


def group_notices(notices):
    if not notices:
        raise ValueError('No documented PGMO found')
    approvals = [n for n in notices if n['fecha_aprob']]
    if not approvals:
        raise ValueError('No dated PGMO approval narrative found; review source')
    latest = max(approvals, key=lambda n: n['fecha_aprob'])
    docs = {}
    for notice in sorted(notices, key=lambda n: n['url']):
        for doc in notice['documentos']:
            if doc['url'] not in docs:
                docs[doc['url']] = {'titulo': doc['titulo'], 'url': doc['url'], 'procedencias': []}
            if notice['url'] not in docs[doc['url']]['procedencias']:
                docs[doc['url']]['procedencias'].append(notice['url'])
    return [{
        'id': 'villanueva-del-rio-segura-pgmo', 'municipio': 'Villanueva del Río Segura',
        'codigo_ine': '30042', 'provincia': 'Murcia',
        'titulo': 'Plan General Municipal de Ordenación de Villanueva del Río Segura',
        'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación definitiva parcial y toma de conocimiento',
        'fecha': None, 'fecha_publicacion': None, 'fecha_aprob': latest['fecha_aprob'],
        'fecha_acuerdo': None, 'url': latest['url'], 'source': 'ayuntamiento',
        'origen': 'archivo_municipal_pgmo', 'descripcion': latest['descripcion'],
        'documentos': list(docs.values()), 'publicaciones': notices,
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'unavailable: linked plans are documents, no verified vector geometry',
        'cobertura': 'PGMO documentado; no inventario exhaustivo de obras, planeamiento de desarrollo o licencias',
    }]


class VillanuevaDelRioSeguraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-villanueva-del-rio-segura/1.0'})
        response.raise_for_status()
        official_url(response.url, url)
        if len(response.content) > 5_000_000:
            raise ValueError('Oversized municipal HTML')
        response.encoding = 'utf-8'
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    def backfill_proyectos(self, out_jsonl):
        pending, visited, found = {0}, set(), {}
        fingerprints = set()
        sources = []
        while pending:
            offset = min(pending)
            pending.remove(offset)
            if offset in visited:
                continue
            if len(visited) >= 200:
                raise ValueError('Archive exceeds safety limit; no partial output written')
            url = INVENTORY + ('?start=' + str(offset) if offset else '')
            html = self._fetch(url)
            digest = hashlib.sha256(html.encode()).hexdigest()
            if digest in fingerprints:
                raise ValueError('Pagination repeated a page')
            fingerprints.add(digest)
            notices, offsets = parse_inventory(html)
            found.update(notices)
            visited.add(offset)
            pending.update(offsets - visited)
            sources.append(url)
        notices = [parse_notice(self._fetch(url), url) for url in sorted(found)]
        rows = group_notices(notices)
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'inventory_pages': len(visited),
                'source_urls': sources + sorted(found), 'coverage': rows[0]['cobertura']}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
