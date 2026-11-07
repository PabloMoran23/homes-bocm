"""Municipal current-planning inventory; one record per instrument, not per PDF."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.badiadelvalles.cat/'
SOURCE = BASE + 'seccio.php?id=35'


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # This inventory currently has no pagination. Fail closed if that changes,
    # including numbered links, rather than silently emit a first-page snapshot.
    for a in soup.select('a[href], link[href]'):
        query = parse_qs(urlparse(a['href']).query)
        label = a.get_text(' ', strip=True).casefold()
        if (set(query) & {'pag', 'pagina', 'page', 'offset', 'inici', 'start'}
                or 'next' in a.get('rel', [])
                or label in {'següent', 'següents', 'siguiente', 'next'}):
            raise ValueError('Pagination detected: review crawler before extracting')
    if soup.select('.paginacio, .pagination, .paginador'):
        raise ValueError('Pagination container detected')
    return soup


def _category(a):
    url = urljoin(BASE, a['href'])
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if (parsed.netloc != 'www.badiadelvalles.cat' or parsed.path != '/fitxes.php'
            or not re.fullmatch(r'\d+', query.get('categoria', [''])[0])):
        raise ValueError('Unexpected planning category URL')
    return url


def parse_inventory(html):
    soup = _soup(html)
    root = soup.select_one('#categoria_ul_118')
    if root is None:
        raise ValueError('Current planning inventory missing')
    instruments = []
    for li in root.find_all('li', recursive=False):
        heading = li.select_one(':scope > div > a[href]')
        if heading is None:
            raise ValueError('Instrument heading missing')
        title = heading.get_text(' ', strip=True)
        if not title.casefold().startswith('modificació'):
            raise ValueError('Unreviewed instrument type in current inventory')
        groups = []
        children = li.find('ul', recursive=False)
        if children:
            for child in children.find_all('li', recursive=False):
                a = child.select_one(':scope > div > a[href]')
                if a is None or child.find('ul', recursive=False):
                    raise ValueError('Unreviewed document category hierarchy')
                groups.append({'titulo': a.get_text(' ', strip=True), 'url': _category(a)})
        else:
            groups.append({'titulo': title, 'url': _category(heading)})
        instruments.append({'titulo': title, 'url': _category(heading), 'groups': groups})
    urls = [r['url'] for r in instruments]
    if not urls or len(set(urls)) != len(urls):
        raise ValueError('Empty or duplicate instrument inventory')
    return instruments


def parse_documents(html, source_url, group):
    soup = _soup(html)
    docs = {}
    for block in soup.select('.div_pdf'):
        a = block.select_one('a.linkpdf[href]')
        if a is None:
            raise ValueError('Document block without PDF link')
        url = urljoin(source_url, a['href'])
        parsed = urlparse(url)
        if (parsed.netloc != 'www.badiadelvalles.cat'
                or not parsed.path.startswith('/ARXIUS/Urbanisme/')
                or not parsed.path.lower().endswith('.pdf')):
            raise ValueError('Unexpected planning document URL')
        title = block.select_one('.descri_pdf')
        docs[url] = {'titulo': title.get_text(' ', strip=True) if title else a.get_text(' ', strip=True),
                     'url': url, 'grupo': group, 'source_url': source_url}
    if not docs:
        raise ValueError('Planning document category empty or changed')
    return list(docs.values())


class BadiaDelVallesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE.rstrip('/'))

    def _fetch(self, url):
        with requests.get(url, timeout=30, stream=True, headers={
                'User-Agent': 'municipio-badia-del-valles/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).netloc != 'www.badiadelvalles.cat':
                raise ValueError('Unexpected redirect outside municipal source')
            parts, size = [], 0
            for part in response.iter_content(65536):
                size += len(part)
                if size > 3_000_000:
                    raise ValueError('Source exceeds reviewed HTML size')
                parts.append(part)
            content = b''.join(parts)
        if self.config.get('evidence_dir'):
            target = Path(self.config['evidence_dir'])
            target.mkdir(parents=True, exist_ok=True)
            category = parse_qs(urlparse(url).query).get('categoria', ['inventory'])[0]
            (target / f'live-{category}.html').write_bytes(content)
        # Parse original bytes so the municipal ISO-8859-1 declaration is honored.
        return content

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        inventory = parse_inventory(self._fetch(SOURCE))
        rows, sources = [], [SOURCE]
        for instrument in inventory:
            documents = {}
            for group in instrument['groups']:
                sources.append(group['url'])
                for doc in parse_documents(self._fetch(group['url']), group['url'], group['titulo']):
                    if doc['url'] in documents:
                        raise ValueError('Document repeated across categories; review provenance')
                    documents[doc['url']] = doc
            category = parse_qs(urlparse(instrument['url']).query)['categoria'][0]
            rows.append({
                'id': 'badia-del-valles-proy-' + category,
                'municipio': 'Badia del Vallès', 'codigo_ine': '08904', 'provincia': 'Barcelona',
                'titulo': instrument['titulo'], 'tipo': 'modificacion_planeamiento',
                'fase': 'vigent', 'fase_fuente': 'Planejament vigent',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': instrument['url'], 'source_url': SOURCE,
                'url_documento': next(iter(documents)), 'documentos': list(documents.values()),
                'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_vigente',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'coverage': 'Inventario municipal de planeamiento vigente; no registro completo de obras o licencias',
            })
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current inventory snapshot; no time cutoff and no state advancement.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
