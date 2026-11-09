"""Document inventories published by Bárcena de Cicero; no licence inference."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.barcenadecicero.es/'
URBANISMO = urljoin(BASE, 'servicios-ciudadanos/urbanismo.html')
MONTHS = dict(zip(
    ('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split(),
    range(1, 13),
))
LIMITATIONS = [
    'Cobertura parcial: inventario NNSS y conjunto PGOU enlazado desde la portada; no histórico completo.',
    'Documentación publicada, sin verificar vigencia, aprobación definitiva ni estado actual del trámite.',
    'Sin registro de licencias concedidas, sin coordenadas y sin geocodificación.',
    'Los archivos ZIP se conservan como paquetes; no se inventarían sus documentos internos.',
]


def official_url(href: str, source: str) -> str:
    url = urljoin(source, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'www.barcenadecicero.es':
        raise ValueError(f'Unexpected source outside municipal HTTPS site: {url}')
    return url


def no_pagination(soup):
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if a['href'] not in ('', '#') and (
            'next' in a.get('rel', [])
            or label in {'siguiente', 'siguiente página', 'next', '›', '»'}
            or a.find_parent(class_=re.compile(r'pagination|paginacion', re.I))
        ):
            raise ValueError('Inventory pagination detected; refusing partial extraction')


def documents(block, source, directory, suffixes):
    docs = {}
    for a in block.select('a[href]'):
        target = urljoin(source, a['href'])
        path = urlparse(target).path
        # Scope to the document family, excluding navigation, forms and news.
        if directory not in path or not path.lower().endswith(suffixes):
            continue
        target = official_url(a['href'], source)
        docs.setdefault(target, {
            'titulo': a.get_text(' ', strip=True), 'url': target,
            'source_url': source, 'formato': path.rsplit('.', 1)[-1].lower(),
        })
    if not docs:
        raise ValueError('Planning instrument has no supported source documents')
    return list(docs.values())


def record(key, title, source, docs):
    return {
        'id': 'barcena-de-cicero-' + key,
        'municipio': 'Bárcena de Cicero', 'codigo_ine': '39009', 'provincia': 'Cantabria',
        'titulo': title, 'tipo': 'planeamiento_urbanistico',
        'url': source, 'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
        'documentos': docs, 'publication_ready': False, 'geometry_status': 'unavailable',
    }


def parse_nnss(html, source=URBANISMO):
    soup = BeautifulSoup(html, 'html.parser')
    no_pagination(soup)
    headings = [h for h in soup.select('h3')
                if h.get_text(' ', strip=True).upper().startswith('NORMAS SUBSIDIARIAS DE BÁRCENA DE CICERO')]
    if len(headings) != 1:
        raise ValueError('Expected the municipal NNSS inventory heading')
    h = headings[0]
    block = h.find_next_sibling('div', class_='from-fckdiv')
    if block is None:
        raise ValueError('Missing NNSS document container')
    return record('nnss', h.get_text(' ', strip=True), source,
                  documents(block, source, '/DOCUMENTOS/NNSS/', ('.pdf',)))


def discover_pgou(html):
    soup = BeautifulSoup(html, 'html.parser')
    urls = {official_url(a['href'], BASE) for a in soup.select('a[href]')
            if 'PGOU' in a.get_text(' ', strip=True).upper()
            and 'EXPOSICIÓN PÚBLICA' in a.get_text(' ', strip=True).upper()}
    if len(urls) != 1:
        raise ValueError('Expected one current PGOU exposure link on municipal homepage')
    return urls.pop()


def spanish_date(text):
    match = re.search(r'\b(\d{1,2}) de (\w+) de (\d{4})\b', text, re.I)
    if not match:
        raise ValueError('Expected an explicit numeric Spanish date')
    day, month, year = match.groups()
    return date(int(year), MONTHS[month.casefold()], int(day)).isoformat()


def parse_pgou(html, source):
    soup = BeautifulSoup(html, 'html.parser')
    no_pagination(soup)
    title = soup.title.get_text(' ', strip=True).split(' - Ayuntamiento')[0] if soup.title else ''
    if not ('PLAN GENERAL DE ORDENACIÓN URBANA' in title.upper()
            and 'INFORMACIÓN PÚBLICA' in title.upper()):
        raise ValueError('Unexpected PGOU page semantics')
    blocks = [b for b in soup.select('.from-fckdiv')
              if b.select('a[href*="/DOCUMENTOS/PGOU_"]')]
    if len(blocks) != 1:
        raise ValueError('Expected one PGOU document container')
    block = blocks[0]
    row = record('pgou', title, source,
                 documents(block, source, '/DOCUMENTOS/PGOU_', ('.zip', '.pdf')))
    row['descripcion'] = ' '.join(block.get_text(' ', strip=True).split())
    # These refer to the notice and to opening the exposure, never final approval.
    meta = soup.select_one('.single-page .meta')
    if meta:
        row['fecha_publicacion'] = spanish_date(meta.get_text(' ', strip=True))
    text = row['descripcion']
    agreement = re.search(
        r'Mediante acuerdo adoptado por el Pleno.*?en fecha de (.*?) '
        r'se ha acordado disponer la apertura de un nuevo trámite de información pública',
        text, re.I,
    )
    if agreement:
        row['fecha_acuerdo'] = spanish_date(agreement.group(1))
        row['fecha_acuerdo_tipo'] = 'apertura de nuevo trámite de información pública'
    return row


class BarcenaDeCiceroAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, capture_name):
        official_url(url, BASE)
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'MunicipalDocumentInventory/1.0',
        })
        response.raise_for_status()
        official_url(response.url, BASE)
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected an HTML inventory')
        capture_dir = self.config.get('evidence_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / capture_name).write_bytes(response.content)
        return response.content

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        nnss = parse_nnss(self._fetch(URBANISMO, 'urbanismo.html'))
        pgou_url = discover_pgou(self._fetch(BASE, 'home.html'))
        pgou = parse_pgou(self._fetch(pgou_url, 'pgou.html'), pgou_url)
        rows = [nnss, pgou]
        self._write(out_jsonl, rows)
        return {
            'count': len(rows), 'written': len(rows), 'coverage': 'partial_document_inventories',
            'source_urls': [BASE, URBANISMO, pgou_url], 'limitations': LIMITATIONS,
            'publication_ready': False,
        }

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh of these unpaginated inventories; no lossy date watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
