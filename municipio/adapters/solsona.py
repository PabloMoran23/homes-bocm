"""Snapshot of Solsona's public-exposure physical works inventory, not licences."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.ajsolsona.cat/ajuntament/projectes-en-exposicio-publica'


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


def _local(url):
    parts = urlsplit(url)
    return (parts.scheme == 'https' and parts.netloc == 'www.ajsolsona.cat'
            and (parts.path == urlsplit(SOURCE).path
                 or parts.path.startswith(urlsplit(SOURCE).path + '/')))


def _canonical(url):
    return url.split('#')[0].split('?')[0].removesuffix('/view').rstrip('/')


class SolsonaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.ajsolsona.cat')
        self.source_urls = []

    @staticmethod
    def parse_inventory(html, page_url=SOURCE):
        soup = BeautifulSoup(html, 'html.parser')
        core = soup.select_one('#content-core')
        if core is None:
            raise ValueError('Missing municipal inventory content')
        entries = {}
        for link in core.select('article.tileItem .tileHeadline a[href]'):
            title = link.get_text(' ', strip=True)
            normalized = _norm(title)
            # Only concrete physical works, never a form, tender or generic news.
            if not re.match(r'^projecte (?:de |d[’\'])', normalized):
                continue
            if not any(word in normalized for word in
                       ('rehabilitacio', 'urbanitzacio', 'reforma', 'construccio',
                        'arranjament', 'millora', 'reparacio')):
                continue
            if any(word in normalized for word in ('licitacio', 'sol·licitud', 'formulari')):
                continue
            url = urljoin(page_url, link['href'])
            if not _local(url):
                raise ValueError('Project link leaves reviewed municipal inventory')
            entries[_canonical(url)] = {'titulo': title, 'url': _canonical(url),
                                        'detail_url': url}
        pages = set()
        for link in soup.select('.listingBar a[href], .batching a[href], '
                                '.pagination a[href], a[rel~=next], a.next[href]'):
            url = urljoin(page_url, link['href']).split('#')[0]
            if not _local(url):
                raise ValueError('Pagination leaves reviewed municipal inventory')
            if url != page_url:
                pages.add(url)
        return list(entries.values()), sorted(pages)

    @staticmethod
    def parse_detail(html, entry):
        soup = BeautifulSoup(html, 'html.parser')
        core = soup.select_one('#content-core')
        heading = soup.select_one('h1.documentFirstHeading')
        if core is None or heading is None or heading.get_text(' ', strip=True) != entry['titulo']:
            raise ValueError('Project detail title/content changed')
        documents = {}
        for link in core.select('a[href]'):
            url = urljoin(entry['url'] + '/', link['href'])
            if not _local(url):
                continue
            if '/at_download/file' in url or urlsplit(url).path.lower().endswith('.pdf'):
                documents[url] = {'titulo': link.get_text(' ', strip=True), 'url': url,
                                  'source_url': entry['detail_url']}
        if not documents:
            raise ValueError('Project lacks linked technical documents')
        return {
            'id': 'solsona-proy-' + hashlib.sha256(entry['url'].encode()).hexdigest()[:16],
            'municipio': 'Solsona', 'provincia': 'Lleida', 'codigo_ine': '25207',
            'titulo': entry['titulo'], 'tipo': 'proyecto_obra_publica',
            'fase': 'exposición pública', 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': entry['url'], 'url_documento': next(iter(documents)),
            'documentos': list(documents.values()), 'source': 'ayuntamiento',
            'origen': 'inventario_exposicion_publica', 'source_url': SOURCE,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'unavailable',
            'coverage': 'Current physical works inventory only; not a historical register. '
                        'Exposure listing does not establish approval or execution.',
        }

    def _fetch(self, url):
        if not _local(url):
            raise ValueError('Unreviewed source URL')
        response = requests.get(url, timeout=40, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-solsona/1.0')})
        response.raise_for_status()
        if not _local(response.url):
            raise ValueError('Source redirected outside inventory')
        if len(response.content) > 4_000_000:
            raise ValueError('HTML source exceeds reviewed size')
        self.source_urls.append(url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                        encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        pending, visited, entries = [SOURCE], set(), {}
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Pagination exceeds safety bound; no partial output written')
            found, pages = self.parse_inventory(self._fetch(url), url)
            visited.add(url)
            entries.update((entry['url'], entry) for entry in found)
            pending.extend(page for page in pages if page not in visited)
        if not entries:
            raise ValueError('No usable physical projects; inventory needs review')
        rows = [self.parse_detail(self._fetch(entry['detail_url']), entry)
                for entry in entries.values()]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'inventory_pages': len(visited), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
