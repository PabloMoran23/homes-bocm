"""Current PGOU dossier snapshot from the official public transparency inventory."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'https://monfortedelcid.sedelectronica.es'
INDEX = HOST + '/transparency/c2e943e9-2609-4a2e-a28c-68f516d07c5c/'
SOURCE = HOST + '/transparency/813eccc0-589a-4bb4-a5c9-a2a10f0ffcff/'


def callback(element):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing public pagination callback')
    url = urljoin(SOURCE, match[1])
    if urlparse(url).netloc != urlparse(HOST).netloc:
        raise ValueError('Unexpected callback host')
    return url


def parse_fragment(html):
    """Parse one initial table or AJAX component set, excluding site navigation."""
    soup = BeautifulSoup(html, 'html.parser')
    documents, folders = {}, {}
    for a in soup.select('a.gIconLink'):
        title = a.get_text(' ', strip=True)
        url = urljoin(SOURCE, a.get('href', ''))
        if urlparse(url).netloc == urlparse(HOST).netloc and re.fullmatch(
            r'/preview-document/[0-9a-f-]{36}/?', urlparse(url).path
        ):
            url = url.rstrip('/')
            documents[url] = {'titulo': title, 'url': url, 'source_url': SOURCE}
        elif 'exp' in a.get('class', []):
            count = re.search(r'\(\s*(\d+)\s*\)\s*$', title)
            if not count:
                raise ValueError('Folder without inventory count')
            folders[title] = {'titulo': title, 'document_count': int(count[1])}
        else:
            raise ValueError('Unknown inventory entry')
    buttons = [b for b in soup.select('button') if 'Mostrar más' in b.get_text(' ', strip=True)]
    if len(buttons) > 1:
        raise ValueError('Ambiguous pagination')
    return documents, folders, callback(buttons[0]) if buttons else None


def ajax_fragment(xml):
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response' or root.find('redirect') is not None:
        raise ValueError('Unexpected AJAX response')
    components = root.findall('component')
    if not components:
        raise ValueError('Empty AJAX page')
    return ''.join(c.text or '' for c in components)


class MonforteDelCidAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, session, url, *, ajax=False):
        headers = {'Wicket-Ajax': 'true', 'Referer': SOURCE} if ajax else {}
        response = session.get(url, headers=headers, timeout=40)
        response.raise_for_status()
        if urlparse(response.url).netloc != urlparse(HOST).netloc:
            raise ValueError('Unexpected source redirect')
        # Optional local source captures; never a cached extraction fallback.
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            number = len(self.source_urls)
            (directory / f'live-{number:02d}.{"xml" if ajax else "html"}').write_text(response.text, encoding='utf-8')
        self.source_urls.append(response.url)
        return response.text

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-monforte-del-cid/1.0'
            index = BeautifulSoup(self._get(session, INDEX), 'html.parser')
            entries = [a for a in index.select('table.TransparencyListPanel a.gIconLink')
                       if a.get_text(' ', strip=True).startswith('PLAN GENERAL - (CTU ')]
            if len(entries) != 1:
                raise ValueError('Missing or ambiguous Plan General inventory')
            label = entries[0].get_text(' ', strip=True)
            count = re.search(r'\(\s*(\d+)\s*\)\s*$', label)
            ctu = re.search(r'\(CTU (\d{2}-\d{2}-\d{4})\)', label)
            if not count or not ctu:
                raise ValueError('Unrecognized Plan General label')
            expected = int(count[1])
            ctu_date = datetime.strptime(ctu[1], '%d-%m-%Y').date().isoformat()
            initial = BeautifulSoup(self._get(session, SOURCE), 'html.parser')
            if 'PLAN GENERAL - (CTU ' not in initial.get_text(' ', strip=True):
                raise ValueError('Plan dossier missing')
            table = initial.select_one('table.TransparencyListPanel')
            if table is None:
                raise ValueError('Inventory table missing')
            # Include pagination outside the table, but no menu/sidebar links.
            fragment = str(table) + ''.join(str(b) for b in initial.select('button')
                                                   if 'Mostrar más' in b.get_text())
            documents, folders, next_url = parse_fragment(fragment)
            pages = 1
            while next_url:
                if pages >= 100:
                    raise ValueError('Pagination safety limit reached; no output written')
                fragment = ajax_fragment(self._get(session, next_url, ajax=True))
                new_docs, new_folders, next_url = parse_fragment(fragment)
                before = len(documents) + len(folders)
                documents.update(new_docs)
                folders.update(new_folders)
                if next_url and len(documents) + len(folders) <= before:
                    raise ValueError('Pagination made no progress')
                pages += 1
            # Recursive source count includes explicitly excluded child dossiers.
            if not documents or len(documents) + sum(f['document_count'] for f in folders.values()) != expected:
                raise ValueError('Inventory count mismatch; incomplete coverage')
            if not any('MEMORIA JUSTIFICATIVA' in d['titulo'] for d in documents.values()):
                raise ValueError('Missing substantive planning document')
        record = {
            'id': 'monforte-del-cid-pgou-813eccc0-589a-4bb4-a5c9-a2a10f0ffcff',
            'municipio': 'Monforte del Cid', 'codigo_ine': '03088', 'provincia': 'Alicante',
            'titulo': re.sub(r'\s*\(\s*\d+\s*\)\s*$', '', label),
            'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
            'origen': 'portal_transparencia_planeamiento', 'url': SOURCE,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'fecha_referencia_ctu': ctu_date, 'fecha_referencia_ctu_fuente': INDEX,
            'documentos': list(documents.values()),
            'subcarpetas_excluidas': list(folders.values()),
            'cobertura': 'Documentos directos del Plan General; modificaciones y estudios de detalle excluidos.',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        }
        result = self._write(out_jsonl, [record])
        return {**result, 'source_urls': self.source_urls, 'inventory_pages': pages,
                'documents': len(documents), 'excluded_folders': list(folders.values())}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
