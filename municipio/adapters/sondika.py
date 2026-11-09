"""Sondika's public technical-project inventory and complete SharePoint libraries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.sondika.eus'
WEB = BASE + '/es-ES/Ayuntamiento/Normas-Subsidiarias'
SOURCE = WEB + '/Paginas/proyectos.aspx'
LIBRARIES = WEB + '/_api/web/lists?$select=Id,Title,RootFolder/ServerRelativeUrl&$expand=RootFolder'


def official(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'www.sondika.eus':
        raise ValueError('Unexpected source URL: ' + url)
    return url


class SondikaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, as_json=False):
        official(url)
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-sondika/1.0',
            'Accept': 'application/json;odata=verbose' if as_json else 'text/html',
        })
        response.raise_for_status()
        official(response.url)
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest() + ('.json' if as_json else '.html')
            (directory / name).write_bytes(response.content)
        self.source_urls.append(url)
        return response.json() if as_json else response.text

    def _items(self, url):
        seen = set()
        rows = []
        while url:
            official(url)
            if url in seen:
                raise ValueError('SharePoint pagination cycle')
            seen.add(url)
            data = self._fetch(url, as_json=True)['d']
            if not isinstance(data.get('results'), list):
                raise ValueError('Unexpected SharePoint inventory schema')
            rows.extend(data['results'])
            url = urljoin(url, data['__next']) if data.get('__next') else None
        return rows

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('.main-content-right')
        if content is None:
            raise ValueError('Missing municipal project inventory')
        # This is a static summary-link inventory, not a search-results page.
        # A changed/paginated layout must be reviewed before accepting a snapshot.
        if content.select('[class*="pager"], [class*="Pager"], [rel="next"]'):
            raise ValueError('Unexpected HTML pagination')
        projects = {}
        for a in content.select('.link-item a[href]'):
            title = a.get_text(' ', strip=True)
            url = official(urljoin(SOURCE, a['href']).split('#')[0])
            if not url.startswith(WEB + '/Paginas/') or not title:
                raise ValueError('Unexpected project inventory entry')
            projects[url] = title
        if not projects:
            raise ValueError('Empty project inventory; review source')
        return projects

    @staticmethod
    def document_libraries(html, page_url, libraries):
        soup = BeautifulSoup(html, 'html.parser')
        folders = set()
        for a in soup.select('.main-content-right .CSPFileName a[href]'):
            url = official(urljoin(page_url, a['href']))
            path = unquote(urlparse(url).path)
            matches = [x for x in libraries if path.startswith(x['RootFolder']['ServerRelativeUrl'] + '/')]
            if len(matches) != 1:
                raise ValueError('Document has no unambiguous public library')
            folders.add(matches[0]['Id'])
        if not folders:
            raise ValueError('Project lacks technical document library: ' + page_url)
        return sorted(folders)

    @staticmethod
    def parse_documents(items, page_url):
        documents = {}
        for item in items:
            if item['FSObjType'] == 1:
                continue  # Items query includes descendant files as well as folders.
            path = item['FileRef']
            if not path.startswith('/es-ES/Ayuntamiento/Normas-Subsidiarias/'):
                raise ValueError('Unexpected document path')
            url = official(urljoin(BASE, path))
            documents[url] = {'titulo': item.get('Title') or item['FileLeafRef'],
                              'url': url, 'source_url': page_url}
        if not documents:
            raise ValueError('Empty technical document library')
        return sorted(documents.values(), key=lambda x: x['url'])

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        projects = self.parse_inventory(self._fetch(SOURCE))
        libraries = self._items(LIBRARIES)
        rows = []
        for url, title in projects.items():
            ids = self.document_libraries(self._fetch(url), url, libraries)
            docs = []
            for library_id in ids:
                endpoint = (WEB + "/_api/web/lists(guid'" + library_id
                            + "')/items?$select=Title,FileRef,FileLeafRef,FSObjType&$top=100")
                docs.extend(self.parse_documents(self._items(endpoint), url))
            rows.append({
                'id': 'sondika-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                'municipio': 'Sondika', 'codigo_ine': '48904', 'provincia': 'Bizkaia',
                'titulo': title, 'tipo': 'proyecto_obra', 'url': url,
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_proyectos',
                'source_url': SOURCE, 'documentos': docs,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None,
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'coverage': 'Inventario municipal Proyectos; sin historial de acuerdos ni licencias',
            })
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': self.source_urls, 'documents': sum(len(r['documentos']) for r in rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
