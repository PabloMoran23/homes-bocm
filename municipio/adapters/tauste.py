"""Municipally linked PGOU document inventory; one instrument, many documents."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.tauste.es/urbanismo'
PLAN = 'https://sites.google.com/view/pgoutauste'
TABS = ('normas', 'planos', 'fichas', 'descargas')
LIMITATIONS = [
    'Partial coverage: only the municipally linked PGOU document inventory, not all municipal planning or works.',
    'Electronic transparency has a separate dynamic urbanism folder (420 items observed); it is outside this adapter scope. No licence register extracted.',
    'Document contents and legal consolidation/current validity are not verified; links are retained as published.',
    'Approval is stated only at month precision (December 2018); exact approval and publication dates are unknown.',
    'No verified geometry or coordinates; publication_ready is false.',
]


def _soup(html):
    return BeautifulSoup(html, 'html.parser')


def verify_municipal_link(html):
    soup = _soup(html)
    if 'Plan General de Ordenación Urbana de Tauste' not in soup.get_text(' ', strip=True):
        raise ValueError('Missing municipal PGOU heading')
    if not any(a.get('href', '').strip().rstrip('/') == PLAN for a in soup.select('a[href]')):
        raise ValueError('Municipal PGOU provenance link missing or changed')


def parse_projects(pages):
    """Parse all four inventory tabs, deduplicating documents by Drive ID."""
    if set(pages) != set(TABS):
        raise ValueError('Incomplete PGOU inventory tabs')
    documents = {}
    for tab in TABS:
        url = PLAN + '/' + tab
        soup = _soup(pages[tab])
        text = soup.get_text(' ', strip=True)
        if 'PGOU TAUSTE' not in text or not soup.select('a[href]'):
            raise ValueError('Missing PGOU inventory content')
        # This inventory has tabs, not record pagination. Reject new tabs or
        # pagination instead of silently omitting newly introduced content.
        for a in soup.select('a[href]'):
            target = urlparse(urljoin(url, a['href']))
            if target.hostname == 'sites.google.com' and target.path.startswith('/view/pgoutauste/'):
                if target.path.rstrip('/').rsplit('/', 1)[-1] not in TABS:
                    raise ValueError('Unrecognised PGOU tab')
            if a.get('rel') and 'next' in a['rel'] or re.search(r'^(siguiente|next|[»›])$', a.get_text(' ', strip=True), re.I):
                raise ValueError('Unexpected pagination in PGOU inventory')
        candidates = [(a.get_text(' ', strip=True), a['href']) for a in soup.select('a[href]')]
        candidates += [(e.get('aria-label', '').removeprefix('Drive, '), e.get('data-src') or e.get('src', ''))
                       for e in soup.select('iframe')]
        found = 0
        for label, href in candidates:
            parsed = urlparse(href)
            if parsed.hostname != 'drive.google.com':
                continue
            doc_id = parse_qs(parsed.query).get('id', [''])[0]
            if not doc_id:
                match = re.fullmatch(r'/file/d/([\w-]+)/preview', parsed.path)
                doc_id = match[1] if match else ''
            if not re.fullmatch(r'[\w-]{10,}', doc_id) or not label:
                continue
            found += 1
            doc = documents.setdefault(doc_id, {'url': 'https://drive.google.com/open?id=' + doc_id, 'titles': [], 'source_urls': []})
            if label not in doc['titles']:
                doc['titles'].append(label)
            if url not in doc['source_urls']:
                doc['source_urls'].append(url)
        if not found:
            raise ValueError('No document links in tab: ' + tab)
    norms = _soup(pages['normas']).get_text(' ', strip=True)
    # Preserve the source's imprecise date verbatim, never invent a day.
    approval = re.search(r'Texto refundido aprobado en [^.]+\.', norms, re.I)
    return [{
        'id': 'tauste-pgou-texto-refundido', 'municipio': 'Tauste',
        'codigo_ine': '50252', 'provincia': 'Zaragoza',
        'titulo': 'Plan General de Ordenación Urbana de Tauste — Texto refundido',
        'tipo': 'PGOU', 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
        'url': SOURCE, 'url_documento': PLAN, 'source_urls': [SOURCE] + [PLAN + '/' + t for t in TABS],
        'descripcion': approval[0] if approval else None,
        'fecha_aprob_texto': approval[0] if approval else None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'documentos': list(documents.values()),
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
        'limitations': LIMITATIONS,
    }]


class TausteAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='tauste', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def _fetch(self, url, capture):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-tauste/1.0 (public planning inventory)'})
        response.raise_for_status()
        if response.url.rstrip('/') != url.rstrip('/'):
            raise ValueError('Unexpected source redirect: ' + response.url)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture).write_text(response.text, encoding='utf-8')
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        verify_municipal_link(self._fetch(SOURCE, 'urbanismo.html'))
        pages = {t: self._fetch(PLAN + '/' + t, t + '.html') for t in TABS}
        rows = parse_projects(pages)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': rows[0]['source_urls'],
                'documents': len(rows[0]['documentos']), 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Complete bounded inventory refresh; no cursor or historical completeness claim.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
