"""Anonymous municipal POM document inventory, grouped as one instrument."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'https://cedillodelcondado.sedelectronica.es'
SOURCE = HOST + '/transparency/f738017d-4b56-41c3-8b4a-02d0964b7a2f/'
PLAN_TITLE = 'PLAN DE ORDENACION MUNICIPAL'
LIMITATIONS = [
    'Cobertura parcial: solo la carpeta del Plan de Ordenación Municipal en 7.1; '
    'no las modificaciones NNSS, normativa de 7.3, tablón ni contratación.',
    'Inventario documental publicado; no acredita aprobación, vigencia ni ejecución del POM.',
    'Sin fechas de publicación/acuerdo/aprobación verificadas ni geometría; '
    'las fechas de creación del documento en la sede no se interpretan como acuerdos.',
    'Sin registro de licencias concedidas; licencias desactivadas.',
]


def soup(html):
    return BeautifulSoup(html, 'html.parser')


def folders(html):
    result = []
    for a in soup(html).select('a.exp[onclick]'):
        count = a.select_one('.linkExtraInfo')
        if not count or not re.fullmatch(r'\s*\(\s*\d+\s*\)\s*', count.get_text()):
            raise ValueError('Missing folder document count')
        title = a.get_text(' ', strip=True).rsplit('(', 1)[0].strip()
        result.append((title, int(re.search(r'\d+', count.get_text())[0]), a))
    return result


def documents(html, inventory_url, folder):
    result = {}
    for a in soup(html).select('a[href]'):
        url = urljoin(inventory_url, a['href'])
        if not re.fullmatch(re.escape(HOST) + r'/preview-document/[0-9a-f-]{36}', url):
            continue
        title = a.get_text(' ', strip=True)
        if not title:
            raise ValueError('Untitled POM document')
        result[url] = {'titulo': title, 'url': url, 'inventory_url': inventory_url,
                       'carpeta': folder}
    return result


def ajax_html(xml):
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response':
        raise ValueError('Unexpected pagination response')
    components = root.findall('component')
    if not components:
        raise ValueError('Missing pagination components')
    # Parse server-rendered fragments only; never execute evaluate/script blocks.
    return '\n'.join(node.text or '' for node in components)


def more_button(html):
    buttons = [b for b in soup(html).select('[onclick]')
               if b.get_text(' ', strip=True) == 'Mostrar más']
    if len(buttons) > 1:
        raise ValueError('Ambiguous pagination')
    return buttons[0] if buttons else None


def make_record(title, url, docs):
    if title != PLAN_TITLE or not docs:
        raise ValueError('No verified POM inventory')
    return {'id': 'cedillo-del-condado-pom-' + url.rstrip('/').rsplit('/', 1)[-1],
            'municipio': 'Cedillo del Condado', 'provincia': 'Toledo', 'codigo_ine': '45047',
            'titulo': title, 'tipo': 'Plan de Ordenación Municipal',
            'url': url, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'portal_transparencia_planeamiento',
            'documentos': sorted(docs.values(), key=lambda d: d['url']),
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False, 'coverage': 'partial_pom_document_inventory',
            'limitations': LIMITATIONS}


class CedilloDelCondadoAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='cedillo-del-condado', config=None, base_url=''):
        super().__init__(slug, config, base_url or HOST)
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'municipio-cedillo-del-condado/1.0'
        self.source_urls = []
        self.capture_index = 0

    def _get(self, url, ajax=False):
        if urlparse(url).netloc != urlparse(HOST).netloc:
            raise ValueError('Unexpected source host')
        r = self.session.get(url, timeout=40, headers={'Wicket-Ajax': 'true'} if ajax else {})
        r.raise_for_status()
        if urlparse(r.url).netloc != urlparse(HOST).netloc:
            raise ValueError('Unexpected source redirect')
        if len(r.content) > 5_000_000:
            raise ValueError('Oversize inventory response')
        if not ajax and r.url not in self.source_urls:
            self.source_urls.append(r.url)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            self.capture_index += 1
            (directory / f'inventory-{self.capture_index:03d}.{"xml" if ajax else "html"}').write_text(r.text, encoding='utf-8')
        return r

    def _click(self, page_url, element):
        match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
        if not match:
            raise ValueError('Missing Wicket navigation URL')
        return self._get(urljoin(page_url, match[1]), ajax=True)

    def _open_folder(self, page_url, title):
        html = self._get(page_url).text
        matches = [(n, count, a) for n, count, a in folders(html) if n == title]
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous folder: ' + title)
        _, count, a = matches[0]
        r = self._click(page_url, a)
        location = r.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Folder did not expose a stable URL')
        return urljoin(r.url, location), count

    def _crawl(self, url, folder, expected, visited):
        if url in visited or len(visited) >= 50:
            raise ValueError('Folder cycle or traversal bound exceeded')
        visited.add(url)
        html = self._get(url).text
        children = folders(html)
        docs = documents(html, url, folder)
        button = more_button(html)
        for _ in range(100):
            if button is None:
                break
            fragment = ajax_html(self._click(url, button).text)
            additions = documents(fragment, url, folder)
            new_children = folders(fragment)
            if not (set(additions) - set(docs)) and not new_children:
                raise ValueError('Pagination made no progress')
            docs.update(additions)
            children.extend(new_children)
            button = more_button(fragment)
        else:
            raise ValueError('Pagination bound exceeded')
        titles = set()
        for title, count, _ in children:
            if title in titles:
                raise ValueError('Duplicate child folder')
            titles.add(title)
            child_url, current_count = self._open_folder(url, title)
            if current_count != count:
                raise ValueError('Inventory changed during traversal')
            child_docs = self._crawl(child_url, folder + '/' + title, count, visited)
            if set(docs) & set(child_docs):
                raise ValueError('Duplicate document across folders')
            docs.update(child_docs)
        if len(docs) != expected:
            raise ValueError(f'Incomplete inventory at {folder}: {len(docs)} != {expected}')
        return docs

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = []
        url, count = self._open_folder(SOURCE, PLAN_TITLE)
        docs = self._crawl(url, PLAN_TITLE, count, set())
        record = make_record(PLAN_TITLE, url, docs)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(record, ensure_ascii=False) + '\n', encoding='utf-8')
        return {'count': 1, 'written': 1, 'documents': len(docs),
                'source_urls': self.source_urls, 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
