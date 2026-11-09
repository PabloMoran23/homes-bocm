"""Latest reviewed annual municipal works inventory (2024), not licence grants."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.almacelles.cat'
INVENTORY = BASE + '/ajuntament/projectes-municipals'
LIMITATIONS = [
    'Partial coverage: only the reviewed 2024 annual municipal-project inventory; older archives and public-exposure inventory excluded.',
    'Municipal listing and linked Drive PDF viewer metadata only; PDF contents, execution and approval status not verified.',
    'No publication/agreement/approval dates or project geometry verified; archive year and filename dates are not approval dates.',
    'No granted-licence register extracted; scheduling and coordinate jitter disabled.',
]


def municipal_url(url):
    return urlparse(url).scheme == 'https' and urlparse(url).netloc == 'www.almacelles.cat'


class AlmacellesAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html, source_url):
        soup = BeautifulSoup(html, 'html.parser')
        core = soup.select_one('#content-core')
        if core is None or core.select_one('.entries') is None:
            raise ValueError('Missing municipal inventory markup')
        entries = {}
        for a in core.select('article.entry .summary a[href]'):
            url = urljoin(source_url, a['href'])
            if not municipal_url(url) or not url.startswith(INVENTORY + '/'):
                raise ValueError('Unexpected inventory destination')
            title = a.get_text(' ', strip=True)
            if not title:
                raise ValueError('Untitled inventory entry')
            if url in entries and entries[url] != title:
                raise ValueError('Conflicting titles for one instrument')
            entries[url] = title
        next_urls = set()
        for a in soup.select('a[href]'):
            rel = a.get('rel', [])
            if ('next' in rel or a.find_parent(class_='next') is not None
                    or a.get_text(' ', strip=True).lower() in {'següent', 'siguiente', 'next', '»', '›'}):
                url = urljoin(source_url, a['href'])
                if not municipal_url(url) or urlparse(url).path != urlparse(source_url).path:
                    raise ValueError('Unexpected pagination destination')
                next_urls.add(url)
        return entries, sorted(next_urls)

    @staticmethod
    def parse_document(html, document_url):
        if not re.fullmatch(r'https://drive\.google\.com/file/d/[\w-]+/view(?:\?.*)?', document_url):
            raise ValueError('Unexpected document destination; review municipal link')
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.select_one('meta[property="og:title"]')
        name = title.get('content', '').strip() if title else ''
        if not name.lower().endswith('.pdf'):
            raise ValueError('Linked viewer does not expose PDF metadata')
        return {'titulo': name, 'url': document_url, 'formato': 'pdf',
                'provenance': 'Destino del enlace publicado por el Ayuntamiento; metadatos del visor público'}

    def _fetch(self, url):
        # Only public municipal pages and their reviewed document viewers.
        self._sources.add(url)
        with requests.Session() as session:
            session.trust_env = False
            for _ in range(6):
                if not (municipal_url(url) or re.fullmatch(r'https://drive\.google\.com/file/d/[\w-]+/view(?:\?.*)?', url)):
                    raise ValueError('Unreviewed redirect destination')
                response = session.get(url, timeout=40, allow_redirects=False,
                                       headers={'User-Agent': 'municipio-almacelles/1.0'}, stream=True)
                if response.is_redirect:
                    url = urljoin(url, response.headers['Location'])
                    response.close()
                    continue
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > 5_000_000:
                        raise ValueError('Source exceeds response size limit')
                html = body.decode('utf-8')
                capture_dir = self.config.get('evidence_dir')
                if capture_dir:
                    folder = Path(capture_dir)
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / (hashlib.sha256(url.encode()).hexdigest()[:20] + '.html')).write_text(html, encoding='utf-8')
                self._sources.add(url)
                return html, url
        raise ValueError('Too many source redirects')

    def _inventory(self, start):
        pending, seen, entries = [start], set(), {}
        while pending:
            url = pending.pop(0)
            if url in seen:
                raise ValueError('Repeated/cyclic pagination URL')
            seen.add(url)
            html, final = self._fetch(url)
            if final != url:
                raise ValueError('Inventory unexpectedly redirected')
            page, next_urls = self.parse_inventory(html, url)
            for key, title in page.items():
                if key in entries and entries[key] != title:
                    raise ValueError('Conflicting paginated entry')
                entries[key] = title
            pending.extend(n for n in next_urls if n not in pending)
        return entries

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self._sources = {INVENTORY}
        years = {}
        for url, title in self._inventory(INVENTORY).items():
            match = re.fullmatch(r'(?:Projectes\s+)?(20\d{2})', title)
            if match:
                years[int(match[1])] = url
        if not years or max(years) != 2024:
            raise ValueError('Latest project archive changed; review coverage before extraction')
        archive = years[2024]
        rows = {}
        for url, title in self._inventory(archive).items():
            if not (re.match(r'^Projecte\b', title, re.I) and re.search(r'arranjament|substitució', title, re.I)):
                raise ValueError('Unreviewed entry in 2024 works archive')
            html, document_url = self._fetch(url)
            document = self.parse_document(html, document_url)
            document['url_origen'] = url
            # One document identity = one instrument, even if linked twice.
            key = urlparse(document_url).path
            if key in rows:
                rows[key]['enlaces_municipales'].append({'titulo': title, 'url': url})
                continue
            rows[key] = {
                'id': 'almacelles-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Almacelles', 'provincia': 'Lleida', 'codigo_ine': '25019',
                'titulo': title, 'tipo': 'proyecto_obra_publica', 'source_entity_type': 'documento', 'fase': None,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'anio_archivo': 2024, 'url': url, 'url_documento': document_url,
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_proyectos',
                'source_inventory': archive, 'documentos': [document],
                'enlaces_municipales': [{'titulo': title, 'url': url}],
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'limitaciones': LIMITATIONS,
            }
        if not rows:
            raise ValueError('No real projects found in reviewed archive')
        self._write(out_jsonl, list(rows.values()))
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(self._sources),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence source'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
