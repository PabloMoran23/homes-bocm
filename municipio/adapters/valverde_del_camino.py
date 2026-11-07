"""Current 7.0 planning/project folders from Valverde's official transparency portal.

Wicket action tokens are resolved in a live session; only stable folder/document
URLs are emitted. Empty folders and generic procedures are not project records.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'valverdedelcamino.sedelectronica.es'
INVENTORY = f'https://{HOST}/transparency/297f7e56-036e-4dd5-81d7-c6c829be0016/'
SECTION = '7.0. DOCUMENTOS EN TRAMITACION'
PROJECT = re.compile(r'^(?:CA_Proyecto_Actuacion_|Proyecto (?:de actuaci[oó]n|Actuacion)\b|Estudio de Detalle\b|Modificaci[oó]n puntual\b)', re.I)


def official_url(url: str, path: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != HOST or not parsed.path.startswith(path):
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def parse_page(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    if SECTION not in soup.get_text(' ', strip=True):
        raise ValueError('Expected 7.0 inventory breadcrumb missing')
    # Refuse partial extraction when the reviewed single-page layout changes.
    for a in soup.select('a,button,input'):
        label = (a.get_text(' ', strip=True) or a.get('value', '')).lower()
        if label in {'mostrar más', 'mostrar mas', 'siguiente', 'next', 'cargar más'} or 'next' in a.get('rel', []):
            raise ValueError('Pagination detected; extend traversal before extraction')
    folders = []
    for a in soup.select('a.gIconLink.exp'):
        title = re.sub(r'\s*\(\s*\d+\s*\)\s*$', '', a.get_text(' ', strip=True)).strip()
        count = a.select_one('.linkExtraInfo')
        match = re.fullmatch(r'\s*\(\s*(\d+)\s*\)\s*', count.get_text() if count else '')
        if not match:
            raise ValueError('Missing folder document count')
        action = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
        if not action:
            raise ValueError('Missing live folder navigation action')
        folders.append({'titulo': title, 'count': int(match[1]), 'action': action[1]})
    docs = {}
    for a in soup.select('a[href]'):
        url = urljoin(f'https://{HOST}/', a['href'])
        if '/preview-document/' in url:
            official_url(url, '/preview-document/')
            docs[url] = {'titulo': a.get_text(' ', strip=True), 'url': url,
                         'source': 'ayuntamiento', 'inventory_section': SECTION}
    if not folders and not docs and 'No se han encontrado elementos' not in soup.get_text():
        raise ValueError('Unrecognized or empty inventory layout')
    return folders, list(docs.values())


def build_record(title: str, url: str, documents: list[dict]) -> dict:
    official_url(url, '/transparency/')
    if not PROJECT.match(title) or not documents:
        raise ValueError('A named instrument with source documents is required')
    return {
        'id': 'valverde-del-camino-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Valverde del Camino', 'codigo_ine': '21072', 'provincia': 'Huelva',
        'titulo': title, 'tipo': 'instrumento o proyecto urbanístico',
        'url': url, 'inventory_url': INVENTORY, 'source': 'ayuntamiento',
        'origen': 'portal_transparencia_documentos_en_tramitacion',
        'documentos': documents, 'source_section': SECTION,
        'coverage': 'partial_current_7_0_document_inventory',
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class ValverdeDelCaminoAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, headers=None):
        official_url(url, '/')
        response = session.get(url, headers=headers, timeout=(10, 35))
        response.raise_for_status()
        official_url(response.url, '/')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20]
            (directory / f'{name}.html').write_bytes(response.content)
        self.source_urls.add(response.url)
        return response

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = set()
        rows, skipped = [], []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-valverde-inventory/1.0'
            folders, root_docs = parse_page(self._fetch(session, INVENTORY).text)
            if root_docs:
                raise ValueError('Ungrouped documents appeared at inventory root; review grouping')
            for folder in folders:
                title = folder['titulo']
                if not PROJECT.match(title):
                    skipped.append({'titulo': title, 'reason': 'generic category, not a named instrument'})
                    continue
                # Refresh Wicket actions immediately before use; they are session-bound.
                current, _ = parse_page(self._fetch(session, INVENTORY).text)
                matches = [f for f in current if f['titulo'] == title]
                if len(matches) != 1 or matches[0]['count'] != folder['count']:
                    raise ValueError('Inventory changed during extraction')
                action_url = urljoin(INVENTORY, matches[0]['action'])
                response = self._fetch(session, action_url, {'Wicket-Ajax': 'true', 'Referer': INVENTORY})
                location = response.headers.get('Ajax-Location')
                if not location:
                    raise ValueError('Wicket folder navigation did not return a stable URL')
                url = official_url(urljoin(response.url, location), '/transparency/')
                children, docs = parse_page(self._fetch(session, url).text)
                if children:
                    raise ValueError('Nested folders appeared; extend grouping before extraction')
                if len(docs) != folder['count']:
                    raise ValueError('Document count mismatch; refusing truncated extraction')
                if not docs:
                    skipped.append({'titulo': title, 'url': url, 'reason': 'empty official folder'})
                    continue
                rows.append(build_record(title, url, docs))
        if not rows:
            raise ValueError('No usable documented projects in current inventory')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'document_count': sum(len(r['documentos']) for r in rows),
                'coverage': 'partial_current_7_0_document_inventory', 'skipped': skipped,
                # Session query tokens are not durable source references.
                'source_urls': sorted(u for u in self.source_urls if not urlparse(u).query)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        """Replace current snapshot; no claim of incremental historical coverage."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
