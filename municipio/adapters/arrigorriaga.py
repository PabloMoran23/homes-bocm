"""Four infrastructure planning instruments in the official departmental inventory.

The public file API supplies documents, not granted licences or approval dates.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.arrigorriaga.eus'
SOURCE = BASE + '/es/departamentos/barrios-urbanismo-y-vivienda'
PLANS = {
    'Plan Director de Equipamientos Públicos Municipales': 'equipamientos',
    'Plan de Accesibilidad': 'accesibilidad',
    'Plan de Movilidad Sostenible': 'movilidad',
    'Plan de Acción del Paisaje de Arrigorriaga': 'paisaje',
}


def official_url(value, base=SOURCE):
    url = urljoin(base, value)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'www.arrigorriaga.eus':
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def parse_inventory(html):
    """Bind each reviewed heading to its own accordion, never the whole page."""
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('a[rel~=next], .pagination a[href]'):
        raise ValueError('Inventory pagination appeared; review required')
    plans = []
    seen = set()
    for button in soup.select('button[aria-controls]'):
        title = button.get_text(' ', strip=True)
        if title not in PLANS:
            continue
        key = PLANS[title]
        if key in seen:
            raise ValueError('Duplicate planning section')
        seen.add(key)
        panel = soup.find(id=button['aria-controls'])
        if panel is None:
            raise ValueError('Missing plan panel')
        folders = []
        for script in panel.select('script.file-list-widget-config'):
            config = json.loads(script.get_text())
            api = official_url(config['base_url'])
            if urlparse(api).path != '/api/v1/':
                raise ValueError('Changed file API')
            if config.get('category_id') is not None:
                raise ValueError('Category filtering needs review')
            folder = config['folder_id']
            if type(folder) is not int or folder <= 0:
                raise ValueError('Invalid folder ID')
            folders.append((api, folder))
        docs = {}
        for anchor in panel.select('a[href]'):
            url = official_url(anchor['href'])
            if urlparse(url).path.lower().endswith('.pdf'):
                docs[url] = {'titulo': anchor.get_text(' ', strip=True), 'url': url,
                             'source_url': SOURCE}
        if not folders and not docs:
            raise ValueError(f'No documents for {title}')
        plans.append({'key': key, 'title': title, 'url': SOURCE + '#' + panel['id'], 'folders': folders,
                      'documents': list(docs.values())})
    if seen != set(PLANS.values()):
        raise ValueError('Reviewed planning inventory is incomplete or changed')
    return plans


def parse_file_page(payload):
    """DataTables counts distinguish an empty folder from a truncated response."""
    data = payload.get('data')
    total = payload.get('recordsFiltered')
    if not isinstance(data, list) or type(total) is not int or total < 0:
        raise ValueError('Invalid DataTables page')
    if payload.get('recordsTotal') != total:
        raise ValueError('Unexpected filtering in file inventory')
    if len(data) > total:
        raise ValueError('File count mismatch')
    return data, total


class ArrigorriagaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, url, as_json=False):
        url = official_url(url)
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-arrigorriaga/1.0', 'Accept-Language': 'es'})
        response.raise_for_status()
        official_url(response.url)
        capture = self.config.get('capture_dir')
        if capture:
            import hashlib
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20]
            (path / (name + ('.json' if as_json else '.html'))).write_bytes(response.content)
        return response.json() if as_json else response.text

    def _files(self, api, folder, expected):
        start = 0
        total = None
        docs = {}
        while True:
            url = api + 'file/?' + urlencode({
                'format': 'datatables', 'folder': folder, 'start': start, 'length': 100})
            page, count = parse_file_page(self._get(url, as_json=True))
            if count != expected or (total is not None and count != total):
                raise ValueError('Folder/file totals changed or disagree')
            total = count
            if not page and start < total:
                raise ValueError('Truncated file inventory')
            for item in page:
                target = official_url(item['url'])
                if item.get('extension', '').lower() != 'pdf' or not urlparse(target).path.lower().endswith('.pdf'):
                    raise ValueError('Unexpected non-PDF planning attachment')
                if target in docs:
                    raise ValueError('Repeated files; pagination did not advance')
                docs[target] = {
                    'titulo': item.get('description') or item['name'],
                    'nombre_archivo': item['name'], 'url': target,
                    'source_url': url, 'folder_id': folder,
                    # Explicitly a CMS timestamp, never an instrument/agreement date.
                    'cms_created_at': item.get('created_at'),
                }
            start += len(page)
            if start > total:
                raise ValueError('Pagination exceeded declared total')
            if start == total:
                return list(docs.values())

    def _folder_documents(self, api, folder):
        url = api + f'folder/{folder}/recursive/'
        tree = self._get(url, as_json=True)
        seen = set()
        docs = []

        def walk(node, expected_id=None):
            fid = node.get('id')
            count = node.get('files')
            children = node.get('children')
            if (type(fid) is not int or fid <= 0 or fid in seen
                    or type(count) is not int or count < 0 or not isinstance(children, list)
                    or (expected_id is not None and fid != expected_id)):
                raise ValueError('Invalid or repeated folder in recursive inventory')
            seen.add(fid)
            files = self._files(api, fid, count)
            for document in files:
                document['folder_name'] = node.get('name')
                document['folder_inventory_url'] = url
            docs.extend(files)
            for child in children:
                walk(child)

        walk(tree, folder)
        return docs

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                     for row in rows), encoding='utf-8')
        temporary.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        plans = parse_inventory(self._get(SOURCE))
        rows = []
        for plan in plans:
            documents = {doc['url']: doc for doc in plan['documents']}
            for api, folder in plan['folders']:
                for doc in self._folder_documents(api, folder):
                    documents.setdefault(doc['url'], doc)
            if not documents:
                raise ValueError('Empty planning instrument')
            row = {
                'id': 'arrigorriaga-plan-' + plan['key'],
                'municipio': 'Arrigorriaga', 'codigo_ine': '48011', 'provincia': 'Bizkaia',
                'titulo': plan['title'], 'tipo': 'planificacion_infraestructuras',
                'url': plan['url'], 'inventory_url': SOURCE,
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_planes',
                'source_entity_type': 'documento',
                'documentos': list(documents.values()),
                'publication_ready': False, 'geometry_status': 'unavailable',
                'alcance': 'Documentación publicada; sin acuerdo ni ejecución verificados.',
            }
            if plan['key'] == 'paisaje':
                row['alcance'] = 'Documento de diagnóstico del plan de paisaje; no acredita aprobación ni ejecución.'
            rows.append(row)
        return {**self._write(out_jsonl, rows),
                'coverage': 'four_departmental_infrastructure_plans', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # A full snapshot is required: CMS timestamps are not legal event dates.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
