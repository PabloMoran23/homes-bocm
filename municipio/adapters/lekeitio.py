"""Municipal public-works inventory, reconciled against its document library."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.lekeitio.com'
WEB = '/es-ES/Servicios/urbanismoobrasyservicios'
SOURCE = BASE + WEB + '/Paginas/udal-proiektuak.aspx'
LIBRARY = WEB + '/udalproiektuak'
API = BASE + WEB + "/_api/web/GetFolderByServerRelativeUrl('" + LIBRARY + "')"


def canonical(url, base=SOURCE):
    url = urljoin(base, url)
    parts = urlparse(url)
    if parts.scheme != 'https' or parts.netloc != 'www.lekeitio.com':
        raise ValueError('Unexpected non-municipal source URL')
    return parts._replace(fragment='').geturl()


class LekeitioAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        zone = soup.select_one('#ProcedureZone')
        if zone is None:
            raise ValueError('Missing municipal project inventory')
        for a in zone.select('a[href]'):
            label = a.get_text(' ', strip=True).lower()
            if (label in {'siguiente', 'next', 'hurrengoa', '>', '»'}
                    or 'paged=' in a['href'].lower()
                    or a.get('rel') == ['next']):
                raise ValueError('HTML pagination requires review; refusing partial inventory')
        records = {}
        for header in zone.select('.ms-WPHeader'):
            title_node = header.select_one('h3')
            body = header.find_next_sibling('div', class_='ms-WPBody')
            if title_node is None or body is None:
                continue
            title = title_node.get_text(' ', strip=True)
            if not title.lower().startswith('proyecto de '):
                raise ValueError('Unreviewed inventory section: ' + title)
            documents = {}
            for a in body.select('a[href]'):
                url = canonical(a['href'])
                if not unquote(urlparse(url).path).startswith(LIBRARY + '/'):
                    raise ValueError('Project document outside reviewed library')
                if not urlparse(url).path.lower().endswith(('.pdf', '.zip')):
                    raise ValueError('Unreviewed project document format')
                documents[url] = {'titulo': a.get_text(' ', strip=True), 'url': url,
                                  'source_url': SOURCE}
            if not documents:
                raise ValueError('Project lacks technical documents')
            key = 'lekeitio-proy-' + hashlib.sha256(title.casefold().encode()).hexdigest()[:16]
            if key in records:
                # Repeated webparts for the same instrument retain all attachments.
                documents.update({d['url']: d for d in records[key]['documentos']})
            records[key] = {
                'id': key, 'municipio': 'Lekeitio', 'codigo_ine': '48057',
                'provincia': 'Bizkaia', 'titulo': title, 'tipo': 'proyecto_urbanizacion',
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'proyectos_municipales',
                'documentos': list(documents.values()),
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'cobertura': 'Inventario municipal Proyectos Municipales; cobertura parcial del municipio',
            }
        if not records:
            raise ValueError('No verifiable municipal works; review source')
        return list(records.values())

    def _get(self, url):
        url = canonical(url)
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-lekeitio/1.0',
            'Accept': 'application/json;odata=verbose' if '/_api/' in url else 'text/html',
        })
        response.raise_for_status()
        canonical(response.url)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            suffix = '.json' if '/_api/' in url else '.html'
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + suffix
            (directory / name).write_bytes(response.content)
        return response

    def _collection(self, url):
        seen = set()
        while url:
            url = canonical(url)
            if url in seen:
                raise ValueError('Repeated SharePoint pagination URL')
            seen.add(url)
            data = self._get(url).json()['d']
            if not isinstance(data.get('results'), list):
                raise ValueError('Unexpected document-library response')
            yield from data['results']
            url = urljoin(url, data['__next']) if data.get('__next') else None

    def backfill_proyectos(self, out_jsonl):
        rows = self.parse_projects(self._get(SOURCE).text)
        files = list(self._collection(API + '/Files'))
        folders = list(self._collection(API + '/Folders'))
        if any(folder['Name'] != 'Forms' for folder in folders):
            raise ValueError('New document subfolders require grouping review')
        inventory = {canonical(f['ServerRelativeUrl']): f for f in files}
        linked = {d['url'] for row in rows for d in row['documentos']}
        if set(inventory) != linked:
            raise ValueError('Page/library mismatch; refusing silently truncated inventory')
        for row in rows:
            for doc in row['documentos']:
                file = inventory[doc['url']]
                doc.update({'library_url': API + '/Files', 'archivo_id': file['UniqueId'],
                            'archivo_bytes': int(file['Length']),
                            'archivo_creado': file.get('TimeCreated'),
                            'archivo_modificado': file.get('TimeLastModified')})
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [SOURCE, API + '/Files', API + '/Folders']}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
