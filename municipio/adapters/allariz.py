"""Municipal planning document inventories; no inferred approvals or geometry."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

PXOM_URL = 'https://www.allariz.gal/admin/plan-xeral-de-organizacion-municipal/'
PECHA_URL = 'https://pecha.allariz.gal/'
LIMITATIONS = [
    'Partial coverage: the municipal planning download page and PECHA public-exhibition portal only; no complete works or licence register.',
    'PERI and encauzamento table dates have unspecified meaning; retained on documents only, never as publication or agreement dates.',
    'No approval/publication dates extracted; PECHA phase is the portal label, not a verified dated agreement.',
    'PDF links retained, not individually downloaded or parsed; no verified feature geometry or coordinates.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href], link[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if ('next' in a.get('rel', []) or
                label in {'next', 'siguiente', 'seguinte', 'seguinte páxina', '›', '»'} or
                a.find_parent(class_=re.compile(r'pagination|paginacion|paginación|nav-links')) or
                'page-numbers' in a.get('class', [])):
            if a['href'] not in {'', '#'}:
                raise ValueError('Pagination detected: inventory coverage must be reviewed')
    return soup


def _document(a, source, title, **extra):
    target = urljoin(source, a['href'])
    parsed = urlparse(target)
    if (parsed.scheme != 'https' or parsed.hostname != urlparse(source).hostname or
            not parsed.path.lower().endswith('.pdf') or not parsed.path.startswith('/wp-content/uploads/')):
        raise ValueError(f'Unexpected planning document URL: {target}')
    return {'titulo': title, 'url': target, 'source_url': source, **extra}


def _record(key, title, source, docs, phase=None):
    if not docs:
        raise ValueError(f'No source documents for {key}')
    return {
        'id': 'allariz-plan-' + key, 'municipio': 'Allariz', 'codigo_ine': '32001',
        'provincia': 'Ourense', 'titulo': title, 'tipo': 'instrumento_planeamiento',
        'url': source, 'source': 'ayuntamiento', 'origen': 'inventario_documental_municipal',
        'documentos': list(docs.values()), 'fase': phase,
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False,
    }


def parse_pxom(html):
    soup = _soup(html)
    titles = {
        'Plan Especial de Reforma Interior (PERI)': ('peri', 'Plan Especial de Reforma Interior (PERI)'),
        'Normativa e Planos do Plan Xeral Vixente': ('pxom', 'Plan Xeral de Ordenación Municipal de Allariz (PXOM)'),
        'Outros Plans e Normativas': ('encauzamento', 'Plan de Encauzamento do Concello de Allariz'),
    }
    groups = {key: {} for key, _ in titles.values()}
    current = None
    for element in soup.select('h2, table.tabla-documentos'):
        if element.name == 'h2':
            current = titles.get(element.get_text(' ', strip=True), (None, None))[0]
            continue
        for tr in element.select('tr'):
            anchors = tr.select('a[href]')
            if not anchors:
                continue
            if current is None:
                raise ValueError('Unrecognized planning section contains documents')
            cells = tr.find_all('td', recursive=False)
            texts = [c.get_text(' ', strip=True) for c in cells]
            date = None
            if texts and re.fullmatch(r'\d{2}/\d{2}/\d{4}', texts[0]):
                date = datetime.strptime(texts.pop(0), '%d/%m/%Y').date().isoformat()
            title = ' '.join(t for t in texts if t)
            if not title:
                raise ValueError('Document row lacks title')
            for a in anchors:
                doc = _document(a, PXOM_URL, title, fecha_fuente=date,
                                significado_fecha='no especificado' if date else None)
                groups[current].setdefault(doc['url'], doc)
    return [_record(key, title, PXOM_URL, groups[key],
                    'vixente' if key == 'pxom' else None)
            for key, title in titles.values()]


def parse_pecha(html):
    soup = _soup(html)
    main = soup.select_one('main')
    if main is None or not main.find('h1', string=re.compile('Documentación PECHA')):
        raise ValueError('Missing PECHA inventory heading')
    phase = next((h.get_text(' ', strip=True) for h in main.select('h2')
                  if h.get_text(' ', strip=True).startswith('Fase aprobación inicial: Exposición pública')), None)
    if not phase:
        raise ValueError('Unrecognized PECHA phase; review source')
    docs = {}
    for a in main.select('a[href]'):
        if not urlparse(a['href']).path.lower().endswith('.pdf'):
            continue
        # The allegation form is a procedure, not an instrument document.
        filename = unquote(urlparse(a['href']).path).split('/')[-1]
        if filename == 'Allariz_modelo-de-alegacion-1.pdf':
            continue
        if not filename.startswith('32001_PECHA_'):
            raise ValueError('Unrecognized PECHA PDF; review grouping before extraction')
        label = a.get_text(' ', strip=True).removeprefix('📄').strip()
        doc = _document(a, PECHA_URL, label)
        docs.setdefault(doc['url'], doc)
    names = [unquote(urlparse(u).path).split('/')[-1] for u in docs]
    if not any('_AI_NU' in n for n in names) or not any('_AI_MX_' in n for n in names):
        raise ValueError('Missing PECHA normative or explanatory documents')
    return [_record('pecha-ai', 'Plan Especial Casco Histórico Allariz (PECHA)', PECHA_URL, docs, phase)]


class AllarizAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, name):
        with requests.get(url, timeout=(10, 40), stream=True,
                          headers={'User-Agent': 'municipio-allariz/1.0 (public planning inventory)'}) as response:
            response.raise_for_status()
            if response.url != url:
                raise ValueError('Unexpected inventory redirect')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 4_000_000:
                    raise ValueError('Inventory exceeds reviewed response size')
            html = content.decode('utf-8')
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = parse_pxom(self._fetch(PXOM_URL, 'pxom.html'))
        rows.extend(parse_pecha(self._fetch(PECHA_URL, 'pecha.html')))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'source_urls': [PXOM_URL, PECHA_URL], 'limitations': LIMITATIONS,
                'coverage': 'two_complete_single_page_document_inventories', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot, deliberately no date-based filtering or pagination cap.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
