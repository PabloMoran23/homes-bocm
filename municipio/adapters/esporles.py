"""Esporles' public planning archive; document bundles are instruments, not permits."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://esporles.cat/ca/arxius-i-documents/urbanisme'
LIMITATIONS = [
    'Partial coverage: only Normativa and the carrer de la Llum study folder in Urbanisme; not a complete works or planning register.',
    'Historical archive currently accessible; legal currency is not certified. The Urbanisme archive also lists revocation of provisional NNSS approval.',
    'Attachments are retained as links with provenance, not interpreted as separate projects or verified granted licences.',
    'No dates inferred from filenames, upload directories, HTTP metadata or month-only text; no verified geometry.',
]
ROOT_TYPES = {
    'Normes Subsidiàries': 'normas_subsidiarias',
    'Adaptació de les Normes Subsidiàries al Pla Territorial': 'adaptacion_planeamiento',
    'Catàleg de Patrimoni Històric': 'catalogo_proteccion',
}
STUDY = 'Aprovació inicial estudi de detall c/ de la Llum'


def official_url(base: str, href: str) -> str:
    url = urldefrag(urljoin(base, href))[0]
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'esporles.cat':
        raise ValueError(f'Unexpected non-municipal URL: {url}')
    return url


def parse_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.region-content')
    if content is None or not content.select_one('h1'):
        raise ValueError(f'Missing archive content: {url}')

    def links(selector):
        return list(dict.fromkeys(
            (a.get_text(' ', strip=True), official_url(url, a['href']))
            for a in content.select(selector)
        ))

    # Follow every linked pager destination, including numeric/last links.
    # A pager whose navigation cannot be read is an error, never a partial success.
    pagers = content.select('.pager, .pagination, nav[aria-label*="agin"]')
    pages = set()
    for pager in pagers:
        for a in pager.select('a[href]'):
            if a['href'] and not a['href'].startswith('#'):
                pages.add(official_url(url, a['href']))
        if not pager.select('a[href]'):
            raise ValueError(f'Unrecognized pagination: {url}')
    for a in content.select('a[rel~=next][href]'):
        pages.add(official_url(url, a['href']))
    return {
        'title': content.select_one('h1').get_text(' ', strip=True),
        'description': '\n'.join(x.get_text(' ', strip=True) for x in content.select(
            '.field--name-description, .field--name-body')),
        'folders': links('.view-children-terms a[href]'),
        'entries': links('article h2 a[href]'),
        'documents': links('.field--name-field-attached-files a[href]'),
        'pages': sorted(pages),
    }


class EsporlesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)
        self.source_urls: list[str] = []

    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-esporles/1.0 (public planning archive)',
        })
        response.raise_for_status()
        official_url(url, response.url)
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError(f'Expected HTML archive page: {url}')
        response.encoding = 'utf-8'
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
            (directory / name).write_text(response.text, encoding='utf-8')
        return response.text

    def extract(self, fetch=None):
        fetch = fetch or self._fetch
        cache, rows, visited = {}, {}, set()

        def page(url):
            if url not in cache:
                if len(cache) >= 200:
                    raise ValueError('Archive traversal exceeds safety bound; no partial output')
                cache[url] = parse_page(fetch(url), url)
            return cache[url]

        def listing(url):
            pending, seen = [url], set()
            while pending:
                current = pending.pop(0)
                if current in seen:
                    continue
                seen.add(current)
                data = page(current)
                yield current, data
                pending.extend(p for p in data['pages'] if p not in seen)

        def new_row(title, url, kind, parent=None):
            if url not in rows:
                rows[url] = {
                    'id': 'esporles-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                    'municipio': 'Esporles', 'codigo_ine': '07020', 'provincia': 'Illes Balears',
                    'titulo': title, 'tipo': kind, 'url': url,
                    'source': 'ayuntamiento', 'origen': 'archivo_planeamiento_municipal',
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                    'fecha_aprob': None, 'fase': None,
                    'documentos': [], 'fuentes': [], 'descripcion': '',
                    'instrumento_padre_url': parent,
                    'lat': None, 'lon': None, 'geometry': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                    'coverage': 'partial_historical_archive',
                }
            return rows[url]

        def walk(url, row):
            key = (url, row['id'])
            if key in visited:
                return
            visited.add(key)
            for current, data in listing(url):
                if current not in row['fuentes']:
                    row['fuentes'].append(current)
                if data['description']:
                    row['descripcion'] += data['description'] + '\n'
                for title, doc in data['documents']:
                    if not urlparse(doc).path.startswith('/sites/cilma_esporles/files/'):
                        raise ValueError(f'Unexpected attachment: {doc}')
                    existing = next((d for d in row['documentos'] if d['url'] == doc), None)
                    if existing is None:
                        row['documentos'].append({'titulo': title, 'url': doc, 'fuentes': [current]})
                    elif current not in existing['fuentes']:
                        existing['fuentes'].append(current)
                for _, child in data['folders']:
                    walk(child, row)
                for title, child in data['entries']:
                    if re.match(r'^(Modificació|Aprovació definitiva de la modificació)\b', title):
                        modification = new_row(title, child, 'modificacion_planeamiento', row['url'])
                        if title.startswith('Aprovació definitiva'):
                            modification['fase'] = 'aprobación definitiva (según título municipal)'
                        walk(child, modification)
                    else:
                        walk(child, row)

        found = set()
        for _, data in listing(SOURCE):
            for title, url in data['folders']:
                if title == 'Normativa':
                    found.add(title)
                    for _, normative in listing(url):
                        for name, root in normative['folders']:
                            if name not in ROOT_TYPES:
                                raise ValueError(f'Unreviewed planning folder: {name}')
                            found.add(name)
                            walk(root, new_row(name, root, ROOT_TYPES[name]))
                elif title == STUDY:
                    found.add(title)
                    row = new_row(title, url, 'estudio_detalle')
                    row['fase'] = 'aprobación inicial (según título municipal)'
                    walk(url, row)
                else:
                    raise ValueError(f'Unreviewed Urbanisme folder: {title}')
        if found != {'Normativa', STUDY, *ROOT_TYPES}:
            raise ValueError('Expected planning inventory missing; review source')
        for row in rows.values():
            if not row['documentos']:
                raise ValueError(f'Instrument has no source documents: {row["url"]}')
            row['descripcion'] = row['descripcion'].strip()
            # The only exact dates exposed by the reviewed folder descriptions.
            # Scope the match to the NS paragraph, never the PTIM parent-plan date.
            if row['tipo'] == 'normas_subsidiarias':
                match = re.search(r'aprovades definitivament[^.]*?el (\d{2}/\d{2}/\d{4}) \(BOIB (\d{2}/\d{2}/\d{4})\)', row['descripcion'])
                if match:
                    row['fecha_aprob'], row['fecha_publicacion'] = (
                        datetime.strptime(d, '%d/%m/%Y').date().isoformat() for d in match.groups())
                    row['fase'] = 'aprobación definitiva (según descripción municipal)'
        self.source_urls = sorted(cache)
        return sorted(rows.values(), key=lambda r: r['id'])

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = self.extract()
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
