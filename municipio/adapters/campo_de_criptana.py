"""Current municipal planning dossiers, grouped by instrument, without inferred dates."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://transparencia.campodecriptana.es'
SOURCE = BASE + '/obras-publicas-y-urbanismo/'
DETAIL = re.compile(r'^(Texto Refundido Plan de Ordenación Municipal|Plan Parcial de Mejora|Modificaci[oó]n Puntual)\b', re.I)
LIMITATIONS = [
    'Partial current planning-document inventory, not a complete historical register or physical-works inventory.',
    'Mixed modifications-in-process page and empty PAU page excluded; procurement notices and licence data excluded.',
    'Document contents are not parsed: agreement, approval and publication dates and legal phase remain unknown.',
    'Page-update timestamps, instrument years and upload paths are not approval/publication dates.',
    'No verified coordinates or vector geometry; publication_ready=false.',
]


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.articleContent')
    if content is None:
        raise ValueError('Missing municipal article content')
    # This inventory is currently unpaginated. Fail explicitly if that changes.
    if content.select('[rel~=next], .pagination, .page-numbers, .nav-links, .elementor-pagination'):
        raise ValueError('Pagination detected; complete traversal requires review')
    if any(re.search(r'cargar m[aá]s|load more|siguiente', a.get_text(' ', strip=True), re.I)
           for a in content.select('a, button')):
        raise ValueError('Additional inventory results detected')
    return content


def discover_details(html, url=SOURCE):
    pages = {}
    for a in _content(html).select('a[href]'):
        title = a.get_text(' ', strip=True)
        if not DETAIL.match(title):
            continue
        target = urljoin(url, a['href'])
        if urlparse(target).hostname != urlparse(BASE).hostname:
            raise ValueError('Nonmunicipal planning detail URL')
        pages[target] = title
    if not pages:
        raise ValueError('No supported planning dossier pages found')
    return pages


def parse_detail(html, url, inventory_title):
    content = _content(html)
    heading = next((h for h in content.select('h1, h2, h3')
                    if DETAIL.match(h.get_text(' ', strip=True))), None)
    if not heading or not DETAIL.match(heading.get_text(' ', strip=True)):
        raise ValueError('Missing named planning instrument heading')
    agricultural = inventory_title.lower().startswith('plan parcial de mejora')
    groups = {}
    current = None
    all_links = set()
    for section in content.select('section.elementor-top-section'):
        links = [a for a in section.select('a[href]')
                 if urlparse(urljoin(url, a['href'])).path.lower().endswith('.pdf')]
        if not links:
            continue
        columns = section.select('.elementor-container > .elementor-column')
        label = columns[0].get_text(' ', strip=True) if len(columns) == 2 else ''
        if agricultural:
            if re.match(r'^(Plan Parcial|Modificaci[oó]n Puntual)\b', label, re.I):
                current = label
            if current is None:
                raise ValueError('Agricultural documents lack instrument grouping')
            title = current + ' — Polígono Industrial para Usos Agrícolas'
        else:
            title = heading.get_text(' ', strip=True)
        docs = groups.setdefault(title, {})
        for a in links:
            target = urljoin(url, a['href'])
            if urlparse(target).hostname != urlparse(BASE).hostname:
                raise ValueError('Unexpected nonmunicipal dossier document')
            docs[target] = {'titulo': a.get_text(' ', strip=True), 'url': target,
                            'contexto': label or None, 'source_url': url}
            all_links.add(target)
    expected = {urljoin(url, a['href']) for a in content.select('a[href]')
                if urlparse(urljoin(url, a['href'])).path.lower().endswith('.pdf')}
    if not groups or all_links != expected:
        raise ValueError('Missing or ungrouped planning documents')
    rows = []
    for title, docs in groups.items():
        identity = url + '#' + title if agricultural else url
        rows.append({
            'id': 'campo-de-criptana-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:20],
            'municipio': 'Campo de Criptana', 'codigo_ine': '13028', 'provincia': 'Ciudad Real',
            'titulo': title, 'tipo': 'instrumento de planeamiento urbanístico',
            'url': url, 'inventory_url': SOURCE, 'documentos': list(docs.values()),
            'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'fase': None,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    return rows


class CampoDeCriptanaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='campo-de-criptana', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, session, url):
        response = session.get(url, timeout=40)
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(BASE).hostname:
            raise ValueError('Unexpected source redirect')
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML source')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            folder = Path(capture_dir)
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (folder / name).write_text(response.text, encoding='utf-8')
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-campo-de-criptana/1.0'
            pages = discover_details(self._fetch(session, SOURCE))
            rows = []
            for url, title in pages.items():
                rows.extend(parse_detail(self._fetch(session, url), url, title))
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate instrument identities')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'source_urls': [SOURCE, *pages], 'coverage': 'partial_current_planning_inventory',
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Complete snapshot refresh; no timestamp cursor or historical completeness claim.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
