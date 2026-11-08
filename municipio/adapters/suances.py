"""Suances: two municipal inventories, grouped instruments and physical works.

Snapshot of published content, not a complete register or confirmation that old
works are still under construction. Dates and geometry require separate evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

PGOU_URL = 'https://suances.es/ayuntamiento/plan-general-de-ordenacion-urbana/'
WORKS_URL = 'https://suances.es/ayuntamiento/proyectos-en-curso/'
REGISTER_URL = 'https://aplicacionesweb.cantabria.es/aucan/public/zona/costacentral/suances'
LIMITATIONS = [
    'Partial coverage: municipal PGOU and Proyectos en Curso inventories only; public notices and the regional register are not enumerated.',
    'Works inventory retains 2022/23 references; current execution/completion status is unverified.',
    'Document links are retained as municipal provenance; linked document contents and availability are not exhaustively verified.',
    'No verified publication/agreement/approval dates, project geometry or granted-licence register.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('[data-elementor-type="wp-page"]')
    if content is None:
        raise ValueError('Missing municipal inventory content')
    # These are full static pages, including all collapsed accordion bodies.
    # Refuse changed paginated markup rather than silently taking page one.
    if soup.select('a[rel~="next"], .pagination, .page-numbers, .nav-links, .elementor-pagination'):
        raise ValueError('Pagination detected; inventory traversal needs review')
    return content


def _record(key, title, kind, source_url, description):
    return {
        'id': 'suances-proy-' + hashlib.sha256(key.encode()).hexdigest()[:20],
        'municipio': 'Suances', 'codigo_ine': '39085', 'provincia': 'Cantabria',
        'titulo': title, 'tipo': kind, 'descripcion': description,
        'url': source_url, 'inventory_url': source_url,
        'source': 'ayuntamiento', 'origen': 'inventario_municipal',
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'documentos': [],
    }


def _links(node, source_url, section=None):
    docs = []
    seen = set()
    for a in node.select('a[href]'):
        href = a['href'].strip()
        if not href or href.startswith('#'):
            continue
        target = urljoin(source_url, href)
        parsed = urlparse(target)
        if parsed.scheme not in ('http', 'https') or parsed.hostname not in (
            'suances.es', 'www.suances.es', 'suancesurbanismo.atys.net', 'aplicacionesweb.cantabria.es'
        ):
            raise ValueError('Unexpected document origin: ' + target)
        if target in seen:
            continue
        seen.add(target)
        title = _text(a) or (a.img.get('alt') if a.img else '') or parsed.path.rsplit('/', 1)[-1]
        doc = {'titulo': title, 'url': target, 'provenance_url': source_url,
               'role': 'imagen' if re.search(r'\.(?:jpe?g|png)$', parsed.path, re.I) else 'documento'}
        if section:
            doc['seccion'] = section
        docs.append(doc)
    return docs


def parse_planning(html):
    content = _content(html)
    headings = [_text(h) for h in content.select('h2')]
    expected = ['PGOU - VIGENTE', 'Avance aprobación inicial nuevo PGOU (no vigente)', 'Informe sostenibilidad']
    if headings != expected:
        raise ValueError('Planning sections changed; cannot establish instrument grouping')
    current = _record(PGOU_URL + '#vigente', 'Plan General de Ordenación Urbana de Suances — vigente',
                      'PGOU', PGOU_URL, expected[0])
    draft = _record(PGOU_URL + '#nuevo', 'Nuevo Plan General de Ordenación Urbana de Suances — no vigente',
                    'PGOU', PGOU_URL, expected[1] + '. ' + expected[2])
    current['vigente'], draft['vigente'] = True, False
    current['estado_segun_fuente'], draft['estado_segun_fuente'] = expected[:2]
    current['fase'], draft['fase'] = None, None
    section = None
    for node in content.find_all(['h2', 'a']):
        if node.name == 'h2':
            section = _text(node)
            continue
        # Parse individual anchors without using surrounding accordion documents.
        docs = _links(BeautifulSoup(str(node), 'html.parser'), PGOU_URL, section)
        for doc in docs:
            if section == expected[0]:
                if doc['url'] != REGISTER_URL:
                    raise ValueError('Unexpected current PGOU register link')
                doc['role'] = 'registro_planeamiento'
                current['documentos'].append(doc)
            else:
                # Allegation application is an ancillary form, never an instrument.
                if doc['titulo'].casefold() == 'instancia':
                    doc['role'] = 'formulario_alegaciones'
                draft['documentos'].append(doc)
    for row in (current, draft):
        row['documentos'] = list({d['url']: d for d in row['documentos']}.values())
    if len(current['documentos']) != 1 or not any(
        d['titulo'].casefold() == 'memoria' and d.get('seccion') == expected[1]
        for d in draft['documentos']
    ) or not any(d.get('seccion') == expected[2] for d in draft['documentos']):
        raise ValueError('Missing PGOU dossier links')
    return [current, draft]


def parse_works(html):
    content = _content(html)
    records = {}
    for card in content.select('.elementskit-card'):
        heading = card.select_one('.ekit-accordion-title')
        body = card.select_one('.elementskit-card-body')
        if heading is None or body is None:
            raise ValueError('Incomplete public works card')
        title, description = _text(heading), _text(body)
        # A card must describe a physical work, not a procedure or unrelated news.
        if re.search(r'licencia|solicitud|formulario|licitaci[oó]n|contrataci[oó]n|anuncio', title, re.I):
            continue
        if not re.match(r'^(Rehabilitación|Reurbanización|Nueva oficina|Segunda fase Paseo|Renovación campo)\b', title):
            raise ValueError('Unrecognised work card: ' + title)
        if len(description) < 80 or not re.search(r'proyecto|trabajos|obras?', description, re.I):
            raise ValueError('Work lacks a substantive description: ' + title)
        identity = unicodedata.normalize('NFKC', title).casefold()
        row = _record(WORKS_URL + '#' + identity, title, 'obra pública', WORKS_URL, description)
        row['documentos'] = _links(body, WORKS_URL)
        row['fase'] = None
        row['estado_actual_verificado'] = False
        if row['id'] in records:
            raise ValueError('Duplicate physical work identity')
        records[row['id']] = row
    if not records:
        raise ValueError('No physical public works in inventory')
    return list(records.values())


class SuancesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='suances', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://suances.es')

    def backfill_proyectos(self, out_jsonl: Path):
        rows = []
        capture_dir = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'
            for name, url, parser in [('pgou', PGOU_URL, parse_planning), ('proyectos', WORKS_URL, parse_works)]:
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if response.url.rstrip('/') != url.rstrip('/') or 'text/html' not in response.headers.get('Content-Type', ''):
                    raise ValueError('Unexpected inventory response: ' + response.url)
                response.encoding = 'utf-8'
                if capture_dir:
                    capture = Path(capture_dir)
                    capture.mkdir(parents=True, exist_ok=True)
                    (capture / (name + '.html')).write_text(response.text, encoding='utf-8')
                rows.extend(parser(response.text))
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'source_urls': [PGOU_URL, WORKS_URL], 'limitations': LIMITATIONS,
                'coverage': 'two_complete_static_inventories_partial_municipal_coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
