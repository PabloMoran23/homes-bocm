"""Municipal NNSS and public-exposure works inventory; no licence claims."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.latorredeclaramunt.cat'
PLANNING = BASE + '/ajuntament/urbanisme/'
INVENTORY = ('https://seu-e.cat/ca/web/latorredeclaramunt/govern-obert-i-transparencia/'
             'accio-de-govern-i-normativa/urbanisme')
LIMITATIONS = [
    'Partial coverage: municipal NNSS page and physical works exposed in the current Catalan transparency inventory only; no complete RPUC or historical archive extraction.',
    'No granted licences, verified geometry or coordinates. Civil-protection DUPROCIM, forms, procurement and news excluded.',
    'Page update dates are not publication or agreement dates. Works agreement dates inside PDFs are not parsed; linked documents retain provenance.',
    'NNSS approval date concerns the 1986 base instrument, not every later amendment included in its consolidated text.',
]


def _main(html):
    main = BeautifulSoup(html, 'html.parser').select_one('main')
    if main is None:
        raise ValueError('Missing official main content')
    for a in main.select('a[href]'):
        if ('next' in a.get('rel', []) or
            a.get_text(' ', strip=True).lower() in {'següent', 'següent »', 'siguiente', 'next', '›', '»'} or
            a.find_parent(class_=re.compile(r'^(pagination|paginacio|pager)$'))):
            raise ValueError('Pagination detected: extend traversal before extracting')
    return main


def _record(key, title, url, kind, docs):
    return {
        'id': 'la-torre-de-claramunt-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
        'municipio': 'La Torre de Claramunt', 'codigo_ine': '08286', 'provincia': 'Barcelona',
        'titulo': title, 'tipo': kind, 'url': url, 'source': 'ayuntamiento',
        'origen': 'urbanisme_municipal', 'documentos': docs,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified instrument geometry in extracted sources',
    }


class LaTorreDeClaramuntAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_planning(html):
        main = _main(html)
        content = main.select_one('#readspeakerPage .ddbbtext')
        title = main.select_one('#readspeakerPage .subtitle')
        if content is None or title is None or 'La Torre de Claramunt' not in title.get_text():
            raise ValueError('Missing municipal NNSS instrument')
        text = content.get_text(' ', strip=True)
        match = re.search(r'NNSS vigents i aprovades per la Comissió d.Urbanisme de Barcelona en sessió (\d{2}-\d{2}-\d{4})', text)
        if not match:
            raise ValueError('NNSS approval narrative changed')
        docs = {}
        for a in main.select('#page-documents a[href]'):
            url = urljoin(PLANNING, a['href'])
            if urlparse(url).hostname == 'www.latorredeclaramunt.cat' and urlparse(url).path.endswith('.pdf'):
                docs[url] = {'titulo': a.get_text(' ', strip=True), 'url': url, 'source_url': PLANNING}
        if not docs:
            raise ValueError('NNSS document missing')
        row = _record('nnss', title.get_text(' ', strip=True), PLANNING, 'normas_subsidiarias', list(docs.values()))
        row.update(descripcion=text, fase='aprobación definitiva',
                   fecha_aprob=datetime.strptime(match[1], '%d-%m-%Y').date().isoformat(),
                   fecha_aprob_alcance='Base NNSS approval; consolidated document includes subsequent amendments without individual dates')
        updated = main.select_one('.updated')
        if updated:
            m = re.search(r'(\d{2}\.\d{2}\.\d{4})', updated.get_text())
            if m:
                row['fecha_actualizacion_fuente'] = datetime.strptime(m[1], '%d.%m.%Y').date().isoformat()
        return row

    @staticmethod
    def parse_inventory(html):
        main = _main(html)
        links = {}
        for a in main.select('a[href]'):
            url = urljoin(INVENTORY, a['href']).split('#')[0].rstrip('/')
            title = a.get_text(' ', strip=True)
            if (url.startswith(INVENTORY + '/') and '/' not in url[len(INVENTORY) + 1:]
                    and re.match(r'^(EXPOSICIÓ PÚBLICA|PROJECTE)', title, re.I)):
                links[url] = title
        if not links:
            raise ValueError('No public-exposure works inventory found; review source')
        return links

    @staticmethod
    def parse_work(html, url, inventory_title):
        main = _main(html)
        heading = main.select_one('h1.page-title')
        if heading is None or heading.get_text(' ', strip=True) != inventory_title:
            raise ValueError('Work detail title differs from inventory')
        docs = {}
        for a in main.select('.journal-content-article a[href]'):
            doc = urljoin(url, a['href'])
            if urlparse(doc).hostname == 'seu-e.cat' and urlparse(doc).path.startswith('/documents/'):
                docs[doc] = {'titulo': a.get_text(' ', strip=True), 'url': doc, 'source_url': url}
        # An exposure title alone is insufficient: require the technical project.
        if not any(re.search(r'MEMÒRIA VALORADA|PROJECTE', d['titulo'], re.I)
                   and not re.search(r'CERTIFICAT|ANUNCI|LICITACI', d['titulo'], re.I) for d in docs.values()):
            raise ValueError('Work lacks a technical project or valued memorandum')
        row = _record(url, inventory_title, url, 'obra_publica', list(docs.values()))
        row.update(fase='exposición pública', descripcion=inventory_title,
                   inventory_url=INVENTORY,
                   date_notes='HTML exposes an update date only. Agreement and publication dates not inferred from document labels or page update.')
        footer = main.select_one('.journal-content-article .datatable_info_footer')
        if footer:
            m = re.search(r'Actualització:\s*(\d{2}/\d{2}/\d{4})', footer.get_text())
            if m:
                row['fecha_actualizacion_fuente'] = datetime.strptime(m[1], '%d/%m/%Y').date().isoformat()
        return row

    def _fetch(self, url):
        response = requests.get(url, timeout=45, headers={'User-Agent': 'municipio-la-torre-de-claramunt/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(url).hostname:
            raise ValueError('Unexpected cross-host source redirect')
        if 'html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected HTML inventory/detail')
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir'])
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = [self.parse_planning(self._fetch(PLANNING))]
        links = self.parse_inventory(self._fetch(INVENTORY))
        for url, title in links.items():
            rows.append(self.parse_work(self._fetch(url), url, title))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [PLANNING, INVENTORY, *links],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot of the supported current inventory; never append duplicates.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
