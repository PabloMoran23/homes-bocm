"""Villamartín (Cádiz): official planning folders, including Wicket pagination."""
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

HOST = 'villamartin.sedelectronica.es'
SOURCE = f'https://{HOST}/transparency/b02afb40-7954-4692-b8c1-431b2fd2da28/'
LIMITATIONS = [
    'Solo inventario 7.1 Planeamiento urbanístico; no registro exhaustivo de obras o licencias.',
    'Incluye documentación provisional histórica; no acredita vigencia ni aprobación actual.',
    'Sin fechas de publicación/acuerdo verificadas ni coordenadas; no se infieren de títulos o CMS.',
    'Se conservan enlaces oficiales de previsualización; no se interpreta el contenido de cada PDF.',
]


def official_url(url):
    p = urlparse(url)
    if p.scheme != 'https' or p.hostname != HOST:
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def action_url(element, url):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing Wicket navigation action')
    return official_url(urljoin(url, match[1]))


def parse_page(text, url):
    """Parse a full page or append-only AJAX components, without executing JS."""
    ajax = text.lstrip().startswith('<?xml')
    if ajax:
        root = ET.fromstring(text)
        if root.tag != 'ajax-response' or root.find('redirect') is not None:
            raise ValueError('Unexpected AJAX response')
        components = [c.text or '' for c in root.findall('component')]
        if not components:
            raise ValueError('AJAX response lacks inventory components')
        text = '<div class="TransparencyListPanel">' + ''.join(components) + '</div>'
    soup = BeautifulSoup(text, 'html.parser')
    table = soup.select_one('.TransparencyListPanel')
    if table is None:
        raise ValueError('Missing official inventory table')
    entries = []
    for a in table.select('a.gIconLink'):
        title_node = BeautifulSoup(str(a), 'html.parser')
        for span in title_node.select('.linkExtraInfo'):
            span.decompose()
        title = title_node.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            count_node = a.select_one('.linkExtraInfo')
            count_match = re.fullmatch(r'\s*\(\s*(\d+)\s*\)\s*', count_node.get_text() if count_node else '')
            if not count_match:
                raise ValueError('Folder lacks advertised document count')
            entries.append({'title': title, 'folder': True, 'count': int(count_match[1]),
                            'url': action_url(a, url)})
        else:
            target = official_url(urljoin(url, a.get('href', '')))
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(target).path):
                raise ValueError('Unknown inventory document link')
            entries.append({'title': title, 'folder': False, 'url': target})
    more = soup.select_one('.more_results button')
    if soup.select_one('[rel="next"], .pagination, .paginator'):
        raise ValueError('Unreviewed pagination controls')
    return entries, action_url(more, url) if more else None


class VillamartinAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(official_url(url), timeout=40)
        response.raise_for_status()
        official_url(response.url)
        self.source_urls.add(response.url)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = f'source-{len(self.captures) + 1:03}.html'
            (directory / name).write_text(response.text, encoding='utf-8')
            self.captures.append({'file': name, 'url': response.url,
                                  'sha256': hashlib.sha256(response.content).hexdigest()})
        return response.text, response.url

    def _entries(self, session, text, url):
        entries, more = parse_page(text, url)
        seen = {e['url'] for e in entries}
        while more:
            text, page_url = self._fetch(session, more)
            new, more = parse_page(text, page_url)
            if not new or any(e['url'] in seen for e in new):
                raise ValueError('Pagination repeated documents or made no progress')
            seen.update(e['url'] for e in new)
            entries.extend(new)
        return entries

    def _documents(self, session, entry, parents, visited):
        if not entry['folder']:
            return [{'titulo': entry['title'], 'url': entry['url'], 'carpetas': parents}]
        text, url = self._fetch(session, entry['url'])
        if url in visited:
            raise ValueError('Repeated planning folder')
        visited.add(url)
        children = self._entries(session, text, url)
        docs = []
        for child in children:
            docs.extend(self._documents(session, child, parents + [{'titulo': entry['title'], 'url': url}], visited))
        if len(docs) != entry['count']:
            raise ValueError(f"Incomplete folder {entry['title']}: {len(docs)} != {entry['count']}")
        entry['canonical_url'] = url
        return docs

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls, self.captures = set(), []
        rows = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-villamartin/1.0 (public planning inventory)'
            text, url = self._fetch(session, SOURCE)
            entries = self._entries(session, text, url)
            if not entries:
                raise ValueError('Empty planning inventory')
            visited = set()
            for entry in entries:
                if not re.match(r'^(?:MODIFICACI[OÓ]N (?:DEL )?PLAN|PLAN GENERAL)\b', entry['title'], re.I):
                    raise ValueError(f"Unreviewed planning entry: {entry['title']}")
                docs = self._documents(session, entry, [], visited)
                target = entry.get('canonical_url', entry['url'])
                rows.append({'id': 'villamartin-plan-' + hashlib.sha256(target.encode()).hexdigest()[:20],
                             'municipio': 'Villamartín', 'codigo_ine': '11041', 'provincia': 'Cádiz',
                             'titulo': entry['title'], 'tipo': 'planeamiento_urbanistico',
                             'url': target, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
                             'origen': 'inventario_documental_planeamiento', 'documentos': docs,
                             'publication_ready': False, 'geometry_status': 'unavailable',
                             'coverage': 'inventario_7_1_parcial', 'limitations': LIMITATIONS})
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': sorted(self.source_urls), 'limitations': LIMITATIONS, 'captures': self.captures}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
