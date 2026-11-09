"""Current official Llerena document inventories; one record per instrument.

This is a snapshot of three reviewed pages, not a licence or historical register.
PDFs and municipally linked Drive files retain their provenance; their contents
are not parsed for dates or geometry. Unexpected pagination/structure fails closed.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

PGM = 'https://www.llerena.org/ayuntamiento/plan-general-municipal/'
MODIFICATIONS = 'https://transparencia.llerena.org/urbanismo-obras-publicas-y-medioambiente/plan-urbanistico/'
WORKS = 'https://transparencia.llerena.org/urbanismo-obras-publicas-y-medioambiente/obras-publicas/obras-publicas/'
SOURCES = (PGM, MODIFICATIONS, WORKS)
MUNICIPAL_HOSTS = {'llerena.org', 'www.llerena.org', 'transparencia.llerena.org'}
MONTHS = ('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split()


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content .post-content')
    if content is None:
        raise ValueError('Missing municipal inventory content')
    if soup.select('[rel~=next], .pagination, .page-links, .nav-links, .wp-pagenavi'):
        raise ValueError('Pagination detected; extend crawler before accepting snapshot')
    for a in soup.select('a[href]'):
        if re.fullmatch(r'(siguiente(?:\s*»)?|next(?:\s*»)?|[»›])', a.get_text(' ', strip=True), re.I):
            raise ValueError('Pagination detected; no partial extraction allowed')
    return content


def _documents(block, source_url):
    docs = {}
    for a in block.select('a[href]'):
        target = urljoin(source_url, a['href'])
        parsed = urlparse(target)
        if parsed.scheme != 'https':
            raise ValueError('Unexpected document URL scheme')
        if parsed.fragment and parsed.path.rstrip('/') == urlparse(source_url).path.rstrip('/'):
            continue
        municipal = parsed.hostname in MUNICIPAL_HOSTS and parsed.path.lower().endswith('.pdf')
        drive = parsed.hostname == 'drive.google.com' and parsed.path.startswith('/file/d/')
        if not (municipal or drive):
            raise ValueError('Unexpected inventory link: ' + target)
        title = a.get_text(' ', strip=True)
        if not title:
            raise ValueError('Unnamed source document')
        docs.setdefault(target, {'titulo': title, 'url': target, 'source_url': source_url,
                                 'alojamiento': 'municipal' if municipal else 'enlace_externo_municipal'})
    if not docs:
        raise ValueError('Inventory has no source documents')
    return list(docs.values())


def _record(key, title, kind, source_url, docs):
    return {'id': 'llerena-' + key, 'municipio': 'Llerena', 'codigo_ine': '06074',
            'provincia': 'Badajoz', 'titulo': title, 'tipo': kind,
            'url': source_url, 'inventory_url': source_url,
            'source': 'ayuntamiento', 'origen': 'inventario_documental_municipal',
            'documentos': docs, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False}


def parse_pgm(html, source_url=PGM):
    content = _content(html)
    headings = {h.get_text(' ', strip=True) for h in content.select('h3')}
    if not {'Planos Llerena Información', 'Planos Llerena Ordenación', 'Información General'} <= headings:
        raise ValueError('Changed PGM inventory headings')
    docs = _documents(content, source_url)
    if not any(d['titulo'] == 'MEMORIA JUSTIFICATIVA' for d in docs) or not any(d['titulo'] == 'NORMATIVA' for d in docs):
        raise ValueError('PGM lacks technical/normative documents')
    return [_record('pgm', 'Plan General Municipal de Llerena', 'plan_general_municipal', source_url, docs)]


def _publication(label):
    match = re.fullmatch(r'Anuncio DOE\s+(\d{1,2})\s*[–-]\s*(\w+)\s*[–-]\s*(\d{4})', label, re.I)
    if not match or match[2].lower() not in MONTHS:
        raise ValueError('Unrecognized explicit DOE publication label')
    return date(int(match[3]), MONTHS.index(match[2].lower()) + 1, int(match[1])).isoformat()


def parse_modifications(html, source_url=MODIFICATIONS):
    content = _content(html)
    records = {}
    for tr in content.select('table tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells:
            continue
        title = cells[0].get_text(' ', strip=True)
        match = re.search(r'\bModificaci[oó]n\s+(\d+)/(\d{4})\b', title, re.I)
        if len(cells) != 3 or not match:
            raise ValueError('Unrecognized planning inventory row')
        key = 'modificacion-' + match[1] + '-' + match[2]
        docs = _documents(tr, source_url)
        notices = [d for d in docs if d['titulo'].lower().startswith('anuncio doe')]
        if len(notices) != 1 or len(docs) < 2:
            raise ValueError('Modification lacks unambiguous notice/supporting documents')
        row = _record(key, title, 'modificacion_plan_general', source_url, docs)
        row['referencia'] = match[1] + '/' + match[2]
        row['fecha_publicacion'] = _publication(notices[0]['titulo'])
        row['fecha_publicacion_fuente'] = notices[0]['url']
        if title.lower().startswith('aprobación definitiva.'):
            row['fase'] = 'aprobación definitiva'
        if key in records:
            raise ValueError('Duplicate instrument reference; review grouping')
        records[key] = row
    if not records:
        raise ValueError('No named modification instruments')
    return list(records.values())


def parse_works(html, source_url=WORKS):
    content = _content(html)
    docs = _documents(content, source_url)
    projects = [d for d in docs if d['titulo'].startswith('Proyecto de construcción de nuevos nichos en el Cementerio Municipal')]
    # The reviewed flat list is a single project followed by its public notice.
    # A new project/layout requires explicit grouping, never a silent omission.
    if len(projects) != 1 or len(docs) != 2 or not any(
        d['titulo'] == 'Anuncio exposición pública construcción nuevo módulo en el Cementerio Municipal' for d in docs
    ):
        raise ValueError('Changed works inventory; review project/document grouping')
    if '(Módulo K)' not in projects[0]['titulo']:
        raise ValueError('Missing cemetery module identifier')
    return [_record('cementerio-modulo-k', projects[0]['titulo'], 'proyecto_obra_publica', source_url, docs)]


class LlerenaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory-llerena/1.0)'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in MUNICIPAL_HOSTS or urlparse(response.url).path != urlparse(url).path:
            raise ValueError('Unexpected source redirect')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected HTML inventory')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            stem = hashlib.sha256(url.encode()).hexdigest()[:16]
            (directory / (stem + '.html')).write_bytes(response.content)
            (directory / (stem + '.json')).write_text(json.dumps({
                'source_url': url, 'resolved_url': response.url, 'status': response.status_code,
                'sha256': hashlib.sha256(response.content).hexdigest()}, indent=2), encoding='utf-8')
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(output)

    def backfill_proyectos(self, out_jsonl):
        rows = []
        for source, parser in zip(SOURCES, (parse_pgm, parse_modifications, parse_works)):
            rows.extend(parser(self._fetch(source), source))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES),
                'coverage': 'three_current_document_inventories', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register; forms excluded'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
