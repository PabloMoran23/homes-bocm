"""PGOU document inventory from La Pobla Llarga's official transparency portal."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'lapoblallarga.sedelectronica.es'
SOURCE = f'https://{HOST}/transparency/73d2c18c-54c7-431e-8b72-ec18e1e40b5c/'
SECTIONS = {'1. APROBACIÓN', '2. MEMORIA JUSTIFICATIVA',
            '3. NORMAS URBANISTICAS', '4. PLANOS'}
ROOT_DOCUMENTS = {'Corrección errores BOP', 'NORMAS PGOU', '01_planos',
                  'RESOLUCIÓN APROBACION DEFINITIVA PGOU', 'Memoria justificativa'}


def official_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != HOST:
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def parse_folder(html, url):
    """Parse one complete folder; counts are checked by the recursive collector."""
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.TransparencyListPanel')
    if table is None:
        raise ValueError('Missing transparency document inventory')
    main = soup.select_one('#content') or soup
    for a in main.select('.pagination a[href], .navigator a[href], .paging a[href]'):
        if a.get('aria-disabled') != 'true' and 'disabled' not in a.get('class', []):
            raise ValueError('Pagination detected; refuse partial inventory')
    for a in main.select('a[href]'):
        label = a.get_text(' ', strip=True).lower()
        if (a.get('rel') == ['next'] or label in {
                'siguiente', 'next', 'següent', "veure’n més", "veure\'n més", 'ver más'}):
            if a.get('aria-disabled') != 'true' and 'disabled' not in a.get('class', []):
                raise ValueError('Pagination detected; refuse partial inventory')
    docs, folders = {}, []
    for a in table.select('a.gIconLink'):
        title = a.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            count = re.fullmatch(r'(.+?)\s*\(\s*(\d+)\s*\)', title)
            callback = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
            if not count or not callback:
                raise ValueError('Folder lacks document count or navigation callback')
            folders.append({'titulo': count[1].strip(), 'count': int(count[2]),
                            'callback': official_url(urljoin(url, callback[1]))})
        else:
            target = official_url(urljoin(url, a.get('href', '')))
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(target).path):
                raise ValueError('Unrecognized inventory document link')
            docs[target] = {'titulo': title, 'url': target, 'inventory_url': url}
    return list(docs.values()), folders


def build_record(documents):
    titles = {d['titulo'] for d in documents}
    if not ROOT_DOCUMENTS.issubset(titles):
        raise ValueError('PGOU identity documents missing; review source structure')
    return {'id': 'la-pobla-llarga-pgou-73d2c18c-54c7-431e-8b72-ec18e1e40b5c',
            'municipio': 'la Pobla Llarga', 'codigo_ine': '46203', 'provincia': 'Valencia',
            'titulo': 'Plan General de Ordenación Urbana (PGOU) de la Pobla Llarga',
            'tipo': 'planeamiento_urbanistico', 'url': SOURCE, 'inventory_url': SOURCE,
            'source': 'ayuntamiento', 'origen': 'inventario_documental_pgou',
            'documentos': documents, 'coverage': 'current_pgou_document_inventory',
            'publication_ready': False, 'geometry_status': 'unavailable'}


class LaPoblaLlargaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        official_url(url)
        response = session.get(url, timeout=40)
        response.raise_for_status()
        official_url(response.url)
        if not urlparse(response.url).path.startswith('/transparency/'):
            raise ValueError('Folder navigation did not return a transparency folder')
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(response.url.encode()).hexdigest()[:16]
            (folder / f'inventory-{name}.html').write_text(response.text, encoding='utf-8')
        return response.url, response.text

    def collect(self, session):
        root_url, html = self._fetch(session, SOURCE)
        if root_url != SOURCE:
            raise ValueError('PGOU inventory redirected to another folder')
        documents, folders = parse_folder(html, root_url)
        if {d['titulo'] for d in documents} != ROOT_DOCUMENTS:
            raise ValueError('PGOU root documents changed; review grouping')
        if {f['titulo'] for f in folders} != SECTIONS or len(folders) != len(SECTIONS):
            raise ValueError('PGOU sections changed; review grouping')
        seen = {d['url'] for d in documents}
        visited = {root_url}
        for section in sorted(SECTIONS):
            # Wicket callbacks belong to a page/session; obtain a fresh one each time.
            _, html = self._fetch(session, SOURCE)
            _, current = parse_folder(html, SOURCE)
            matches = [f for f in current if f['titulo'] == section]
            if len(matches) != 1:
                raise ValueError('Section changed during collection')
            folder = matches[0]
            child_url, child_html = self._fetch(session, folder['callback'])
            if child_url in visited:
                raise ValueError('Repeated folder navigation')
            visited.add(child_url)
            child_docs, grandchildren = parse_folder(child_html, child_url)
            if grandchildren or len(child_docs) != folder['count']:
                raise ValueError('Incomplete or changed PGOU subfolder')
            for doc in child_docs:
                if doc['url'] in seen:
                    raise ValueError('Repeated document across PGOU folders')
                seen.add(doc['url'])
                doc['seccion'] = section
                documents.append(doc)
        return [build_record(sorted(documents, key=lambda d: d['url']))]

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'municipal-planning-inventory/1.0'})
            rows = self.collect(session)
        return {**self._write(out_jsonl, rows), 'coverage': 'current_pgou_document_inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
