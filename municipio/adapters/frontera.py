"""Frontera's municipal planning inventory; one row per instrument, not PDF."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.aytofrontera.org/ayuntamiento/planeamiento.html'
HOST = 'www.aytofrontera.org'
PLAN_TITLE = re.compile(r'^Plan (?:General de Ordenaci[oó]n|Belgara\b)', re.I)
MODIFICATION = re.compile(r'^(?:Aprobaci[oó]n\s+)?modificaci[oó]n\s+menor\s+unidad de actuaci[oó]n\b', re.I)


def official_url(href: str, base: str) -> str:
    url = urldefrag(urljoin(base, href))[0]
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != HOST:
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def content(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#sp-page-builder')
    if main is None:
        raise ValueError('Municipal planning content container missing')
    # This is a single-page inventory. Fail visibly if pagination is introduced.
    for a in soup.select('a[href]'):
        href = a['href']
        label = a.get_text(' ', strip=True).lower()
        if (a.get('rel') and 'next' in a['rel']) or re.search(r'[?&](?:start|limitstart|page)=', href) or label in {'siguiente', 'next', 'último', 'ultima', 'última'}:
            raise ValueError('Pagination detected; inventory coverage must be reviewed')
    if main.select('.pagination, .pager'):
        raise ValueError('Pagination detected in planning content')
    return main


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    plans = {}
    for a in content(html).select('.sppb-addon-text-block a[href]'):
        title = a.get_text(' ', strip=True)
        if not PLAN_TITLE.match(title):
            continue
        target = official_url(a['href'], url)
        if not urlparse(target).path.endswith('.html'):
            raise ValueError('Planning entry is no longer a detail page')
        plans.setdefault(target, {'titulo': title, 'url': target})
    if not plans:
        raise ValueError('No named planning instruments in municipal inventory')
    return list(plans.values())


def record(title: str, url: str, documents: list[dict], inventory_url: str) -> dict:
    return {
        'id': 'frontera-plan-' + hashlib.sha256(url.encode()).hexdigest()[:20],
        'municipio': 'Frontera', 'codigo_ine': '38013',
        'provincia': 'Santa Cruz de Tenerife', 'titulo': title,
        'tipo': 'planeamiento_urbanistico', 'url': url,
        'inventory_url': inventory_url, 'source': 'ayuntamiento',
        'origen': 'inventario_municipal_planeamiento', 'documentos': documents,
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


def parse_instrument(html: str, entry: dict, inventory_url: str = SOURCE) -> list[dict]:
    main = content(html)
    heading = main.select_one('.sppb-addon-header .sppb-addon-title')
    if heading is None or not PLAN_TITLE.match(heading.get_text(' ', strip=True)):
        raise ValueError('Planning detail title missing or unsupported')
    docs, amendments = {}, {}
    for a in main.select('.sppb-addon-text-block a[href]'):
        if not urlparse(urljoin(entry['url'], a['href'])).path.lower().endswith('.pdf'):
            continue
        url = official_url(a['href'], entry['url'])
        title = a.get_text(' ', strip=True)
        if not title:
            raise ValueError('Untitled planning document')
        doc = {'titulo': title, 'url': url, 'source_url': entry['url']}
        if MODIFICATION.match(title):
            amendments.setdefault(title, {})[url] = doc
        else:
            docs.setdefault(url, doc)
    if not docs:
        raise ValueError('Planning instrument has no linked documents')
    rows = [record(heading.get_text(' ', strip=True), entry['url'], list(docs.values()), inventory_url)]
    for title, documents in amendments.items():
        # An explicitly named amendment is separate from the parent PGO sheets.
        row = record(title, next(iter(documents)), list(documents.values()), inventory_url)
        row['parent_url'] = entry['url']
        rows.append(row)
    return rows


class FronteraAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url: str) -> str:
        official_url(url, SOURCE)
        response = requests.get(url, timeout=45, headers={
            'User-Agent': 'municipio-frontera/1.0 (public planning inventory)',
        })
        response.raise_for_status()
        official_url(response.url, SOURCE)
        if urlparse(response.url).path != urlparse(url).path:
            raise ValueError('Unexpected planning page redirect')
        response.encoding = 'utf-8'
        html = response.text
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / Path(urlparse(url).path).name).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        entries = parse_inventory(self._fetch(SOURCE))
        rows = []
        for entry in entries:
            rows.extend(parse_instrument(self._fetch(entry['url']), entry))
        if len({row['id'] for row in rows}) != len(rows):
            raise ValueError('Duplicate instrument identities; review grouping')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows),
                'coverage': 'current_municipal_planning_inventory',
                'source_urls': [SOURCE] + [entry['url'] for entry in entries],
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full snapshot: all published documents can change without dated notices.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
