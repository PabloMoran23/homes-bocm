"""Alameda's public Gestiona inventory: complete snapshots of two named plans."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://alameda.sedelectronica.es'
INVENTORIES = (
    ('6dc62266-2848-4ce4-bbda-75c6a1118b62',
     'PLAN BÁSICO DE ORDENACIÓN MUNICIPAL (PBOM)', 'PBOM', 'PBOMA TOMO'),
    ('1d04d624-dd6e-4621-864f-ed03abd91459',
     'PLAN MUNICIPAL VIVIENDA Y SUELO', 'plan municipal de vivienda y suelo', 'TomoIMemoria'),
)
LIMITATIONS = [
    'Cobertura parcial: dos carpetas de instrumentos nominados de la sede municipal; no es un registro exhaustivo de actuaciones.',
    'Excluidos los planos y memoria ALA_AP_AD, el documento UR 3 A y los decretos históricos de obras: requieren identificación adicional.',
    'Las fechas de publicación, acuerdo y aprobación no se extraen de los nombres ni del año del decreto.',
    'No se afirma vigencia, aprobación definitiva ni ejecución; sin geometría verificada ni registro de licencias concedidas.',
]


def official_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'alameda.sedelectronica.es':
        raise ValueError('Unexpected non-municipal URL')
    return url


def ajax_url(node, page_url):
    match = re.search(r"wicketAjaxGet\('([^']+)'", node.get('onclick', ''))
    if not match:
        raise ValueError('Unrecognized pagination callback')
    return official_url(urljoin(page_url, match[1]))


def apply_ajax(soup, payload):
    """Apply Wicket components as data; never execute scripts supplied by the site."""
    root = ET.fromstring(payload)
    if root.tag != 'ajax-response' or root.find('redirect') is not None:
        raise ValueError('Unexpected pagination response or expired session')
    components = root.findall('component')
    if not components:
        raise ValueError('Pagination response has no components')
    for component in components:
        markup = component.text or ''
        if component.get('encoding') == 'wicket1':
            markup = markup.replace(']^', ']')
        fragment = BeautifulSoup(markup, 'html.parser')
        node = fragment.find()
        if node is None:
            raise ValueError('Empty pagination component')
        old = soup.find(id=component.get('id'))
        if old is not None:
            old.replace_with(node)
        elif node.name == 'tr' and soup.select_one('table.TransparencyListPanel tbody'):
            soup.select_one('table.TransparencyListPanel tbody').append(node)
        else:
            raise ValueError('Unrecognized pagination component target')
    return soup


def parse_inventory(html, url, title, kind, required_document):
    soup = BeautifulSoup(html, 'html.parser')
    if title not in soup.get_text(' ', strip=True):
        raise ValueError('Expected instrument folder is missing')
    if soup.select_one('.more_results button[onclick]'):
        raise ValueError('Unfinished pagination')
    table = soup.select_one('table.TransparencyListPanel')
    if table is None or table.select('a.exp'):
        raise ValueError('Missing inventory or unexpected nested folders')
    documents = {}
    for a in table.select('a[href*="/preview-document/"]'):
        target = official_url(urljoin(url, a['href']))
        if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(target).path):
            raise ValueError('Unexpected document identifier')
        label = a.get_text(' ', strip=True)
        if not label:
            raise ValueError('Untitled document')
        documents[target] = {'titulo': label, 'url': target, 'inventory_url': url,
                             'descripcion': a.get('title') or None}
    docs = list(documents.values())
    # A category name or procedural decree alone is not a planning instrument.
    if not any(required_document.casefold() in d['titulo'].casefold() for d in docs):
        raise ValueError('No technical plan documents found')
    return {
        'id': 'alameda-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Alameda', 'provincia': 'Málaga', 'codigo_ine': '29001',
        'titulo': title, 'tipo': kind, 'url': url, 'inventory_url': url,
        'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
        'documentos': docs,
        'descripcion': 'Instrumento publicado en la carpeta municipal; documentos técnicos y administrativos agrupados. La publicación en el inventario no acredita su aprobación ni vigencia.',
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class AlamedaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='alameda', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'municipio-alameda/1.0 (public planning inventory)'
        self.source_urls = []
        self._capture_number = 0

    def _get(self, url, ajax=False):
        official_url(url)
        response = self.session.get(url, timeout=45, allow_redirects=False,
                                    headers={'Wicket-Ajax': 'true'} if ajax else {})
        response.raise_for_status()
        if response.status_code != 200 or response.headers.get('Ajax-Location'):
            raise ValueError('Unexpected inventory redirect/status')
        if url not in self.source_urls:
            self.source_urls.append(url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            self._capture_number += 1
            name = f'alameda-source-{self._capture_number:02d}' + ('.xml' if ajax else '.html')
            (path / name).write_bytes(response.content)
        return response.text

    def _inventory(self, url):
        soup = BeautifulSoup(self._get(url), 'html.parser')
        seen = set()
        for _ in range(100):
            button = soup.select_one('.more_results button[onclick]')
            if button is None:
                return str(soup)
            callback = ajax_url(button, url)
            before = str(soup)
            if callback in seen:
                raise ValueError('Repeated pagination callback; refusing partial output')
            seen.add(callback)
            apply_ajax(soup, self._get(callback, ajax=True))
            if str(soup) == before:
                raise ValueError('Pagination made no progress')
        raise ValueError('Pagination safety limit exceeded; refusing partial output')

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = []
        rows = []
        for folder, title, kind, required in INVENTORIES:
            url = f'{BASE}/transparency/{folder}/'
            rows.append(parse_inventory(self._inventory(url), url, title, kind, required))
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'live_records': len(rows),
                'document_count': sum(len(r['documentos']) for r in rows),
                'source_urls': self.source_urls, 'limitations': LIMITATIONS,
                'coverage': 'two_current_instrument_folders_complete_pagination',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # The upstream inventory exposes no reliable incremental cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
