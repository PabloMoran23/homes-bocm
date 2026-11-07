"""Municipal planning inventory: plans and their grouped source documents."""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.ermua.eus'
SOURCE = BASE + '/es/ayuntamiento/accion-gobierno/planes-municipales'


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _body(html):
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('article.node .field--name-body')
    if body is None:
        raise ValueError('Missing municipal content body')
    if soup.select('.pager a[href], a[rel~=next]') or any(
        _text(a).lower() in {'siguiente', 'next', 'hurrengoa', '›', '»'}
        and a.get('href') not in {'', '#'} for a in soup.select('a[href]')
    ):
        raise ValueError('Unexpected pagination: traversal needs review')
    return soup, body


def parse_inventory(html):
    _, body = _body(html)
    active = False
    links = {}
    for tag in body.find_all(['h2', 'a']):
        title = _text(tag)
        if tag.name == 'h2':
            active = title.lower() == 'urbanismo'
        elif active and re.match(r'^Plan (?:General de Ordenación Urbana|Especial\b)', title, re.I):
            url = urljoin(SOURCE, tag.get('href', ''))
            if urlparse(url).hostname != 'www.ermua.eus' or '/planes-municipales/' not in url:
                raise ValueError('Unexpected planning detail URL')
            links[url] = title
    if len(links) < 3:
        raise ValueError('Planning inventory incomplete or changed')
    return list(links.items())


def _record(key, title, url, description='', phase=None, year=None):
    return {
        'id': 'ermua-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
        'municipio': 'Ermua', 'codigo_ine': '48034', 'provincia': 'Bizkaia',
        'titulo': title, 'tipo': 'planeamiento_urbanistico', 'fase': phase,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'anio_aprobacion': year,
        'url': url, 'source': 'ayuntamiento', 'origen': 'planes_municipales',
        'descripcion': description, 'documentos': [],
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


def parse_plan(html, url):
    soup, body = _body(html)
    heading = soup.select_one('h1')
    if heading is None or not re.match(r'^Plan (?:general|especial)', _text(heading), re.I):
        raise ValueError('Missing planning title')
    title = _text(heading)
    paragraphs = [_text(p) for p in body.find_all('p', recursive=False) if not p.find('a') and _text(p)]
    description = '\n'.join(paragraphs)
    is_pgou = 'general de ordenación urbana' in title.lower()
    year = re.search(r'aprobado en el año (\d{4})', description, re.I) if is_pgou else None
    current = _record(url, title + ' de Ermua', url, description,
                      'aprobado' if year else None, int(year[1]) if year else None)
    rows = [current]
    for tag in body.find_all(['li', 'p', 'a']):
        # Only the actual list item labels delimit amendments; enclosing blocks
        # and linked document titles must never open additional instruments.
        marker = re.match(r'^(\d{4}):\s*(Aprobación definitiva de la (\d+)[ªº].*Modificación.*)$', _text(tag), re.I) if tag.name in {'li', 'p'} and not tag.find(['li', 'p', 'a']) else None
        if tag.name in {'li', 'p'} and not tag.find(['li', 'p', 'a']) and re.match(r'^\d{4}:', _text(tag)) and not marker:
            raise ValueError('Unrecognized dated instrument label; review grouping')
        if marker:
            if not is_pgou:
                raise ValueError('Unexpected amendment outside PGOU')
            current = _record(url + '#modificacion-' + marker[3], marker[2], url,
                              marker[0], 'aprobación definitiva', int(marker[1]))
            current['parent_id'] = rows[0]['id']
            rows.append(current)
        if tag.name != 'a' or not tag.get('href'):
            continue
        link = urljoin(url, tag['href'])
        parsed = urlparse(link)
        if parsed.hostname not in {'www.ermua.eus', 'abiapuntu.ermua.eus'}:
            raise ValueError('Unexpected external document in planning body')
        if parsed.path.lower().endswith('.pdf') or 'sesiones_organos_gobierno' in link or parsed.hostname == 'abiapuntu.ermua.eus':
            doc = {'titulo': _text(tag), 'url': link, 'source_url': url,
                   'tipo': 'documento' if parsed.path.lower().endswith('.pdf') else 'sesion_plenaria'}
            if not any(d['url'] == link for d in current['documentos']):
                current['documentos'].append(doc)
    for row in rows:
        if not any(d['tipo'] == 'documento' for d in row['documentos']):
            raise ValueError('Instrument lacks documentary evidence')
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate instrument identifier')
    return rows


class ErmuaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'Mozilla/5.0 (compatible; MunicipioErmua/1.0)'})
        response.raise_for_status()
        if len(response.content) > 4_000_000:
            raise ValueError('Oversized municipal HTML')
        html = response.content.decode('utf-8')
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        rows = []
        sources = [SOURCE]
        for url, _ in parse_inventory(self._fetch(SOURCE)):
            time.sleep(.25)
            rows.extend(parse_plan(self._fetch(url), url))
            sources.append(url)
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': sources, 'coverage': 'partial: municipal PGOU and special plans'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
