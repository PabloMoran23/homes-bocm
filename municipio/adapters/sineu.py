"""Reviewed Sineu urbanisme inventory; document bundles, not licence grants."""
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

SOURCE = 'https://ajsineu.net/ca/archivos-y-documentos/urbanisme'
PREFIX = '/ca/arxius-i-documents/urbanisme/'
# Reviewed source identities. New entries require review instead of being silently
# dropped or converted into projects based on words such as "obres".
GROUPS = {
    'normes-subsidiaries-de-sineu': 'nnss',
    'modificacions-i-adaptacio-normes-subsidiaries-de-sineu': 'adaptacio-nnss',
    'programa-area-rehabilitacion-integral-del-casco-antiguo-del-municipio': 'ari',
    'delimitacion-ari-nucleo-historico-sineu': 'ari',
}
EXCLUDED = {'tramitacions-xarxes-de-distribucio'}
LIMITATIONS = [
    'Partial coverage: reviewed municipal Urbanisme document inventory only; not all municipal works, heritage catalogues or bulletins.',
    'Documents may be historical; availability does not establish current legal validity, approval or execution.',
    'Portal file dates are retained as document metadata, not publication or agreement dates; PDF dates are not automatically extracted.',
    'No verified granted-licence register or project geometry; no inferred coordinates.',
]


def official(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'ajsineu.net':
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def content(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None or main.select_one('h1') is None:
        raise ValueError('Missing municipal main content/title')
    # This source is currently unpaginated. Fail visibly if pagination appears;
    # never emit a successful first-page-only snapshot.
    if main.select_one('.pager, .pagination, [rel~=next], .pager__item'):
        raise ValueError('Pagination detected; crawler review required')
    for a in main.select('a[href]'):
        if re.search(r'[?&]page=', a['href']) or a.get_text(' ', strip=True).casefold() in {'següent', 'siguiente', 'next', '›', '»'}:
            raise ValueError('Pagination detected; crawler review required')
    return main


def parse_inventory(html: str) -> list[dict]:
    main = content(html)
    if main.select_one('h1').get_text(' ', strip=True) != 'Urbanisme':
        raise ValueError('Unexpected inventory title')
    container = main.select_one('.taxonomy-term-files')
    if container is None:
        raise ValueError('Missing document inventory')
    entries = {}
    for heading in container.select('h3'):
        a = heading.find_parent('a', href=True)
        if a is None:
            raise ValueError('Document card lacks URL')
        url = official(urljoin(SOURCE, a['href']))
        if not urlparse(url).path.startswith(PREFIX):
            raise ValueError('Unexpected inventory item path')
        key = urlparse(url).path[len(PREFIX):].rstrip('/')
        if key not in GROUPS and key not in EXCLUDED:
            raise ValueError(f'Unreviewed inventory entry: {key}')
        count = re.search(r'\b(\d+)\s+documents?\b', a.get_text(' ', strip=True))
        if count is None:
            raise ValueError('Missing attachment count')
        item = {'key': key, 'url': url, 'titulo': heading.get_text(' ', strip=True), 'document_count': int(count[1])}
        if key in entries and entries[key] != item:
            raise ValueError('Conflicting inventory cards')
        entries[key] = item
    if not entries or not any(k in GROUPS for k in entries):
        raise ValueError('No reviewed planning instruments found')
    return list(entries.values())


def parse_documents(html: str, entry: dict) -> list[dict]:
    main = content(html)
    if main.select_one('h1').get_text(' ', strip=True) != entry['titulo']:
        raise ValueError('Inventory/detail title mismatch')
    article = main.select_one('article.node-file-or-document')
    if article is None:
        raise ValueError('Missing document detail')
    docs = {}
    for link in article.select('a[download][href]'):
        url = official(urljoin(entry['url'], link['href']))
        if not urlparse(url).path.startswith('/sites/cilma_sineu/files/') or not urlparse(url).path.lower().endswith('.pdf'):
            raise ValueError('Unexpected document location/type')
        block = link.parent
        title = block.select_one('h3')
        if title is None:
            raise ValueError('Missing attachment title')
        dates = re.findall(r'\b\d{2}/\d{2}/\d{4}\b', block.get_text(' ', strip=True))
        if len(set(dates)) > 1:
            raise ValueError('Ambiguous portal file date')
        file_date = datetime.strptime(dates[0], '%d/%m/%Y').date().isoformat() if dates else None
        docs[url] = {'titulo': title.get_text(' ', strip=True), 'url': url,
                     'source_page': entry['url'], 'fecha_fichero_portal': file_date,
                     'fecha_publicacion': None, 'fecha_acuerdo': None}
    if not docs or len(docs) != entry['document_count']:
        raise ValueError('Attachment count mismatch or empty detail')
    return list(docs.values())


def group_records(entries: list[dict], documents: dict[str, list[dict]]) -> list[dict]:
    groups = {}
    for entry in entries:
        if entry['key'] in EXCLUDED:
            continue
        groups.setdefault(GROUPS[entry['key']], []).append(entry)
    records = []
    for group, members in sorted(groups.items()):
        # The ARI boundary is supporting documentation of the rehabilitation
        # programme, not a second project. NNSS adaptation is a distinct act.
        primary = next((e for e in members if e['key'].startswith('programa-')), members[0])
        docs = {d['url']: d for e in members for d in documents[e['key']]}
        records.append({
            'id': 'sineu-proy-' + group, 'municipio': 'Sineu', 'codigo_ine': '07060',
            'provincia': 'Illes Balears', 'titulo': primary['titulo'],
            'tipo': 'programa_rehabilitacion_urbana' if group == 'ari' else 'planeamiento_urbanistico',
            'url': primary['url'], 'inventory_url': SOURCE,
            'source': 'ayuntamiento', 'origen': 'inventario_urbanisme',
            'source_pages': [e['url'] for e in members],
            'documentos': list(docs.values()), 'fecha': None,
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'fase': None, 'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'partial_reviewed_urbanisme_inventory',
        })
    return records


class SineuAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='sineu', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://ajsineu.net')

    def _fetch(self, url: str, *, pdf=False) -> bytes:
        official(url)
        with requests.get(url, timeout=(15, 60), stream=True,
                          headers={'User-Agent': 'municipio-sineu/1.0'}) as response:
            response.raise_for_status()
            official(response.url)
            chunks, size = [], 0
            limit = 25_000_000 if pdf else 3_000_000
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source exceeds reviewed response size')
                chunks.append(chunk)
            data = b''.join(chunks)
        if pdf and not data.startswith(b'%PDF-'):
            raise ValueError('Document response is not a PDF')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest() + ('.pdf' if pdf else '.html')
            (path / name).write_bytes(data)
        return data

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        entries = parse_inventory(self._fetch(SOURCE).decode('utf-8'))
        documents = {}
        source_urls = [SOURCE]
        for entry in entries:
            if entry['key'] in EXCLUDED:
                continue
            source_urls.append(entry['url'])
            docs = parse_documents(self._fetch(entry['url']).decode('utf-8'), entry)
            for doc in docs:
                data = self._fetch(doc['url'], pdf=True)
                doc['sha256'] = hashlib.sha256(data).hexdigest()
                source_urls.append(doc['url'])
            documents[entry['key']] = docs
        rows = group_records(entries, documents)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': source_urls,
                'inventory_entries': len(entries),
                'excluded_entries': [e for e in entries if e['key'] in EXCLUDED],
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
