"""Current public NNSS inventory: one record per instrument, all document pages."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'albuixech.sedelectronica.es'
SOURCE = f'https://{HOST}/transparency/6b558ca4-37b4-4ebf-9fb0-9d77b2e06c18/'
LIMITATIONS = [
    'Partial municipal coverage: current sede NNSS inventory only; not all planning or works.',
    'Document titles and official preview links retained; PDF contents are not parsed.',
    'No verified agreement, approval or publication dates; filename years and portal clock are not dates.',
    'No verified coordinates or geometry; publication_ready=false.',
    'No public granted-licence register verified; licences disabled.',
]


def action_url(tag, base):
    match = re.search(r"wicketAjaxGet\('([^']+)'", tag.get('onclick', ''))
    if not match:
        raise ValueError('Missing public navigation action')
    url = urljoin(base, match[1])
    if urlparse(url).hostname != HOST or urlparse(url).scheme != 'https':
        raise ValueError('Unexpected navigation host')
    return url


def fragment(text):
    """Read Wicket component HTML without executing its scripts."""
    if text.lstrip().startswith('<?xml'):
        root = ElementTree.fromstring(text)
        if root.tag != 'ajax-response' or root.find('redirect') is not None:
            raise ValueError('Unexpected AJAX response')
        parts = [node.text or '' for node in root.findall('component')]
        if not parts:
            raise ValueError('No pagination components')
        return BeautifulSoup('\n'.join(parts), 'html.parser')
    soup = BeautifulSoup(text, 'html.parser')
    content = soup.select_one('#content')
    if content is None or content.select_one('table.TransparencyListPanel') is None:
        raise ValueError('Missing public transparency inventory')
    return content


def entries(content, base):
    docs, folders = {}, []
    for a in content.select('a.gIconLink'):
        if 'exp' in a.get('class', []):
            count = a.select_one('.linkExtraInfo')
            if count is None or not re.fullmatch(r'\s*\(\s*\d+\s*\)\s*', count.text):
                raise ValueError('Missing folder document count')
            title = ' '.join(a.get_text(' ', strip=True).split())
            title = re.sub(r'\s*\(\s*\d+\s*\)\s*$', '', title)
            folders.append((title, int(re.search(r'\d+', count.text)[0]), action_url(a, base)))
        else:
            url = urljoin(base, a.get('href', ''))
            if urlparse(url).hostname != HOST or not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(url).path):
                # External cartographic viewers are inventory aids, not projects.
                continue
            title = ' '.join(a.get_text(' ', strip=True).split())
            if not title:
                raise ValueError('Untitled source document')
            docs[url] = {'titulo': title, 'url': url, 'source_url': base}
    more = [a for a in content.select('button[onclick], a[onclick]')
            if a.get_text(' ', strip=True).casefold() in {'mostrar más', 'mostrar mas'}]
    if len(more) > 1:
        raise ValueError('Ambiguous pagination')
    # Never silently ignore a newly introduced next-page control.
    for a in content.select('a, button'):
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', 'següent'}:
            raise ValueError('Unsupported pagination control')
    return docs, folders, action_url(more[0], base) if more else None


def project(title, url, docs):
    if not docs or 'NORM' not in title.upper():
        raise ValueError('Unsupported or empty planning instrument')
    return {
        'id': 'albuixech-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Albuixech', 'provincia': 'Valencia', 'codigo_ine': '46014',
        'titulo': title, 'tipo': 'planeamiento_urbanistico',
        'source': 'ayuntamiento', 'origen': 'sede_planeamiento_normas_subsidiarias',
        'url': url, 'source_inventory': SOURCE, 'documentos': sorted(docs.values(), key=lambda d: d['url']),
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'fase': None,
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'coverage': LIMITATIONS,
    }


class AlbuixechAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or f'https://{HOST}')
        self.source_urls = []
        self.captures = []

    def _fetch(self, session, url):
        response = session.get(url, timeout=40)
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Unexpected source redirect')
        self.source_urls.append(response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir) / f'live-{len(self.source_urls):03d}.html'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
            self.captures.append({'path': str(path), 'url': response.url,
                                  'sha256': hashlib.sha256(response.content).hexdigest()})
        return response.url, response.text

    def _inventory(self, session, url):
        canonical, html = self._fetch(session, url)
        docs, folders, more = entries(fragment(html), canonical)
        seen = set()
        for _ in range(100):
            if more is None:
                return canonical, docs, folders
            if more in seen:
                raise ValueError('Pagination loop')
            seen.add(more)
            page_url, html = self._fetch(session, more)
            new_docs, new_folders, more = entries(fragment(html), page_url)
            if not (set(new_docs) - set(docs)) and not new_folders:
                raise ValueError('Pagination made no progress')
            docs.update(new_docs)
            folders.extend(new_folders)
        raise ValueError('Pagination safety limit reached; no output written')

    def backfill_proyectos(self, out_jsonl):
        self.source_urls, self.captures = [], []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-albuixech/1.0'
            _, _, folders = self._inventory(session, SOURCE)
            selected = [f for f in folders if f[0].startswith('6.1.1. NORMES SUBSIDIÀRIES')]
            if len(selected) != 1:
                raise ValueError('NNSS inventory missing or ambiguous')
            _, total, action = selected[0]
            _, docs, instruments = self._inventory(session, action)
            if docs or not instruments:
                raise ValueError('Changed instrument grouping')
            rows = []
            for title, expected, action in instruments:
                canonical, docs, nested = self._inventory(session, action)
                if nested or len(docs) != expected:
                    raise ValueError(f'Incomplete document coverage for {title}: {len(docs)}/{expected}')
                rows.append(project(title, canonical, docs))
            if sum(len(r['documentos']) for r in rows) != total:
                raise ValueError('Parent inventory document count mismatch')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'documents': total,
                'source_urls': self.source_urls, 'captures': self.captures,
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
