"""Albatera's official planning inventory; one record per documented instrument."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'albatera.sedelectronica.es'
SOURCE = f'https://{HOST}/transparency/350eaa4d-01c2-4fa7-9ce4-d6961986f094/'
LIMITATIONS = [
    'Partial municipal coverage: only transparency section 7.1, not all public works or licences.',
    'Document inventory does not establish current legal validity, approval or agreement dates.',
    'Empty instrument folders excluded; shared consolidated document linked to modifications 1 and 2.',
    'No document-body extraction or verified geometry; preview links retained with original labels.',
]


def parse_page(text):
    """Parse full HTML or Wicket CDATA components without executing scripts."""
    if text.lstrip().startswith('<?xml'):
        root = ElementTree.fromstring(text)
        if root.tag != 'ajax-response':
            raise ValueError('Unexpected Wicket response')
        text = '\n'.join(c.text or '' for c in root.findall('component'))
    soup = BeautifulSoup(text, 'html.parser')
    entries = []
    for a in soup.select('a.gIconLink'):
        label = a.get_text(' ', strip=True)
        if not label:
            continue
        if 'exp' in a.get('class', []):
            match = re.fullmatch(r'(.+?)\s*\(\s*(\d+)\s*\)', label)
            if not match:
                raise ValueError('Folder without document count')
            entries.append({'kind': 'folder', 'title': match[1].strip(),
                            'count': int(match[2]), 'action': a.get('onclick', '')})
        elif a.get('href', '').startswith(f'https://{HOST}/preview-document/'):
            entries.append({'kind': 'document', 'titulo': label, 'url': a['href'],
                            'nombre_archivo': a.get('title')})
        else:
            raise ValueError('Unknown inventory entry')
    more = [b for b in soup.select('button') if 'Mostrar más' in b.get_text()]
    if len(more) > 1:
        raise ValueError('Ambiguous pagination')
    return entries, more[0].get('onclick', '') if more else None


def build_records(entries, inventories):
    """Group by official folder, never treat a standalone attachment as a plan."""
    shared = [e for e in entries if e['kind'] == 'document']
    if any(not re.search(r'Refundido de Modif 1 y 2', e['titulo'], re.I) for e in shared):
        raise ValueError('Unclassified standalone planning document')
    records = []
    for folder, url, docs in inventories:
        if len({d['url'] for d in docs}) != folder['count']:
            raise ValueError('Incomplete document inventory: ' + folder['title'])
        if not docs:
            continue
        if not re.match(r'^7\.1\.\d+\s+(NORMAS SUBSIDIARIAS|MODIFICACI[OÓ]N|PLAN PARCIAL)', folder['title'], re.I):
            raise ValueError('Unknown instrument folder')
        attachments = [dict(d, inventory_url=url) for d in docs]
        if re.search(r'MODIFICACION Nº [12] DE NNSS$', folder['title']):
            attachments.extend(dict(d, inventory_url=SOURCE, relacion='texto refundido compartido modificaciones 1 y 2') for d in shared)
        records.append({
            'id': 'albatera-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'municipio': 'Albatera', 'codigo_ine': '03005', 'provincia': 'Alicante',
            'titulo': re.sub(r'^7\.1\.\d+\s+', '', folder['title']),
            'tipo': 'instrumento de planeamiento urbanístico',
            'url': url, 'inventory_url': SOURCE, 'documentos': attachments,
            'source': 'ayuntamiento', 'origen': 'portal_transparencia_planeamiento',
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'geometry_status': 'unavailable',
        })
    if not records:
        raise ValueError('No documented planning instruments')
    return records


class AlbateraAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, session, url, **kwargs):
        if urlparse(url).hostname != HOST:
            raise ValueError('Off-site inventory URL')
        response = session.get(url, timeout=40, **kwargs)
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Off-site redirect')
        self._source_urls.add(response.url)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(response.url.encode()).hexdigest()[:16] + '.gz'
            (directory / name).write_bytes(gzip.compress(response.content))
            self._captures.append({'url': response.url, 'file': name,
                                   'sha256': hashlib.sha256(response.content).hexdigest()})
        return response

    def _action(self, session, url, action):
        match = re.search(r"wicketAjaxGet\('([^']+)'", action)
        if not match:
            raise ValueError('Missing Wicket action')
        return self._get(session, urljoin(url, match[1]),
                         headers={'Wicket-Ajax': 'true', 'Referer': url})

    def _inventory(self, session, url):
        response = self._get(session, url)
        entries, more = parse_page(response.text)
        pages = 0
        while more is not None:
            pages += 1
            if pages > 1000:
                raise ValueError('Pagination safety limit; refusing partial output')
            response = self._action(session, url, more)
            batch, more = parse_page(response.text)
            if not batch:
                raise ValueError('Pagination made no progress')
            old_keys = {(e['kind'], e.get('url', e.get('title'))) for e in entries}
            new_keys = {(e['kind'], e.get('url', e.get('title'))) for e in batch}
            if not new_keys - old_keys:
                raise ValueError('Pagination made no progress')
            entries.extend(batch)
        keys = [(e['kind'], e.get('url', e.get('title'))) for e in entries]
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate inventory items')
        return entries

    def backfill_proyectos(self, out_jsonl: Path):
        self._source_urls, self._captures = set(), []
        with requests.Session() as session:
            entries = self._inventory(session, SOURCE)
            folders = [e for e in entries if e['kind'] == 'folder']
            if not folders:
                raise ValueError('Missing planning folders')
            inventories = []
            for folder in folders:
                response = self._action(session, SOURCE, folder['action'])
                location = response.headers.get('Ajax-Location')
                if not location:
                    raise ValueError('Missing folder location')
                url = urljoin(SOURCE, location)
                docs = self._inventory(session, url)
                if any(d['kind'] != 'document' for d in docs):
                    raise ValueError('Nested folder requires explicit grouping')
                inventories.append((folder, url, docs))
        records = build_records(entries, inventories)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
        return {'status': 'ok', 'live_records': len(records), 'source_urls': sorted(self._source_urls),
                'limitations': LIMITATIONS, 'captures': self._captures,
                'empty_folders': [f['title'] for f, _, docs in inventories if not docs],
                'document_count': sum(len(d) for _, _, d in inventories) + sum(e['kind'] == 'document' for e in entries)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        raise NotImplementedError('Licences disabled: no verified granted-licence inventory')

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
