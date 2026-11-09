"""Viana's municipal DUS 5000 physical-works inventory (partial coverage)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.viana.es/plan-de-recuperacion-transformacion-y-resiliencia/'
HOST = 'www.viana.es'


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None:
        raise ValueError('Missing municipal main content')
    if main.select('.pagination, .page-numbers, a[rel~=next]'):
        raise ValueError('Pagination requires review; refusing partial extraction')
    for a in main.select('a[href]'):
        if re.search(r'/page/\d|[?&](?:paged|page)=', a['href']) or a.get_text(' ', strip=True).lower() in {'siguiente', 'next'}:
            raise ValueError('Pagination requires review')
    body = main.select_one('.contenido.content')
    if body is None:
        raise ValueError('Missing municipal content body')
    for share in body.select('.list-inline, .comentarios'):
        share.decompose()
    return body


def official_url(base, href):
    url = urljoin(base, href).split('#')[0]
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != HOST:
        raise ValueError('Unexpected non-municipal source link')
    return url


def parse_inventory(html):
    body = content(html)
    headings = [p for p in body.select('p') if p.get_text(' ', strip=True) == 'DUS 5000']
    if len(headings) != 1:
        raise ValueError('DUS 5000 inventory section missing or ambiguous')
    listing = headings[0].find_next_sibling()
    if listing is None or listing.name != 'ul':
        raise ValueError('DUS 5000 works list missing')
    rows = {}
    for li in listing.find_all('li', recursive=False):
        title = li.get_text(' ', strip=True)
        if not re.match(r'^(Renovación del alumbrado|Instalación de generación térmica|Reforma de la envolvente térmica)\b', title):
            raise ValueError('Unreviewed DUS 5000 item: ' + title)
        anchors = li.select('a[href]')
        if len(anchors) > 1:
            raise ValueError('Ambiguous project detail links')
        url = official_url(SOURCE, anchors[0]['href']) if anchors else SOURCE
        identity = url if anchors else SOURCE + '#' + title.casefold()
        key = 'viana-dus5000-' + hashlib.sha256(identity.encode()).hexdigest()[:16]
        rows.setdefault(key, {
            'id': key, 'municipio': 'Viana', 'codigo_ine': '31251', 'provincia': 'Navarra',
            'titulo': title, 'tipo': 'obra_publica', 'url': url, 'inventory_url': SOURCE,
            'source': 'ayuntamiento', 'origen': 'inventario_municipal_dus5000',
            'coverage': 'partial_dus5000', 'geometry_status': 'unavailable',
            'publication_ready': False,
            'documentos': [{'titulo': 'Inventario municipal PRTR / DUS 5000', 'url': SOURCE,
                            'procedencia': 'ayuntamiento', 'tipo': 'pagina_inventario'}],
            'detalle_disponible': bool(anchors),
        })
    if not rows:
        raise ValueError('Empty DUS 5000 works inventory')
    return list(rows.values())


def enrich_detail(row, html):
    body = content(html)
    text = body.get_text(' ', strip=True)
    if 'Descripción del proyecto' not in text or 'DUS5000' not in text:
        raise ValueError('Missing actual DUS 5000 project description')
    # Funding/application dates in this text are not municipal approval dates.
    row['descripcion'] = text
    match = re.search(r'PR-D5000-\d{4}-\d+', text)
    if match:
        row['expediente_ayuda'] = match.group()
    docs = {doc['url']: doc for doc in row['documentos']}
    docs[row['url']] = {'titulo': row['titulo'], 'url': row['url'],
                        'procedencia': 'ayuntamiento', 'tipo': 'ficha_proyecto'}
    for a in body.select('a[href]'):
        if urlparse(a['href']).path.lower().endswith('.pdf'):
            url = official_url(row['url'], a['href'])
            docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                                  'procedencia': 'adjunto_ficha_municipal', 'tipo': 'documento_pdf'})
    row['documentos'] = list(docs.values())
    return row


class VianaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(url, timeout=35)
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Unexpected source redirect')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected municipal HTML')
        capture_dir = self.config.get('evidence_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (directory / name).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)
        return {'count': len(rows), 'coverage': 'partial_dus5000'}

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'MunicipalInventory/1.0 (Viana public works)'
            rows = parse_inventory(self._fetch(session, SOURCE))
            for row in rows:
                if row['detalle_disponible']:
                    enrich_detail(row, self._fetch(session, row['url']))
        return self._write(out_jsonl, rows)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
