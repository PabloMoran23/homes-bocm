"""Son Servera: municipal NNSS and modification document inventories."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.sonservera.es/portal/'
SOURCE = BASE + ('p_18_final_Contenedor1.jsp?seccion=s_p_21_menu_nivel1.jsp'
                 '&language=es&codResi=1&codMenuPN=3&codMenu=16')
LIMITATIONS = [
    'Partial coverage: NNSS revision and numbered modifications in the municipal urbanism menu only; excludes heritage catalogues, works and other noticeboards.',
    'Document inventories retain historical stages; modification phase and dates are unknown, not inferred from document labels or crawl time.',
    'PDF contents and legal currency are not interpreted; linked maps are not extracted as vector geometry.',
    'No verified granted-licence register; no coordinates or municipal centroid substituted.',
]


def official_url(base, href):
    url = urljoin(base, href.strip())
    p = urlparse(url)
    if p.scheme != 'https' or p.hostname != 'www.sonservera.es' or not p.path.startswith('/portal/'):
        raise ValueError('Unexpected non-municipal source URL: ' + url)
    return url


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('#interior_cuerpo')
    if body is None or body.select_one('h2') is None or body.select_one('.interior_texto') is None:
        raise ValueError('Municipal content missing; possible changed markup/login')
    return body


def complete(body, count):
    """Fail closed on paging or totals that exceed extracted rows."""
    for a in body.select('.paginacion a[href], a[rel~=next]'):
        if a['href'].strip() not in ('', '#'):
            raise ValueError('Pagination detected; refusing incomplete inventory')
    pager = body.select_one('.paginacion')
    match = re.search(r'(\d+)\s+contenidos', pager.get_text(' ', strip=True)) if pager else None
    if not match or int(match[1]) != count:
        raise ValueError('Inventory total missing or mismatches extracted items')


def discover(html, url=SOURCE):
    body = content(html)
    if body.select_one('h2').get_text(' ', strip=True) != 'Urbanismo y vivienda':
        raise ValueError('Unexpected urbanism inventory heading')
    soup = BeautifulSoup(html, 'html.parser')
    found = {}
    for a in soup.select('a[href]'):
        title = a.get_text(' ', strip=True)
        if title == 'Normas Subsidiarias' or re.fullmatch(r'Modificación núm\. \d+ de NNSS', title):
            dest = official_url(url, a['href'])
            if title in found and found[title] != dest:
                raise ValueError('Conflicting menu sources')
            found[title] = dest
    if 'Normas Subsidiarias' not in found or len(found) < 2:
        raise ValueError('Missing NNSS inventories')
    return found


def revision_links(html, url):
    body = content(html)
    links = [official_url(url, a['href']) for a in body.select('#listado #descriptivo li a[href]')]
    complete(body, len(links))
    if not links:
        raise ValueError('Empty revision inventory')
    return list(dict.fromkeys(links))


def documents(html, url):
    """Return (instrument key, document) pairs; table section overrides page label."""
    body = content(html)
    title = body.select_one('h2').get_text(' ', strip=True)
    text = body.select_one('.interior_texto')
    pairs = []
    if title.startswith('Modificación núm.'):
        section = None
        count = 0
        for tr in text.select('table.listado tr'):
            h = tr.select_one('h3')
            if h:
                section = h.get_text(' ', strip=True)
                continue
            a = tr.select_one('a.linkTb01[href]')
            if not a:
                continue
            count += 1
            m = re.search(r'modificaci[oó]n\s*(?:núm\.?\s*)?(\d+)\s+NNSS', section or '', re.I)
            files = [x for x in tr.select('a[href]') if '/DOCUMENTOS/' in x['href']]
            if not m or len(files) != 1:
                raise ValueError('Unrecognized document group or missing file')
            pairs.append(('modificacion-' + m[1], {
                'titulo': a.get_text(' ', strip=True),
                'url': official_url(url, files[0]['href']),
                'url_ficha': official_url(url, a['href']),
                'seccion': section, 'source_urls': [url],
            }))
        complete(body, count)
    elif title.startswith('Revisión Normas Subsidiarias') or title == 'Normas Subsidiarias Planos':
        for a in text.select('.masinfo a[href]'):
            if '/DOCUMENTOS/' in a['href']:
                pairs.append(('revision', {'titulo': a.get_text(' ', strip=True),
                    'url': official_url(url, a['href']), 'source_urls': [url]}))
    else:
        raise ValueError('Unexpected NNSS detail heading: ' + title)
    if not pairs:
        raise ValueError('No source documents')
    narrative = text.find('div', recursive=False) if title.startswith('Modificación') else None
    description = narrative.get_text(' ', strip=True) if narrative else ''
    approval = None
    if title.startswith('Revisión'):
        match = re.search(r'Aprobación definitiva con fecha (\d{1,2}) de marzo de (\d{4})', text.get_text(' ', strip=True))
        if match:
            approval = date(int(match[2]), 3, int(match[1])).isoformat()
    return pairs, description, approval


class SonServeraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='son-servera', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []

    def _fetch(self, url):
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-son-servera/1.0'}) as response:
            response.raise_for_status()
            official_url(url, response.url)
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected municipal HTML')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Municipal response exceeds size bound')
                chunks.append(chunk)
            raw = b''.join(chunks)
        self.source_urls.append(url)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(raw)
        return raw

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        inventories = discover(self._fetch(SOURCE))
        revision_url = inventories.pop('Normas Subsidiarias')
        pages = revision_links(self._fetch(revision_url), revision_url) + list(inventories.values())
        groups = {}
        for url in dict.fromkeys(pages):
            pairs, description, approval = documents(self._fetch(url), url)
            for key, doc in pairs:
                row = groups.setdefault(key, {
                    'id': 'son-servera-proy-nnss-' + key,
                    'municipio': 'Son Servera', 'codigo_ine': '07062', 'provincia': 'Illes Balears',
                    'titulo': ('Revisión de las Normas Subsidiarias de Son Servera' if key == 'revision'
                               else 'Modificación núm. ' + key.split('-')[1] + ' de NNSS de Son Servera'),
                    'tipo': 'planeamiento_urbanistico', 'fase': None,
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_documental_nnss',
                    'source_urls': [], 'descripcion': '', 'documentos': [],
                    'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                })
                if url not in row['source_urls']:
                    row['source_urls'].append(url)
                if description and description not in row['descripcion']:
                    row['descripcion'] = (row['descripcion'] + '\n' + description).strip()
                if approval:
                    row['fecha_aprob'], row['fase'] = approval, 'aprobación definitiva'
                existing = next((d for d in row['documentos'] if d['url'] == doc['url']), None)
                if existing:
                    existing['source_urls'] = sorted(set(existing['source_urls'] + doc['source_urls']))
                else:
                    row['documentos'].append(doc)
        expected = {'revision'} | {'modificacion-' + re.search(r'\d+', name)[0] for name in inventories}
        if set(groups) != expected:
            raise ValueError('Instrument groups do not match discovered menu')
        rows = sorted(groups.values(), key=lambda r: r['id'])
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot refresh: no dates are used as incremental cursors.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
