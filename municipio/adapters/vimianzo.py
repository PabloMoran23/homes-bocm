"""Snapshot of the municipal NNSS modification inventory, not a licence register."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.vimianzo.gal'
SOURCE = BASE + '/info.php?sec=311&idioma=gl'
PLAN = re.compile(r'^MODIFICACIÓN PUNTUAL (\d+) DAS NNSS DE VIMIANZO$', re.I)


def _municipal_url(href: str, page_url: str) -> str:
    url = urljoin(page_url, href)
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    if (parts.scheme != 'https' or parts.netloc != 'www.vimianzo.gal'
            or parts.path != '/info.php' or query.get('sec') != ['311']):
        raise ValueError('Unexpected URL in urbanism inventory: ' + url)
    if 'id' in query:
        if not re.fullmatch(r'\d+', query['id'][0]):
            raise ValueError('Invalid municipal item ID')
        return BASE + '/info.php?' + urlencode({'id': query['id'][0], 'idioma': 'gl', 'sec': '311'})
    page = query.get('page', ['1'])[0]
    if not re.fullmatch(r'[1-9]\d*', page):
        raise ValueError('Invalid inventory page')
    return SOURCE + '&page=' + page


class VimianzoAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='vimianzo', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []

    @staticmethod
    def parse_inventory(html: str, page_url: str = SOURCE):
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.select_one('#CONTIDOS h1.titSeccion')
        if not heading or heading.get_text(' ', strip=True) != 'Normativa':
            raise ValueError('Missing municipal urbanism inventory')
        items = {}
        for anchor in soup.select('#CONTIDOS .listado a.tit[href]'):
            title = anchor.get_text(' ', strip=True)
            if PLAN.fullmatch(title):
                items[_municipal_url(anchor['href'], page_url)] = title
        if not items:
            raise ValueError('No NNSS modifications in inventory')
        pages = set()
        # Pagination lives outside #CONTIDOS on this portal. Follow every listed
        # page, including newly discovered pages, without a fixed page ceiling.
        for anchor in soup.select('a[href]'):
            target = urljoin(page_url, anchor['href'])
            query = parse_qs(urlsplit(target).query)
            if query.get('sec') == ['311'] and 'page' in query:
                pages.add(_municipal_url(anchor['href'], page_url))
            elif re.search(r'seguinte|siguiente|next', anchor.get_text(' ', strip=True), re.I):
                if query.get('sec') == ['311']:
                    raise ValueError('Unrecognized inventory pagination')
        return items, pages

    @staticmethod
    def parse_detail(html: str, url: str, expected_title: str):
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.select_one('#CONTIDOS h1.titSeccion')
        content = soup.select_one('#CONTIDOS .contido')
        title = heading.get_text(' ', strip=True) if heading else ''
        match = PLAN.fullmatch(title)
        if not match or title != expected_title or content is None:
            raise ValueError('Missing or mismatched planning detail: ' + url)
        documents = {}
        publication_dates = set()
        definitive = False
        for anchor in content.select('a[href]'):
            target = urljoin(url, anchor['href'])
            parts = urlsplit(target)
            if not parts.path.lower().endswith('.pdf'):
                continue
            if (parts.scheme not in {'http', 'https'} or parts.hostname not in
                    {'www.vimianzo.gal', 'bop.dicoruna.es'}):
                raise ValueError('Unexpected planning document host')
            label = anchor.get_text(' ', strip=True)
            parent = anchor.find_parent('li')
            context = (parent or anchor).get_text(' ', strip=True)
            publication = None
            date_match = re.search(r'publicada no BOP.*?do (\d{2}/\d{2}/\d{4})', label, re.I)
            if date_match:
                publication = datetime.strptime(date_match[1], '%d/%m/%Y').date().isoformat()
                publication_dates.add(publication)
            is_definitive = 'aprobación definitiva' in label.lower()
            definitive = definitive or is_definitive
            documents.setdefault(target, {
                'titulo': label, 'url': target, 'url_procedencia': url,
                'contexto_fuente': context, 'fecha_publicacion': publication,
                'fase_documento': 'aprobación definitiva' if is_definitive else None,
            })
        if not documents:
            raise ValueError('Planning detail has no source documents')
        if len(publication_dates) > 1:
            raise ValueError('Conflicting definitive publication dates')
        return {
            'id': 'vimianzo-nnss-mp-' + match[1],
            'municipio': 'Vimianzo', 'codigo_ine': '15092', 'provincia': 'A Coruña',
            'titulo': title, 'tipo': 'modificacion_planeamiento',
            'fase': 'aprobación definitiva' if definitive else None,
            'fecha': None, 'fecha_publicacion': next(iter(publication_dates), None),
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'descripcion': content.get_text(' ', strip=True),
            'url': url, 'source': 'ayuntamiento', 'origen': 'normativa_urbanistica_municipal',
            'url_inventario': SOURCE, 'documentos': list(documents.values()),
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'Sin geometría verificada; documentos cartográficos enlazados sin georreferenciar',
        }

    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-vimianzo/1.0')})
        response.raise_for_status()
        if urlsplit(response.url).netloc != 'www.vimianzo.gal':
            raise ValueError('Municipal source redirected to another host')
        self.source_urls.append(url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            query = parse_qs(urlsplit(url).query)
            name = ('detail-' + query['id'][0] if 'id' in query else
                    'inventory-' + query.get('page', ['1'])[0])
            (directory / (name + '.html')).write_bytes(response.content)
        return response.content

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        pending, visited, items = {SOURCE + '&page=1'}, set(), {}
        page_items = {}
        while pending:
            url = sorted(pending)[0]
            pending.remove(url)
            if url in visited:
                continue
            found, pages = self.parse_inventory(self._fetch(url), url)
            signature = frozenset(found)
            if signature in page_items and page_items[signature] != url:
                raise ValueError('Pagination repeats an inventory page; refusing partial coverage')
            page_items[signature] = url
            visited.add(url)
            items.update(found)
            pending.update(pages - visited)
        rows = [self.parse_detail(self._fetch(url), url, title)
                for url, title in sorted(items.items())]
        if len({row['id'] for row in rows}) != len(rows):
            raise ValueError('Multiple municipal pages for one instrument require reconciliation')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_pages': len(visited),
                'source_urls': self.source_urls, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
