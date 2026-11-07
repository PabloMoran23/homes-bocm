"""Partial municipal planning inventory: PGOU package and El Plano study."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://cuartedehuerva.es'
SOURCE = BASE + '/ayuntamiento/urbanismo'
PAGES = {name: SOURCE + '/' + name for name in
         ('plan-general-de-ordenacion-urbana', 'memoria', 'planos')}
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def spanish_date(day, month, year):
    return date(int(year), MONTHS.index(month.lower()) + 1, int(day)).isoformat()


def content(html, heading):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.select_one('#body_content_title')
    body = soup.select_one('#body_content_left')
    if title is None or title.get_text(' ', strip=True) != heading or body is None:
        raise ValueError('Missing municipal content: ' + heading)
    if soup.select('a[rel~=next]') or body.select('.pagination, .pager'):
        raise ValueError('Unexpected pagination: coverage must be reviewed')
    return body


def documents(body, source_url):
    found = {}
    for a in body.select('a[href]'):
        target = urljoin(source_url, a['href'])
        parsed = urlparse(target)
        if not parsed.path.lower().endswith('.pdf'):
            continue
        if parsed.scheme != 'https' or parsed.hostname != 'cuartedehuerva.es' or not parsed.path.startswith('/system/resources/'):
            raise ValueError('Unexpected document origin: ' + target)
        label = a.get_text(' ', strip=True) or a.get('title') or unquote(parsed.path.rsplit('/', 1)[-1])
        found[target] = {'titulo': label, 'url': target, 'source_url': source_url}
    if not found:
        raise ValueError('No actual PDF documents in ' + source_url)
    return list(found.values())


def parse_notice(text):
    normalized = ' '.join(text.split())
    if not re.search(r'AYUNTAMIENTO DE CUARTE DE HUERVA', normalized, re.I) or not re.search(
            r'manzana 5 del sector 5\.2', normalized, re.I):
        raise ValueError('Notice is not the El Plano municipal instrument')
    publication = re.search(r'Núm\.\s*\d+\s+(\d{1,2})\s+(\w+)\s+(\d{4})', normalized)
    agreement = re.search(r'acuerdo de la Junta de Gobierno Local de (\d{1,2}) de (\w+) de (\d{4}) se ha aprobado inicialmente', normalized, re.I)
    if not publication or not agreement:
        raise ValueError('Unrecognized BOP publication/agreement semantics')
    return {'fecha_publicacion': spanish_date(*publication.groups()),
            'fecha_acuerdo': spanish_date(*agreement.groups()), 'fase': 'aprobación inicial'}


def record(key, title, url, docs):
    return {'id': 'cuarte-de-huerva-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Cuarte de Huerva', 'provincia': 'Zaragoza', 'codigo_ine': '50089',
            'titulo': title, 'url': url, 'source': 'ayuntamiento',
            'origen': 'inventario_planeamiento_municipal', 'documentos': docs,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'fase': None, 'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'partial_municipal_planning_snapshot'}


def parse_projects(pages, notice_text):
    urban = content(pages[SOURCE], 'Urbanismo')
    study_docs = documents(urban, SOURCE)
    for doc in study_docs:
        if not re.search(r'(manz(?:ana|5)|bopz)', doc['titulo'], re.I):
            raise ValueError('New planning document requires grouping review')
    notices = [d for d in study_docs if re.search(r'^Anuncio BOPZ', d['titulo'], re.I)]
    studies = [d for d in study_docs if re.match(r'Modificación de estudio de detalle manzana 5 del sector 5\.2', d['titulo'], re.I)]
    if len(notices) != 1 or len(studies) != 1:
        raise ValueError('Ambiguous or missing study/notice document')
    study = record('estudio-detalle-manzana-5-sector-5.2', studies[0]['titulo'], SOURCE, study_docs)
    study.update(parse_notice(notice_text))
    study.update(tipo='estudio de detalle', url_documento=studies[0]['url'],
                 date_source_url=notices[0]['url'])
    pgou_body = content(pages[PAGES['plan-general-de-ordenacion-urbana']], 'Plan General de Ordenación Urbana')
    description = '\n'.join(p.get_text(' ', strip=True) for p in pgou_body.select('p'))
    if 'Cuarte de Huerva' not in description or 'Revisión del Plan General' not in description:
        raise ValueError('Missing PGOU substantive narrative')
    pgou_docs = []
    for name, heading in [('memoria', 'Memoria del PGOU'), ('planos', 'Planos del PGOU')]:
        # Require that the detailed plan actually links its document inventories.
        if not any(urljoin(PAGES['plan-general-de-ordenacion-urbana'], a['href']) == PAGES[name]
                   for a in pgou_body.select('a[href]')):
            raise ValueError('PGOU no longer links ' + name)
        pgou_docs.extend(documents(content(pages[PAGES[name]], heading), PAGES[name]))
    pgou = record('pgou', 'Plan General de Ordenación Urbana de Cuarte de Huerva',
                  PAGES['plan-general-de-ordenacion-urbana'], pgou_docs)
    pgou.update(tipo='PGOU', descripcion=description, url_documento=pgou_docs[0]['url'],
                date_note='Narrativa histórica conservada en descripcion; no acredita fecha ni estado vigente del texto refundido enlazado.')
    return [pgou, study]


class CuarteDeHuervaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url, capture_name, limit=5_000_000):
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-cuarte-de-huerva/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'cuartedehuerva.es':
                raise ValueError('Unexpected redirect from municipal source')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source response exceeds size limit')
                chunks.append(chunk)
            data = b''.join(chunks)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture_name).write_bytes(data)
        return data

    def backfill_proyectos(self, out_jsonl: Path):
        pages = {url: self._fetch(url, name + '.html').decode('utf-8')
                 for name, url in {'urbanismo': SOURCE, **PAGES}.items()}
        docs = documents(content(pages[SOURCE], 'Urbanismo'), SOURCE)
        notices = [d for d in docs if d['titulo'].startswith('Anuncio BOPZ')]
        if len(notices) != 1:
            raise ValueError('Expected one study notice')
        pdf = self._fetch(notices[0]['url'], 'anuncio.pdf')
        if not pdf.startswith(b'%PDF-'):
            raise ValueError('Notice response is not PDF')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'notice.pdf'
            path.write_bytes(pdf)
            text = subprocess.run(['pdftotext', '-layout', str(path), '-'], check=True,
                                  capture_output=True, text=True, timeout=30).stdout
        if self.config.get('capture_dir'):
            (Path(self.config['capture_dir']) / 'anuncio.txt').write_text(text, encoding='utf-8')
        rows = parse_projects(pages, text)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [*pages, notices[0]['url']],
                'coverage': 'partial_municipal_planning_snapshot', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
