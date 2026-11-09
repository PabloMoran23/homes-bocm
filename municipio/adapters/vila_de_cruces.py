"""Partial official planning inventory; refreshes the two municipal surfaces.

No licence grants, inferred legal currency, PDF dates or synthetic geometry.
"""
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

BASE = 'https://viladecruces.es'
URBANISMO = BASE + '/urbanismo/'
INVENTORY = BASE + '/ordenanzas/'
LIMITATIONS = [
    'Partial coverage: Urbanismo page and planning instruments linked from Ordenanzas only; not all municipal works or planning history.',
    'Phases describe the cited publication, not independently verified current legal status.',
    'PDF and Nextcloud links retained as published; their contents are not parsed by the adapter. Agreement dates in those documents remain null.',
    'No public register of granted licences verified; application forms and procurement notices excluded.',
    'No verified coordinates or geometry; publication_ready=false.',
]


def _soup(html):
    return BeautifulSoup(html, 'html.parser')


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _official(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.netloc != 'viladecruces.es':
        raise ValueError('Unexpected municipal source URL: ' + url)
    return url


def _record(key, title, url):
    return {
        'id': 'vila-de-cruces-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
        'municipio': 'Vila de Cruces', 'provincia': 'Pontevedra', 'codigo_ine': '36059',
        'titulo': title, 'url': url, 'source': 'ayuntamiento',
        'origen': 'planeamiento_municipal', 'fecha': None,
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'unavailable', 'documentos': [],
        'coverage': 'partial_municipal_planning_inventory',
    }


def parse_urbanismo(html):
    body = _soup(html).select_one('article .jupiterx-post-content')
    if body is None:
        raise ValueError('Urbanismo content missing')
    paragraphs = [_text(p) for p in body.select('p') if _text(p)]
    agreement = next((p for p in paragraphs if 'O Concello de Vila de Cruces acordou no Pleno' in p
                      and 'aprobación inicial do Plan Xeral de Ordenación Municipal' in p), '')
    match = re.search(r'día (\d{1,2}) de (\w+) de (\d{4})', agreement)
    months = 'xaneiro febreiro marzo abril maio xuño xullo agosto setembro outubro novembro decembro'.split()
    if not match or match[2] not in months:
        raise ValueError('Verified PXOM agreement narrative missing or changed')
    agreed = date(int(match[3]), months.index(match[2]) + 1, int(match[1])).isoformat()
    row = _record('pxom', 'Plan Xeral de Ordenación Municipal de Vila de Cruces (PXOM)', URBANISMO)
    row.update(tipo='PXOM', fase='aprobación inicial', fecha_acuerdo=agreed,
               fecha_aprob=agreed, descripcion='\n'.join(paragraphs),
               phase_scope='Approval reported by the source; current legal status not verified')
    # The live page names a document link but currently provides no href.
    for a in body.select('a[href]'):
        href = urljoin(URBANISMO, a['href'])
        if urlsplit(href).path.lower().endswith('.pdf'):
            row['documentos'].append({'titulo': _text(a), 'url': href, 'source_url': URBANISMO})
    return row


def _planning_title(title):
    return bool(re.match(r'^(?:APROBACIÓN (?:INICIAL|DEFINITIVA) (?:DA|DO) )?'
                         r'(?:MODIFICACIÓN PUNTUAL .*NORMAS SUBSIDIARIAS|PLAN (?:XERAL|ESPECIAL|PARCIAL)|ESTUDO DE DETALLE)\b',
                         title, re.I))


def parse_inventory(html, url):
    soup = _soup(html)
    body = soup.select_one('main')
    if body is None or not body.select('.raven-post-title a[href]'):
        raise ValueError('Ordenanzas inventory missing or changed')
    if body.select('.raven-load-more, .raven-pagination-load-more, [data-next-page]'):
        raise ValueError('Unsupported dynamic pagination; refusing partial snapshot')
    details = []
    for a in body.select('.raven-post-title a[href]'):
        if _planning_title(_text(a)):
            details.append(_official(urljoin(url, a['href'])))
    # Walk every explicit pagination URL, not just the first page.
    pages = []
    for a in body.select('a.page-numbers[href], .pagination a[href], .raven-pagination a[href], a[rel="next"][href]'):
        target = _official(urljoin(url, a['href']))
        if target != url and target not in pages:
            pages.append(target)
    return list(dict.fromkeys(details)), pages


def parse_instrument(html, url):
    soup = _soup(html)
    heading = soup.select_one('main h1')
    body = soup.select_one('article .jupiterx-post-content')
    if heading is None or body is None or not _planning_title(_text(heading)):
        raise ValueError('Not a named planning instrument: ' + url)
    documents = {}
    for a in body.select('a[href]'):
        target = urljoin(url, a['href'])
        p = urlsplit(target)
        if p.scheme == 'https' and (p.netloc == 'viladecruces.es' and p.path.lower().endswith('.pdf')
                                   or p.netloc == 'nextcloud.viladecruces.gal' and p.path.startswith('/s/')):
            documents.setdefault(target, {'titulo': _text(a), 'url': target, 'source_url': url})
    if not documents:
        raise ValueError('Instrument has no published supporting documents: ' + url)
    title = _text(heading)
    row = _record(url, title, url)
    timestamp = soup.select_one('article time[itemprop="datePublished"][datetime]')
    if timestamp:
        row['fecha_publicacion'] = date.fromisoformat(timestamp['datetime'][:10]).isoformat()
    row.update(tipo='instrumento de planeamiento', inventory_url=INVENTORY,
               documentos=list(documents.values()), descripcion=_text(body),
               fase='aprobación inicial' if title.upper().startswith('APROBACIÓN INICIAL') else
                    'aprobación definitiva' if title.upper().startswith('APROBACIÓN DEFINITIVA') else None)
    return row


class VilaDeCrucesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='vila-de-cruces', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        _official(url)
        response = requests.get(url, timeout=45, headers={
            'User-Agent': 'municipio-vila-de-cruces/1.0 (public planning inventory)'})
        response.raise_for_status()
        _official(response.url)
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML inventory: ' + url)
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (folder / name).write_text(response.text, encoding='utf-8')
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        rows = [parse_urbanismo(self._fetch(URBANISMO))]
        sources = [URBANISMO]
        pending, visited, instruments = [INVENTORY], set(), set()
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 200:
                raise ValueError('Pagination exceeded safety bound; no truncated output written')
            details, pages = parse_inventory(self._fetch(url), url)
            visited.add(url)
            sources.append(url)
            instruments.update(details)
            pending.extend(p for p in pages if p not in visited)
        for url in sorted(instruments):
            rows.append(parse_instrument(self._fetch(url), url))
            sources.append(url)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources,
                'inventory_pages': len(visited), 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full snapshot of selected surfaces; no date cutoff or implicit history cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': LIMITATIONS[3]}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
