"""Astigarraga's public PGOU development inventory (a partial municipal snapshot)."""
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

BASE = 'https://www.astigarraga.eus'
SOURCE = BASE + '/es/desarrollo-del-pgou'
LIMITATIONS = [
    'Partial municipal coverage: only the public Desarrollo del PGOU inventory; '
    'excludes PGOU general plan, modifications inventory, revision, news and procurement.',
    'Publication dates are the index labels, not agreement, approval or document-upload dates.',
    'No approval phase, agreement dates, granted licences or verified geometry extracted.',
    'Attachments are retained as source links; their contents are not parsed for dates or geometry.',
    'Current website snapshot includes historical instruments; not a complete historical register '
    'and does not establish current legal validity or construction progress.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _official(url, prefix):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'www.astigarraga.eus' or not parts.path.startswith(prefix):
        raise ValueError('Unexpected municipal source URL: ' + url)
    return url


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#main-content')
    if main is None or 'Desarrollo del PGOU' not in _text(main):
        raise ValueError('Missing PGOU development inventory')
    # Reviewed source is a static, unpaginated inventory. Fail closed if controls
    # appear: callers must extend the crawler before accepting a partial snapshot.
    if main.select('.pagination, .lfr-pagination, .taglib-page-iterator, [rel="next"], [class*="paginador"]'):
        raise ValueError('Pagination detected; crawler must be extended')
    for a in main.select('a[href]'):
        if (_text(a).lower() in {'siguiente', 'next', 'hurrengoa', '›', '»'}
                or re.search(r'(?:[?&]|_)(?:cur|page|start)=', a['href'], re.I)):
            raise ValueError('Pagination detected; crawler must be extended')
    rows = {}
    for block in main.select('.destacado_contenido'):
        a = block.select_one('.titulo a[href]')
        if a is None:
            raise ValueError('Inventory item without title/link')
        title = _text(a)
        if not re.match(r'^(?:\d+ª modificación|Plan especial|Modificación puntual|Proyecto de Urbanización)\b', title, re.I):
            raise ValueError('Unreviewed inventory item: ' + title)
        url = _official(urljoin(SOURCE, a['href']), '/es/-/').split('?')[0].split('#')[0]
        date_node = block.select_one('.pre-titulo')
        match = re.fullmatch(r'Fecha de publicación:\s*(\d{2}-\d{2}-\d{4})', _text(date_node)) if date_node else None
        if match is None:
            raise ValueError('Missing explicit publication date: ' + title)
        publication = datetime.strptime(match[1], '%d-%m-%Y').date().isoformat()
        row = {
            'id': 'astigarraga-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'municipio': 'Astigarraga', 'codigo_ine': '20903', 'provincia': 'Gipuzkoa',
            'titulo': title, 'tipo': 'instrumento o proyecto urbanístico',
            'url': url, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'desarrollo_del_pgou', 'fecha_publicacion': publication,
            'fecha_acuerdo': None, 'fecha_aprob': None, 'fase': None,
            'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'partial_municipal_inventory',
        }
        if url in rows and rows[url] != row:
            raise ValueError('Conflicting inventory entries: ' + url)
        rows[url] = row
    if not rows:
        raise ValueError('Empty PGOU development inventory')
    return list(rows.values())


def parse_documents(html: str, row: dict) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    assets = soup.select('#main-content .asset-full-content')
    if len(assets) != 1:
        raise ValueError('Expected one instrument detail')
    asset = assets[0]
    title = asset.select_one('.asset-title')
    article = asset.select_one('.journal-content-article')
    if title is None or _text(title) != row['titulo'] or article is None:
        raise ValueError('Inventory/detail title mismatch: ' + row['url'])
    docs = {}
    for a in article.select('a[href]'):
        url = urljoin(row['url'], a['href'])
        if '/documents/' not in urlsplit(url).path:
            continue
        _official(url, '/documents/')
        key = url.split('?')[0].split('#')[0]
        label = _text(a)
        if not label:
            raise ValueError('Unlabelled source attachment')
        docs.setdefault(key, {'titulo': label, 'url': url, 'source_url': row['url']})
    if not docs:
        raise ValueError('Instrument has no source documents: ' + row['url'])
    return list(docs.values())


class AstigarragaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        _official(url, '/es/')
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-astigarraga/1.0 (public planning inventory)',
        })
        response.raise_for_status()
        _official(response.url, '/es/')
        if urlsplit(response.url).path != urlsplit(url).path:
            raise ValueError('Unexpected source redirect')
        if 'text/html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML source')
        response.encoding = 'utf-8'
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(output)

    def backfill_proyectos(self, out_jsonl):
        rows = parse_inventory(self._fetch(SOURCE))
        for row in rows:
            row['documentos'] = parse_documents(self._fetch(row['url']), row)
        # Replace output only after the entire inventory and all details validate.
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + [r['url'] for r in rows],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        """Refresh the full current inventory; no date cutoff hides older instruments."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
