"""Épila's public planning inventory; one record per instrument, not per PDF."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://epila.sedelectronica.es/transparency/7e75f398-8dca-4199-8066-3347c59dd4b2/'
HOST = 'epila.sedelectronica.es'


def official_url(base, target):
    url = urljoin(base, target)
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != HOST:
        raise ValueError('Unexpected off-site municipal navigation')
    return url


def parse_page(html):
    """Read every visible inventory row, refusing unhandled pagination."""
    soup = BeautifulSoup(html, 'html.parser')
    for node in soup.select('a, button, input, [class*="pagin"], [class*="navigator"]'):
        label = ' '.join([node.get_text(' ', strip=True), node.get('title', ''),
                          node.get('aria-label', ''), node.get('value', '')]).lower()
        if (node.get('rel') == ['next'] or re.search(r'\b(siguiente|next|mostrar más|última)\b', label)
                or any('pagin' in c.lower() or 'navigator' in c.lower() for c in node.get('class', []))):
            if not node.has_attr('disabled') and node.get('aria-disabled') != 'true':
                raise ValueError('Pagination detected: review crawler before accepting partial coverage')
    cells = soup.select('td.class_name')
    if not cells:
        raise ValueError('Planning inventory missing or empty')
    entries = []
    for cell in cells:
        a = cell.select_one('a.gIconLink, a.extUrl')
        if not a:
            raise ValueError('Unknown inventory row')
        label = a.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            count = re.search(r'\(\s*(\d+)\s*\)\s*$', label)
            callback = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
            if not count or not callback:
                raise ValueError('Folder lacks count or navigation callback')
            entries.append({'kind': 'folder', 'titulo': label[:count.start()].strip(),
                            'count': int(count[1]), 'callback': callback[1]})
        elif '/preview-document/' in a.get('href', ''):
            entries.append({'kind': 'document', 'titulo': label,
                            'descripcion': a.get('title', ''), 'url': a['href']})
        elif 'extUrl' in a.get('class', []):
            entries.append({'kind': 'external', 'titulo': label, 'url': a['href']})
        else:
            raise ValueError('Unknown inventory link')
    return entries


def make_record(title, url, documents):
    if not documents:
        raise ValueError('Instrument has no source documents')
    return {'id': 'epila-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'municipio': 'Épila', 'codigo_ine': '50099', 'provincia': 'Zaragoza',
            'titulo': title, 'tipo': 'planeamiento_urbanistico', 'url': url,
            'inventory_url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_planeamiento', 'documentos': documents,
            'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'Inventario documental parcial; no acredita aprobación ni vigencia.'}


class EpilaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, url, **kwargs):
        official_url(SOURCE, url)
        response = self.session.get(url, timeout=40, **kwargs)
        response.raise_for_status()
        official_url(SOURCE, response.url)
        self.source_urls.append(response.url)
        capture = self.config.get('source_capture_dir')
        if capture and response.content.strip():
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(response.url.encode()).hexdigest()[:16] + '.html'
            (directory / name).write_bytes(response.content)
        return response

    def _folder_url(self, page_url, entry):
        response = self._get(official_url(page_url, entry['callback']),
                             headers={'Wicket-Ajax': 'true', 'Referer': page_url})
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Municipal folder no longer supplies an Ajax-Location')
        target = official_url(response.url, location)
        if not urlparse(target).path.startswith('/transparency/'):
            raise ValueError('Unexpected folder target')
        return target

    def _documents(self, url, visited):
        if url in visited:
            raise ValueError('Cyclic or duplicate planning folder')
        visited.add(url)
        docs = []
        count = 0
        for entry in parse_page(self._get(url).text):
            if entry['kind'] == 'folder':
                child = self._folder_url(url, entry)
                nested, size = self._documents(child, visited)
                if size != entry['count']:
                    raise ValueError('Folder count mismatch: possible truncated inventory')
                docs.extend(nested)
                count += size
            else:
                count += 1
                if entry['kind'] == 'document':
                    docs.append(self._document(entry, url))
                else:
                    raise ValueError('Unreviewed external link inside an instrument')
        return docs, count

    @staticmethod
    def _document(entry, page_url):
        return {'titulo': entry['titulo'], 'descripcion': entry['descripcion'],
                'url': official_url(page_url, entry['url']), 'source_page': page_url}

    def backfill_proyectos(self, out_jsonl):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'municipio-epila/1.0 (public planning inventory)'
        self.source_urls = []
        try:
            rows = []
            visited = {SOURCE}
            for entry in parse_page(self._get(SOURCE).text):
                title = entry['titulo']
                if entry['kind'] == 'external':
                    # Regional archive directory is a cross-reference, not an instrument.
                    if (urlparse(entry['url']).hostname != 'idearagon.aragon.es'
                            or 'CMUNIINE=50099' not in entry['url']):
                        raise ValueError('Unreviewed external inventory entry')
                    continue
                if entry['kind'] == 'folder':
                    if not re.search(r'PLAN PARCIAL|MODIFICACI[ÓO]N.*NNSS', title, re.I):
                        raise ValueError('Unreviewed planning folder')
                    url = self._folder_url(SOURCE, entry)
                    documents, count = self._documents(url, visited)
                    if count != entry['count']:
                        raise ValueError('Folder count mismatch: possible pagination')
                else:
                    if not re.search(r'Normas subsidiarias de planeamiento|normas del SAUR', title, re.I):
                        raise ValueError('Unreviewed standalone planning document')
                    documents = [self._document(entry, SOURCE)]
                    url = documents[0]['url']
                row = make_record(title, url, documents)
                # Only the unambiguous BOP publication date; never an agreement date.
                match = re.search(r'BOP Z \d+ (\d{4})\.(\d{2})\.(\d{2})', title)
                if match:
                    from datetime import date
                    row['fecha_publicacion'] = date(*map(int, match.groups())).isoformat()
                rows.append(row)
            if not rows:
                raise ValueError('No documented planning instruments')
            if len({row['id'] for row in rows}) != len(rows):
                raise ValueError('Duplicate instruments')
            self._write(out_jsonl, rows)
            return {'count': len(rows), 'document_count': sum(len(r['documentos']) for r in rows),
                    'source_urls': list(dict.fromkeys(self.source_urls)),
                    'coverage': 'current_planning_document_inventory', 'publication_ready': False}
        finally:
            self.session.close()

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
