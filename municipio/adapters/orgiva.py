"""Órgiva: general planning instruments in the public municipal document inventory.

Wicket folder navigation uses Ajax-Location; document links are stable previews.
No execution of JavaScript, licence claims, inferred dates or coordinates.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://orgiva.sedelectronica.es/transparency/dfa36414-bbe5-4574-a2c1-ce698b725e59/'
HOST = 'orgiva.sedelectronica.es'
LIMITATIONS = [
    'Cobertura parcial: solo PBOM y Plan de Delimitación de Suelo Urbano del inventario de planeamiento.',
    'Excluye estudios de detalle, urbanización, obras, convenios y otras categorías; no es un registro de licencias.',
    'Los documentos de consulta y avance no acreditan aprobación definitiva ni vigencia actual.',
    'Sin fechas de publicación/acuerdo verificadas ni coordenadas; enlaces a visores oficiales, no PDF directos.',
]


def official_url(base, target):
    url = urljoin(base, target)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != HOST:
        raise ValueError('Unexpected external source URL')
    return url


def ajax_url(node, base):
    match = re.search(r"wicketAjaxGet\('([^']+)'", node.get('onclick', ''))
    if not match:
        raise ValueError('Missing Wicket navigation action')
    return official_url(base, match[1])


def parse_page(body, *, ajax=False):
    """Read initial HTML or Wicket component fragments, never evaluate scripts."""
    if ajax:
        root = ET.fromstring(body)
        if root.tag != 'ajax-response':
            raise ValueError('Unexpected pagination response')
        fragments = [node.text or '' for node in root.findall('component')]
        if not fragments:
            raise ValueError('Pagination returned no components')
        soup = BeautifulSoup(''.join(fragments), 'html.parser')
    else:
        soup = BeautifulSoup(body, 'html.parser')
        table = soup.select_one('table.TransparencyListPanel')
        if table is None:
            raise ValueError('Municipal inventory table missing')
    entries = []
    selector = 'a.gIconLink' if ajax else 'table.TransparencyListPanel a.gIconLink'
    for a in soup.select(selector):
        text = a.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            count = re.search(r'\(\s*(\d+)\s*\)\s*$', text)
            if not count:
                raise ValueError('Folder document count missing')
            entries.append({'kind': 'folder', 'titulo': text[:count.start()].strip(),
                            'count': int(count[1]), 'node': a})
        elif '/preview-document/' in a.get('href', ''):
            entries.append({'kind': 'document', 'titulo': text, 'url': a['href'],
                            'descripcion_fuente': a.get('title', '')})
        else:
            raise ValueError('Unrecognized inventory entry')
    more = soup.select('.more_results button[onclick]')
    if len(more) > 1:
        raise ValueError('Ambiguous pagination')
    # Fail closed if the site switches to conventional pagination.
    if soup.select('a[rel=next], .pagination, .paginator'):
        raise ValueError('Unsupported pagination layout')
    return entries, more[0] if more else None


class OrgivaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, session, url, *, ajax=False):
        official_url(SOURCE, url)
        response = session.get(url, timeout=40, allow_redirects=False,
                               headers={'Wicket-Ajax': 'true'} if ajax else {})
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError('Unexpected source redirect/status')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            number = len(self.source_urls)
            (directory / f'source-{number:03d}.txt').write_text(response.text, encoding='utf-8')
        self.source_urls.append(url)
        return response

    def _listing(self, session, url):
        body = self._get(session, url).text
        entries, more = parse_page(body)
        seen = {(e['kind'], e['titulo'], e.get('url')) for e in entries}
        pages = 0
        # A safety limit raises instead of returning a truncated result.
        while more is not None:
            if pages >= 100:
                raise ValueError('Pagination safety limit exceeded')
            action = ajax_url(more, url)
            pages += 1
            batch, more = parse_page(self._get(session, action, ajax=True).text, ajax=True)
            identities = {(e['kind'], e['titulo'], e.get('url')) for e in batch}
            if not identities.difference(seen) and more is not None:
                raise ValueError('Pagination made no progress')
            seen.update(identities)
            entries.extend(batch)
        return entries

    def _folder(self, session, entry, parent):
        response = self._get(session, ajax_url(entry['node'], parent), ajax=True)
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Folder navigation lacks Ajax-Location')
        target = official_url(parent, location)
        if not re.fullmatch(r'/transparency/[0-9a-f-]{36}/', urlparse(target).path):
            raise ValueError('Unexpected folder destination')
        return target

    def _documents(self, session, url, visited):
        if url in visited or len(visited) >= 100:
            raise ValueError('Folder cycle or safety limit exceeded')
        visited.add(url)
        documents = {}
        for entry in self._listing(session, url):
            if entry['kind'] == 'folder':
                child = self._folder(session, entry, url)
                docs = self._documents(session, child, visited)
                if len(docs) != entry['count']:
                    raise ValueError('Folder count differs from extracted documents')
            else:
                docs = [self._document(entry, url)]
            for doc in docs:
                documents.setdefault(doc['url'], doc)
        return list(documents.values())

    @staticmethod
    def _document(entry, inventory_url):
        return {'titulo': entry['titulo'], 'url': official_url(inventory_url, entry['url']),
                'inventory_url': inventory_url, 'descripcion_fuente': entry['descripcion_fuente']}

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = []
        rows = {}
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-orgiva/1.0 (public planning inventory)'
            for entry in self._listing(session, SOURCE):
                title = entry['titulo']
                if entry['kind'] == 'folder' and title == 'PBOM':
                    url = self._folder(session, entry, SOURCE)
                    docs = self._documents(session, url, set())
                    if not docs or len(docs) != entry['count']:
                        raise ValueError('Incomplete PBOM document inventory')
                elif entry['kind'] == 'document' and re.match(r'^PLAN DELIMITACI[ÓO]N SUELO URBANO\b', title, re.I):
                    url = official_url(SOURCE, entry['url'])
                    docs = [self._document(entry, SOURCE)]
                else:
                    continue
                key = 'orgiva-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16]
                rows[key] = {'id': key, 'titulo': title, 'municipio': 'Órgiva',
                             'codigo_ine': '18147', 'provincia': 'Granada',
                             'tipo': 'planeamiento_urbanistico', 'url': url,
                             'inventory_url': SOURCE, 'documentos': docs,
                             'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_general',
                             'publication_ready': False, 'geometry_status': 'unavailable',
                             'limitaciones': LIMITATIONS}
        if not rows:
            raise ValueError('No supported general planning instruments found')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n'
                                     for r in rows.values()), encoding='utf-8')
        temporary.replace(output)
        return {'count': len(rows), 'written': len(rows), 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'coverage': 'partial_general_planning_inventory'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        raise NotImplementedError('Licencias disabled: no verified public grant register')

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
