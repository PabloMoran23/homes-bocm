"""Municipal NNSS document inventory and its listed amendments (partial coverage)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.mutriku.eus/es/servicios/urbanismo/normativa'
CATEGORIES = {'PLANOS GENERALES', 'CATALOGO', 'FICHAS URBANISTICAS', 'MODIFICACIÓN PUNTUAL'}


def official_url(base, href):
    url = urljoin(base, href)
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'www.mutriku.eus':
        raise ValueError(f'Unexpected source host: {url}')
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    # Fail closed if Plone adds pagination rather than returning a partial snapshot.
    for a in soup.select('a[href]'):
        if (a.get_text(' ', strip=True).casefold() in
                {'siguiente', 'next', 'hurrengoa', '»', '›'} or
                'next' in a.get('rel', []) or
                'batching' in ' '.join(a.parent.get('class', [])) or
                re.search(r'[?&](?:b_start(?::int)?|page)=', a['href'])):
            raise ValueError('Pagination detected; inventory requires review')
    body = soup.select_one('#parent-fieldname-text')
    if body is None:
        raise ValueError('Municipal content container missing')
    return soup, body


def documents(body, url):
    docs = {}
    for a in body.select('a[href]'):
        # These Plone pages also expose extensionless file objects. Internal
        # content links in document sections are documents, not extra projects.
        if a.get('data-linktype') != 'internal' and not urlsplit(a['href']).path.lower().endswith('.pdf'):
            continue
        link = official_url(url, a['href'])
        docs.setdefault(link, {'titulo': a.get_text(' ', strip=True), 'url': link,
                               'source_url': url})
    if not docs:
        raise ValueError(f'No source documents: {url}')
    return list(docs.values())


def record(identity, title, url, docs):
    return {'id': 'mutriku-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:20],
            'municipio': 'Mutriku', 'codigo_ine': '20056', 'provincia': 'Gipuzkoa',
            'titulo': title, 'tipo': 'planeamiento_urbanistico',
            'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_normativa_municipal',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'documentos': docs, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False}


class MutrikuAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.mutriku.eus')
        self.source_urls = []

    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-mutriku/1.0'})
        response.raise_for_status()
        official_url(url, response.url)
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError(f'Expected HTML inventory: {url}')
        self.source_urls.append(url)
        if self.config.get('capture_dir'):
            dest = Path(self.config['capture_dir'])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(
                response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def parse_root(html):
        soup, body = content(html)
        all_docs = documents(body, SOURCE)
        anchors = [a for a in body.select('a[href]')
                   if a.get_text(' ', strip=True).startswith('Normas Subsidiarias de Mutriku')]
        if len(anchors) != 1:
            raise ValueError('NNSS instrument missing or ambiguous')
        primary = official_url(SOURCE, anchors[0]['href'])
        # Local noise/chabola ordinances are separate regulations, not plans.
        keep = [d for d in all_docs if d['url'] == primary or
                d['titulo'] in {'Memoria', 'Sistemas Generales de Mutriku'}]
        if len(keep) != 3:
            raise ValueError('Core NNSS documents changed')
        row = record('nnss', 'Normas Subsidiarias de Planeamiento de Mutriku', SOURCE, keep)
        date = re.search(r'BOG\s+(\d{2}-\d{2}-\d{4})', anchors[0].get_text(' ', strip=True))
        if date:
            row['fecha_publicacion'] = datetime.strptime(date[1], '%d-%m-%Y').date().isoformat()
            row['fecha_publicacion_fuente'] = {'url': SOURCE, 'texto': anchors[0].get_text(' ', strip=True),
                                               'ambito': 'publicación BOG indicada por el inventario; no fecha de la página'}
        categories = {}
        for a in soup.select('a[href]'):
            title = a.get_text(' ', strip=True)
            if title in CATEGORIES:
                link = official_url(SOURCE, a['href'])
                if not link.startswith(SOURCE + '/'):
                    raise ValueError('Category outside reviewed inventory')
                if title in categories and categories[title] != link:
                    raise ValueError('Ambiguous category')
                categories[title] = link
        if set(categories) != CATEGORIES:
            raise ValueError('Planning inventory categories changed')
        return row, categories

    @staticmethod
    def parse_amendments(html, url):
        _, body = content(html)
        entries = {}
        for a in body.select('a[href]'):
            title = a.get_text(' ', strip=True)
            if not re.match(r'^\d+\s*[.\-]+\s*Modificaci[oó]n puntual', title, re.I):
                raise ValueError(f'Unrecognized amendment inventory entry: {title}')
            link = official_url(url, a['href'])
            if not link.startswith(url.rstrip('/') + '/'):
                raise ValueError('Amendment outside inventory')
            entries.setdefault(link, (a.get('data-val') or link, re.sub(r'^\d+\s*[.\-]+\s*', '', title)))
        if not entries:
            raise ValueError('Amendment inventory empty; review coverage')
        return entries

    @staticmethod
    def parse_amendment(html, url, identity, title):
        _, body = content(html)
        row = record(identity, title, url, documents(body, url))
        row['descripcion'] = '\n'.join(p.get_text(' ', strip=True) for p in body.select('p')
                                       if p.get_text(strip=True))
        for p in body.select('p'):
            label = p.select_one('strong')
            if label and label.get_text(' ', strip=True).rstrip(':') == 'Egoera':
                row['fase_fuente'] = p.get_text(' ', strip=True).split(':', 1)[-1].strip()
        # HTML describes formulation/participation, not final plan approval.
        # Dates inside the attached gazette are deliberately not inferred.
        return row

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        main, categories = self.parse_root(self._fetch(SOURCE))
        rows = [main]
        for title, url in categories.items():
            html = self._fetch(url)
            if title == 'MODIFICACIÓN PUNTUAL':
                for link, (identity, name) in self.parse_amendments(html, url).items():
                    rows.append(self.parse_amendment(self._fetch(link), link, identity, name))
            else:
                _, body = content(html)
                main['documentos'].extend(documents(body, url))
        main['documentos'] = list({d['url']: d for d in main['documentos']}.values())
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': list(self.source_urls), 'coverage': 'partial', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
