"""Municipal planning inventory: one instrument per folder, all linked documents."""
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

HOST = 'https://sanmigueldesalinas.sedelectronica.es'
SOURCE = HOST + '/transparency/8d019610-1215-41b6-9d8c-a415d1cbc368/'
FOLDER_PATH = re.compile(r'/transparency/[0-9a-f-]{36}/$')
DOCUMENT_PATH = re.compile(r'/preview-document/[0-9a-f-]{36}$')
INSTRUMENT = re.compile(
    r'^1\.\d+\.?\s+(?:NORMAS SUBSIDIARIAS|MODIFICACIÓN PUNTUAL|PLAN PARCIAL|'
    r'PLAN ESPECIAL|CATÁLOGO DE BIENES)\b', re.I
)


def official_url(url, pattern):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.netloc != urlparse(HOST).netloc
            or parsed.query or parsed.fragment or not pattern.fullmatch(parsed.path)):
        raise ValueError(f'Unexpected official source URL: {url}')
    return url


def callback_url(element, page_url):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing Wicket navigation callback')
    target = urljoin(page_url, match[1])
    if urlparse(target).netloc != urlparse(HOST).netloc:
        raise ValueError('External navigation callback')
    return target


def parse_entries(soup, page_url):
    table = soup.select_one('table.TransparencyListPanel')
    if table is None:
        raise ValueError('Planning inventory table missing')
    entries = []
    for anchor in table.select('a.gIconLink'):
        label = ' '.join(anchor.stripped_strings)
        if 'exp' in anchor.get('class', []):
            count = anchor.select_one('.linkExtraInfo')
            match = re.fullmatch(r'\s*\(\s*(\d+)\s*\)\s*', count.get_text() if count else '')
            if not match:
                raise ValueError('Folder document count missing')
            title = label[:label.rfind('(')].strip()
            entries.append({'kind': 'folder', 'title': title, 'count': int(match[1]),
                            'callback': callback_url(anchor, page_url)})
        else:
            target = official_url(urljoin(page_url, anchor.get('href', '')), DOCUMENT_PATH)
            if not label:
                raise ValueError('Document title missing')
            entries.append({'kind': 'document', 'title': label, 'url': target,
                            'inventory_url': page_url})
    if not entries:
        raise ValueError('Empty planning inventory')
    return entries


def apply_more(soup, xml):
    """Apply only HTML components; never evaluate website JavaScript."""
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response':
        raise ValueError('Unexpected pagination response')
    components = root.findall('component')
    if not components:
        raise ValueError('Pagination returned no components')
    for component in components:
        fragment = BeautifulSoup(component.text or '', 'html.parser')
        tag = fragment.find()
        if tag is None or tag.get('id') != component.get('id'):
            raise ValueError('Unrecognized pagination component')
        old = soup.find(id=component.get('id'))
        if old is not None:
            old.replace_with(tag)
        elif tag.name == 'tr':
            soup.select_one('table.TransparencyListPanel tbody').append(tag)
        else:
            raise ValueError('Unknown pagination insertion')


class SanMiguelDeSalinasAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='san-miguel-de-salinas', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'municipio-planning-inventory/1.0'
        self.source_urls = set()
        self.captures = []

    def _get(self, url, **kwargs):
        response = self.session.get(url, timeout=40, **kwargs)
        response.raise_for_status()
        if urlparse(response.url).netloc != urlparse(HOST).netloc:
            raise ValueError('Unexpected source redirect')
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = f'capture-{len(self.captures):03d}.txt'
            (directory / name).write_text(response.text, encoding='utf-8')
            # Do not persist session cookies or temporary callback tokens in metadata.
            self.captures.append({'file': name, 'page': response.url.split('?')[0],
                                  'ajax_location': response.headers.get('Ajax-Location')})
        return response

    def _folder_url(self, entry, parent):
        response = self._get(entry['callback'], headers={'Wicket-Ajax': 'true',
                             'Accept': 'text/xml', 'Referer': parent})
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Folder callback returned no Ajax-Location')
        return official_url(urljoin(parent, location), FOLDER_PATH)

    def _listing(self, url):
        official_url(url, FOLDER_PATH)
        self.source_urls.add(url)
        soup = BeautifulSoup(self._get(url).text, 'html.parser')
        seen = set()
        # Exhaust Mostrar más, failing rather than returning a truncated snapshot.
        for _ in range(100):
            more = soup.select_one('.more_results button[onclick]')
            if more is None:
                return parse_entries(soup, url)
            callback = callback_url(more, url)
            fingerprint = str(soup.select_one('table.TransparencyListPanel'))
            if fingerprint in seen:
                raise ValueError('Pagination did not advance')
            seen.add(fingerprint)
            response = self._get(callback, headers={'Wicket-Ajax': 'true',
                                 'Accept': 'text/xml', 'Referer': url})
            if response.headers.get('Ajax-Location'):
                raise ValueError('Pagination unexpectedly navigated away')
            apply_more(soup, response.text)
        raise ValueError('Pagination limit exceeded; no partial output written')

    def _documents(self, url, ancestors):
        if url in ancestors or len(ancestors) > 12:
            raise ValueError('Folder cycle/depth exceeded')
        documents = []
        for entry in self._listing(url):
            if entry['kind'] == 'document':
                documents.append({k: v for k, v in entry.items() if k != 'kind'})
            else:
                child = self._folder_url(entry, url)
                nested = self._documents(child, ancestors | {url})
                if len(nested) != entry['count']:
                    raise ValueError(f'Document count mismatch: {entry["title"]}')
                documents.extend(nested)
        if len({d['url'] for d in documents}) != len(documents):
            raise ValueError('Duplicate documents within an instrument')
        return documents

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls.clear()
        rows = []
        entries = self._listing(SOURCE)
        for entry in entries:
            if entry['kind'] != 'folder' or not INSTRUMENT.match(entry['title']):
                raise ValueError('Unrecognized instrument in selected planning inventory')
            url = self._folder_url(entry, SOURCE)
            documents = self._documents(url, {SOURCE})
            if not documents or len(documents) != entry['count']:
                raise ValueError(f'Instrument document count mismatch: {entry["title"]}')
            rows.append({
                'id': 'san-miguel-de-salinas-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                'municipio': 'San Miguel de Salinas', 'codigo_ine': '03120',
                'provincia': 'Alicante', 'titulo': entry['title'],
                'tipo': 'instrumento de planeamiento', 'url': url,
                'inventory_url': SOURCE, 'documentos': documents,
                'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
                'publication_ready': False, 'geometry_status': 'unavailable',
            })
        if len({row['url'] for row in rows}) != len(rows):
            raise ValueError('Duplicate instruments')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows),
                'documents': sum(len(r['documentos']) for r in rows),
                'coverage': 'current_inventory_section_1.1', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
