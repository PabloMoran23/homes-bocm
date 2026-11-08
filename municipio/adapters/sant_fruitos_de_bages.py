"""Complete document snapshot of the municipal POUM initial-approval folder."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'santfruitosdebages.eadministracio.cat'
SOURCE = f'https://{HOST}/transparency/270cead3-327c-4745-90f0-633eaaf9e14d/'
TITLE = 'Pla d’Ordenació Urbanística Municipal (POUM) de Sant Fruitós de Bages'


def _official(url: str) -> str:
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != HOST:
        raise ValueError('Unexpected non-municipal source URL')
    return url


def _callback(element, base_url: str) -> str:
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing public navigation callback')
    return _official(urljoin(base_url, match[1]))


def _content(html: str):
    # Wicket load-more returns document rows as CDATA components. Never execute
    # its JavaScript; parse only the supplied HTML fragments.
    if html.lstrip().startswith('<?xml'):
        root = ElementTree.fromstring(html)
        if root.tag != 'ajax-response':
            raise ValueError('Unexpected pagination response')
        html = '\n'.join(node.text or '' for node in root.findall('component'))
    return BeautifulSoup(html, 'html.parser')


class SantFruitosDeBagesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or f'https://{HOST}')

    @staticmethod
    def parse_index(html: str, page_url: str = SOURCE):
        soup = _content(html)
        content = soup.select_one('#content')
        if not content or TITLE not in content.get_text(' ', strip=True):
            raise ValueError('Municipal POUM inventory missing')
        folders = content.select('table.TransparencyListPanel a.exp')
        if len(folders) != 1:
            raise ValueError('POUM stages changed; review coverage')
        text = folders[0].get_text(' ', strip=True)
        count = re.fullmatch(r'Aprovació inicial\s*\(\s*(\d+)\s*\)', text)
        if not count or int(count[1]) < 1:
            raise ValueError('Missing initial-approval document count')
        return _callback(folders[0], page_url), int(count[1])

    @staticmethod
    def parse_document_page(html: str, page_url: str):
        soup = _content(html)
        if not html.lstrip().startswith('<?xml'):
            content = soup.select_one('#content')
            if not content or TITLE + '/Aprovació inicial' not in content.get_text(' ', strip=True):
                raise ValueError('Unexpected POUM document folder')
        else:
            content = soup
        if content.select('a.exp'):
            raise ValueError('Unexpected nested document folders')
        docs = {}
        for a in content.select('td.class_name a[href]'):
            url = _official(urljoin(page_url, a['href']))
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(url).path):
                raise ValueError('Unexpected document provenance')
            title = a.get_text(' ', strip=True)
            if not title:
                raise ValueError('Document title missing')
            docs[url] = {'titulo': title, 'url': url, 'source_url': SOURCE}
        if not docs:
            raise ValueError('No actual POUM documents in response')
        buttons = content.select('.more_results button[onclick]')
        if len(buttons) > 1:
            raise ValueError('Ambiguous pagination')
        more = _callback(buttons[0], page_url) if buttons else None
        return list(docs.values()), more

    @staticmethod
    def build_record(documents: list[dict[str, Any]], expected: int, folder_url: str):
        docs = {doc['url']: doc for doc in documents}
        if len(docs) != expected:
            raise ValueError(f'Incomplete POUM inventory: expected {expected}, got {len(docs)}')
        return {
            'id': 'sant-fruitos-de-bages-proy-poum-270cead3-327c-4745-90f0-633eaaf9e14d',
            'municipio': 'Sant Fruitós de Bages', 'codigo_ine': '08213',
            'provincia': 'Barcelona', 'titulo': TITLE,
            'tipo': 'POUM', 'fase': 'aprobación inicial',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None,
            'url': SOURCE, 'url_documento': folder_url,
            'documentos': list(docs.values()),
            'source': 'ayuntamiento', 'origen': 'portal_transparencia_planeamiento',
            'descripcion': 'Documentació del POUM publicada a la carpeta municipal Aprovació inicial.',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'coverage': 'POUM initial-approval document folder only; no complete municipal project or licence register',
        }

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        captures = Path(self.config['evidence_dir']) if self.config.get('evidence_dir') else None
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = self.config.get('user_agent', 'municipio-sant-fruitos-de-bages/1.0')

            def fetch(url):
                _official(url)
                with session.get(url, timeout=30, stream=True) as response:
                    response.raise_for_status()
                    _official(response.url)
                    body = bytearray()
                    for chunk in response.iter_content(65536):
                        body.extend(chunk)
                        if len(body) > 4_000_000:
                            raise ValueError('Source response exceeds reviewed size')
                    source_urls.append(response.url)
                    if captures:
                        captures.mkdir(parents=True, exist_ok=True)
                        (captures / f'poum-live-{len(source_urls)}.html').write_bytes(body)
                    return body.decode('utf-8'), response.url

            html, url = fetch(SOURCE)
            next_url, expected = self.parse_index(html, url)
            documents, seen = [], set()
            folder_url = None
            for _ in range(100):
                if next_url in seen:
                    raise ValueError('Pagination cycle')
                seen.add(next_url)
                html, url = fetch(next_url)
                if folder_url is None:
                    folder_url = url
                page_docs, next_url = self.parse_document_page(html, url)
                documents.extend(page_docs)
                if next_url is None:
                    break
            else:
                raise ValueError('Pagination limit reached; refusing partial output')
        row = self.build_record(documents, expected, folder_url)
        self._write(out_jsonl, [row])
        return {'status': 'ok', 'rows': 1, 'documents': len(row['documentos']),
                'source_urls': source_urls, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full refresh of this bounded current document inventory.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
