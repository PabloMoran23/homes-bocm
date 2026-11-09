"""Municipal NNSS catalogue snapshot, one record per instrument, not per PDF."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://eskoriatza.eus/es/ayuntamiento/normativa/normas-subsidiarias/'
DOCUMENT_HOSTS = {'eskoriatza.eus', 'ssl4.gipuzkoa.net', 'egoitza.gipuzkoa.eus'}


def canonical(url):
    """Upgrade municipal legacy HTTP links; retain meaningful document queries."""
    parts = urlsplit(url)
    scheme = 'https' if parts.hostname == 'eskoriatza.eus' else parts.scheme
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, ''))


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    # These static inventories currently have no pagination. Never accept a
    # future paginated version as a complete snapshot.
    if soup.select('.wp-pagenavi a[href], a[rel~=next], .pagination a[href]'):
        raise ValueError('Pagination detected; catalogue traversal requires review')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', 'hurrengoa', '»', '›'}:
            if a['href'] not in {'', '#'}:
                raise ValueError('Pagination detected')
    body = soup.select_one('#content .c1')
    if body is None or body.select_one('h1') is None:
        raise ValueError('Missing municipal catalogue content')
    return body


def documents(body, source):
    docs = {}
    for a in body.select('a[href]'):
        url = canonical(urljoin(source, a['href']))
        parts = urlsplit(url)
        if parts.path.lower().endswith('.pdf'):
            if parts.hostname not in DOCUMENT_HOSTS:
                raise ValueError('Unexpected document host: ' + url)
            section = a.find_previous(['h2', 'h3', 'strong'])
            docs.setdefault(url, {
                'titulo': a.get_text(' ', strip=True), 'url': url,
                'url_original': urljoin(source, a['href']),
                'source_url': source,
                'seccion': section.get_text(' ', strip=True) if section else None,
            })
        elif url != source and not url.startswith(SOURCE):
            raise ValueError('Unreviewed content link: ' + url)
    return list(docs.values())


class EskoriatzaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        body = content(html)
        if body.h1.get_text(' ', strip=True) != 'Normas Subsidiarias':
            raise ValueError('Unexpected inventory title')
        children = {}
        for a in body.select('a[href]'):
            url = canonical(urljoin(SOURCE, a['href']))
            if url.startswith(SOURCE) and url != SOURCE:
                title = a.get_text(' ', strip=True)
                if not re.search(r'mo[cd]ificaci[oó]n puntual', title, re.I):
                    raise ValueError('Unrecognized child instrument: ' + title)
                children.setdefault(url, title)
        docs = documents(body, SOURCE)
        if not docs:
            raise ValueError('NNSS catalogue lost its text document')
        title = next((d['titulo'] for d in docs if 'Texto Refundido' in d['titulo']), None)
        if not title:
            raise ValueError('Missing consolidated instrument')
        row = EskoriatzaAyuntamientoAdapter._record(SOURCE, title, body, docs)
        # Explicit council session date in the narrative, not the PDF path or
        # the WordPress upload/publication timestamp.
        match = re.search(r'sesi[oó]n de (\d{1,2}) de julio de (\d{4})', body.get_text(' ', strip=True))
        if match:
            row['fecha_acuerdo'] = date(int(match[2]), 7, int(match[1])).isoformat()
        return row, children

    @staticmethod
    def _record(url, title, body, docs):
        return {
            'id': 'eskoriatza-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'municipio': 'Eskoriatza', 'provincia': 'Gipuzkoa', 'codigo_ine': '20034',
            'titulo': title, 'tipo': 'planeamiento_urbanistico',
            'url': url, 'source': 'ayuntamiento', 'origen': 'catalogo_normas_subsidiarias',
            'descripcion': body.get_text('\n', strip=True),
            'documentos': docs, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'geometry': None, 'lat': None, 'lon': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'documentacion_status': 'enlaces_publicados' if docs else 'sin_enlaces_documentales',
        }

    @classmethod
    def parse_detail(cls, html, url, inventory_title):
        body = content(html)
        # Santa Ana currently lists document names as plain text without links.
        # Keep that genuine instrument and explicitly report missing documents.
        docs = documents(body, url)
        for a in body.select('a[href]'):
            if not urlsplit(urljoin(url, a['href'])).path.lower().endswith('.pdf'):
                raise ValueError('Nested instrument links require traversal review')
        heading = body.h1.get_text(' ', strip=True)
        if heading.casefold() not in inventory_title.casefold():
            raise ValueError('Detail does not match discovered instrument')
        return cls._record(url, inventory_title, body, docs)

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        sources = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-eskoriatza/1.0'

            def fetch(url):
                response = session.get(url, timeout=35)
                response.raise_for_status()
                if canonical(response.url) != url:
                    raise ValueError('Unexpected catalogue redirect: ' + response.url)
                if 'text/html' not in response.headers.get('Content-Type', ''):
                    raise ValueError('Expected HTML inventory')
                sources.append(url)
                capture = self.config.get('capture_dir')
                if capture:
                    path = Path(capture)
                    path.mkdir(parents=True, exist_ok=True)
                    name = 'normas' if url == SOURCE else url.rstrip('/').rsplit('/', 1)[-1]
                    (path / (name + '.html')).write_text(response.text, encoding='utf-8')
                return response.text

            root, children = self.parse_inventory(fetch(SOURCE))
            rows = [root]
            for url, title in children.items():
                rows.append(self.parse_detail(fetch(url), url, title))
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': sources, 'coverage': 'Municipal NNSS catalogue only'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
