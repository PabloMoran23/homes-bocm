"""Public municipal planning folder; Wicket navigation and complete document trees.

Only the reviewed PLANEAMIENTO URBANÍSTICO inventory is covered. Neither the
portal's clock nor a document title establishes an agreement/publication date.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://tosiria.sedelectronica.es/transparency/9ec75040-0b30-44e0-b159-f4477431ab0a/'
HOST = 'tosiria.sedelectronica.es'
COVERAGE = 'current_planeamiento_urbanistico_folder_only'


def official_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != HOST:
        raise ValueError('Unexpected source host: ' + url)
    return url


def action_url(element, page_url):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing Wicket navigation action')
    return official_url(urljoin(page_url, match[1]))


def parse_inventory(html, page_url):
    """Parse either a full folder or the assembled HTML of pagination components."""
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.select('tbody a.gIconLink')
    documents, folders = {}, []
    for a in links:
        title = a.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            count = re.search(r'\(\s*(\d+)\s*\)\s*$', title)
            if not count:
                raise ValueError('Folder lacks document count')
            folders.append({'titulo': title[:count.start()].strip(),
                            'count': int(count[1]), 'element': a})
        else:
            target = official_url(urljoin(page_url, a.get('href', '')))
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(target).path):
                raise ValueError('Unexpected document link')
            if not title:
                raise ValueError('Unnamed document')
            documents[target] = {'titulo': title, 'url': target, 'inventory_url': page_url}
    return list(documents.values()), folders


def apply_ajax(soup, xml):
    """Apply Wicket component replacements/appends without executing remote JS."""
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response':
        raise ValueError('Unexpected pagination response')
    components = root.findall('component')
    if not components:
        raise ValueError('Pagination returned no components')
    for component in components:
        fragment = BeautifulSoup(component.text or '', 'html.parser')
        node = fragment.find()
        if node is None:
            raise ValueError('Empty pagination component')
        old = soup.find(id=component.attrib['id'])
        if old is not None:
            old.replace_with(node)
        elif node.name == 'tr' and soup.select_one('tbody'):
            soup.select_one('tbody').append(node)
        else:
            raise ValueError('Unknown pagination component')
    return soup


def make_record(title, identity_url, documents):
    if not documents:
        raise ValueError('Instrument has no source documents')
    key = hashlib.sha256(identity_url.encode()).hexdigest()[:20]
    return {'id': 'torredonjimeno-plan-' + key, 'municipio': 'Torredonjimeno',
            'codigo_ine': '23087', 'provincia': 'Jaén', 'titulo': title,
            'tipo': 'planeamiento_urbanistico', 'url': identity_url,
            'inventory_url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_planeamiento', 'documentos': documents,
            'coverage': COVERAGE, 'publication_ready': False,
            'geometry_status': 'unavailable'}


class TorredonjimenoAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE = SOURCE

    def _get(self, session, url, **kwargs):
        official_url(url)
        response = session.get(url, timeout=40, allow_redirects=False, **kwargs)
        # Public AJAX redirects use Ajax-Location, not HTTP Location. Fail closed
        # on HTTP redirects so a host change never causes an unreviewed fetch.
        if response.status_code != 200:
            response.raise_for_status()
            raise ValueError('Unexpected HTTP status: ' + str(response.status_code))
        official_url(response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            name = f'{len(self.captures):04d}-' + hashlib.sha256(url.encode()).hexdigest() + '.gz'
            with gzip.open(path / name, 'wt', encoding='utf-8') as stream:
                stream.write(response.text)
            self.captures.append({'url': url, 'capture': name})
        return response

    def _action(self, session, element, page_url):
        return self._get(session, action_url(element, page_url),
                         headers={'Wicket-Ajax': 'true', 'Referer': page_url})

    def _folder(self, session, url, seen):
        if url in seen:
            raise ValueError('Folder cycle or duplicate instrument folder')
        seen.add(url)
        self.source_urls.append(url)
        response = self._get(session, url)
        soup = BeautifulSoup(response.text, 'html.parser')
        if not soup.select_one('tbody'):
            raise ValueError('Planning inventory table missing')
        actions = set()
        for _ in range(100):
            buttons = soup.select('.more_results button[onclick]')
            if not buttons:
                break
            if len(buttons) != 1:
                raise ValueError('Ambiguous pagination')
            action = action_url(buttons[0], url)
            # Wicket may reuse the callback URL while its server-side cursor
            # advances. Detect a repeated action AND unchanged inventory.
            signature = (action, tuple(str(a) for a in soup.select('tbody a.gIconLink')))
            if signature in actions:
                raise ValueError('Pagination did not advance')
            actions.add(signature)
            page = self._action(session, buttons[0], url)
            if page.headers.get('Ajax-Location'):
                raise ValueError('Pagination redirected unexpectedly')
            soup = apply_ajax(soup, page.text)
        else:
            raise ValueError('Pagination safety limit reached; no partial output')
        return parse_inventory(str(soup), url)

    def _open_folder(self, session, folder, parent_url):
        response = self._action(session, folder['element'], parent_url)
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Folder action lacks Ajax-Location')
        url = official_url(urljoin(parent_url, location))
        if not re.fullmatch(r'/transparency/[0-9a-f-]{36}/', urlparse(url).path):
            raise ValueError('Unexpected folder location')
        return url

    def _tree(self, session, url, seen):
        documents, folders = self._folder(session, url, seen)
        for folder in folders:
            child_url = self._open_folder(session, folder, url)
            children = self._tree(session, child_url, seen)
            if len(children) != folder['count']:
                raise ValueError('Folder document count mismatch: ' + folder['titulo'])
            documents.extend(children)
        if len({d['url'] for d in documents}) != len(documents):
            raise ValueError('Duplicate documents across folders')
        return documents

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls, self.captures = [], []
        seen = set()
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'})
            documents, folders = self._folder(session, self.SOURCE, seen)
            # Six documents sit directly in the parent folder. They form one
            # Avance, rather than six separate planning instruments.
            memories = [d for d in documents if d['titulo'].startswith('MEMORIA AVANCE DE PLANEAMIENTO')]
            if len(memories) != 1 or any(
                d not in memories and not re.match(r'^Asentamientos \d+\.', d['titulo'])
                for d in documents
            ):
                raise ValueError('Unreviewed grouping in planning inventory')
            records = [make_record(memories[0]['titulo'], memories[0]['url'], documents)]
            for folder in folders:
                if not folder['titulo'].startswith(('PLAN DE ', 'MODIFICACIÓN ', 'ESTUDIO DE ', 'PROYECTO DE ')):
                    raise ValueError('Unreviewed instrument folder: ' + folder['titulo'])
                url = self._open_folder(session, folder, self.SOURCE)
                children = self._tree(session, url, seen)
                if len(children) != folder['count']:
                    raise ValueError('Instrument document count mismatch')
                records.append(make_record(folder['titulo'], url, children))
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in records), encoding='utf-8')
        temp.replace(output)
        return {'count': len(records), 'written': len(records), 'coverage': COVERAGE,
                'documents': sum(len(r['documentos']) for r in records),
                'source_urls': self.source_urls, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Current inventory snapshot; no historical completeness claim or cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        raise NotImplementedError('Licencias disabled: no verified granted-licence register')

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
