"""Amurrio's municipal planning document inventories (complete page snapshots)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://udala.amurrio.eus'
PGOU = BASE + '/cas/pgou'
PLANES = BASE + '/cas/servicios/urbanismo-obras-y-servicios/urbanismo/planes-urbanismo'
SOURCES = (PGOU, PLANES)
LIMITATIONS = [
    'Partial municipal coverage: only the PGOU and Planes Urbanismo document inventories; not the provincial registry or all public works.',
    'Dates remain null: these HTML inventories do not identify publication or agreement dates. Linked PDF dates are not parsed.',
    'Only PGOU approval phase is explicit in the HTML. Other instruments have no inferred phase.',
    'No verified granted-licence register; licence extraction disabled.',
    'No instrument-linked vector geometry verified; PDF maps retained as documents, no invented coordinates.',
    'Document links are inventoried, not a guarantee that every linked file is currently downloadable.',
]


def _label(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _direct_label(node):
    return ' '.join(' '.join(str(t) for t in node.find_all(string=True)
                            if t.find_parent(['ul', 'ol']) == node.find_parent(['ul', 'ol'])).split())


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main#sp-component')
    if main is None:
        raise ValueError('Missing municipal main content')
    for a in soup.select('a[href]'):
        rel = a.get('rel', [])
        if ('next' in rel or a.find_parent(class_=re.compile(r'pagination|pagenav'))
                or _label(a).lower() in {'siguiente', 'next', 'hurrengoa', 'última', 'ultima'}
                or re.search(r'[?&](?:limitstart|start|page|cursor)=', a['href'])):
            raise ValueError('Pagination detected; refusing an incomplete snapshot')
    return main


def _documents(node, source):
    docs = {}
    for a in node.select('a[href]'):
        url = urljoin(source, a['href'])
        parsed = urlparse(url)
        if not parsed.path.lower().endswith('.pdf'):
            continue
        if parsed.scheme != 'https' or parsed.hostname != 'udala.amurrio.eus':
            raise ValueError('Unexpected planning document host')
        url = quote(unquote(url.split('#')[0]), safe=':/?=&%')
        docs.setdefault(url, {'titulo': _label(a), 'url': url, 'source_url': source})
    return list(docs.values())


def _record(title, docs, source, *, phase=None):
    if not docs or not title:
        raise ValueError('Planning instrument has no title or documents')
    key = hashlib.sha256((source + '#' + title.casefold()).encode()).hexdigest()[:16]
    return {
        'id': 'amurrio-plan-' + key, 'municipio': 'Amurrio', 'codigo_ine': '01002',
        'provincia': 'Álava', 'titulo': title, 'tipo': 'planeamiento_urbanistico',
        'fase': phase, 'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'url': source, 'inventory_url': source,
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
        'documentos': docs, 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'partial_municipal_document_inventory',
    }


def parse_pgou(html):
    main = _content(html)
    announcement = next((a for a in main.select('a[href]')
                         if _label(a) == 'ANUNCIO BOTHA APROBACIÓN DEFINITIVA'), None)
    if announcement is None:
        raise ValueError('PGOU approval document missing')
    root = announcement.find_parent('ul')
    if root is None:
        raise ValueError('PGOU document list missing')
    base_docs, modifications = {}, []
    for li in root.find_all('li', recursive=False):
        if _direct_label(li).upper() == 'MODIFICACIONES':
            modifications.append(li)
        else:
            for doc in _documents(li, PGOU):
                base_docs.setdefault(doc['url'], doc)
    if len(modifications) != 1:
        raise ValueError('PGOU modifications structure changed')
    rows = [_record('Plan General de Ordenación Urbana de Amurrio', list(base_docs.values()),
                    PGOU, phase='aprobación definitiva')]
    group = modifications[0].find('ul', recursive=False)
    if group is None:
        raise ValueError('Missing modifications list')
    title, docs = None, []
    for li in group.find_all('li', recursive=False):
        links = _documents(li, PGOU)
        if links:
            if title is None:
                raise ValueError('Ungrouped modification documents')
            docs.extend(links)
        else:
            if title is not None:
                rows.append(_record(title, list({d['url']: d for d in docs}.values()), PGOU))
            title, docs = _label(li), []
            if not re.match(r'^(Plan especial|Plan parcial|Modificación|Estudio de detalle)\b', title, re.I):
                raise ValueError('Unrecognized modification heading')
    if title is not None:
        rows.append(_record(title, list({d['url']: d for d in docs}.values()), PGOU))
    return rows


def parse_planes(html):
    main = _content(html)
    rows = []
    for li in main.select('li'):
        title = _direct_label(li)
        if not re.match(r'^(Modificación puntual|Plan especial|Plan parcial|Estudio de detalle)\b', title, re.I):
            continue
        rows.append(_record(title, _documents(li, PLANES), PLANES))
    if not rows:
        raise ValueError('No named planning instruments in Planes Urbanismo')
    return list({row['id']: row for row in rows}.values())


class AmurrioAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='amurrio', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = []
        for url, parser, name in ((PGOU, parse_pgou, 'pgou'), (PLANES, parse_planes, 'planes')):
            response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-amurrio/1.0'})
            response.raise_for_status()
            if response.url.rstrip('/') != url:
                raise ValueError('Unexpected municipal inventory redirect')
            if 'html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Inventory is not HTML')
            if self.config.get('capture_dir'):
                capture = Path(self.config['capture_dir'])
                capture.mkdir(parents=True, exist_ok=True)
                (capture / (name + '.html')).write_bytes(response.content)
            rows.extend(parser(response.text))
        ids = [r['id'] for r in rows]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate instrument identity')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Re-read both complete current inventories; no unsupported date cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
