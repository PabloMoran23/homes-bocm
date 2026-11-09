"""Ferreries municipal PGOU document inventory, refreshed as one instrument."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.ajferreries.org'
SOURCE = BASE + '/Contingut.aspx?IdPub=99'
SECTIONS = {'ISA', 'NORMATIVA', 'MEMÒRIA JUSTIFICATIVA', 'MEMÒRIA INFORMATIVA', 'MEMÒRIA DE GESTIÓ'}


def _content(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    block = soup.select_one('.PLA_ntilla')
    if block is None or block.select_one('.PLA_texte') is None:
        raise ValueError('Missing municipal content container')
    for a in soup.select('a[href]'):
        if 'next' in a.get('rel', []) or a.get_text(' ', strip=True).casefold() in {
            'següent', 'siguiente', 'next', 'següents', 'més resultats', '»', '›'}:
            if a['href'] not in ('', '#', '#*'):
                raise ValueError('Pagination detected; inventory traversal needs review')
    return block


def _official(url: str) -> bool:
    return urlsplit(url).hostname == 'www.ajferreries.org' and urlsplit(url).scheme in {'http', 'https'}


class FerreriesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='ferreries', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html: str) -> list[dict]:
        block = _content(html)
        heading = block.select_one('h1')
        if not heading or heading.get_text(' ', strip=True) != 'PGOU':
            raise ValueError('Expected the PGOU inventory')
        sections = {}
        for a in block.select('.PLA_texte a[href]'):
            title = a.get_text(' ', strip=True)
            url = urljoin(SOURCE, a['href'])
            if not _official(url) or urlsplit(url).path.lower() != '/contingut.aspx':
                raise ValueError('Unexpected PGOU section link')
            ids = parse_qs(urlsplit(url).query.lower()).get('idpub', [])
            if len(ids) != 1 or not ids[0].isdigit():
                raise ValueError('Missing section identifier')
            canonical = BASE + '/Contingut.aspx?IdPub=' + ids[0]
            sections.setdefault(canonical, {'titulo': title, 'url': canonical})
        if not SECTIONS.issubset({s['titulo'] for s in sections.values()}):
            raise ValueError('Incomplete PGOU section inventory')
        return list(sections.values())

    @staticmethod
    def parse_documents(html: str, section: dict) -> list[dict]:
        block = _content(html)
        heading = block.select_one('h1')
        if not heading or heading.get_text(' ', strip=True) != 'PGOU - ' + section['titulo']:
            raise ValueError('PGOU section title changed')
        documents = {}
        for a in block.select('.PLA_texte a[href]'):
            url = urljoin(section['url'], a['href']).split('#')[0]
            if not _official(url) or not urlsplit(url).path.lower().endswith(('.pdf', '.rar', '.zip')):
                raise ValueError('Unexpected document link; review inventory coverage')
            title = a.get_text(' ', strip=True) or unquote(urlsplit(url).path.rsplit('/', 1)[-1])
            documents.setdefault(url, {'titulo': title, 'url': url, 'seccion': section['titulo'],
                                       'url_procedencia': section['url']})
        if not documents:
            raise ValueError('PGOU section has no documents')
        return list(documents.values())

    def _fetch(self, url: str) -> str:
        with requests.get(url, timeout=(10, 45), stream=True,
                          headers={'User-Agent': self.config.get('user_agent', 'municipio-ferreries/1.0')}) as response:
            response.raise_for_status()
            if not _official(response.url):
                raise ValueError('Source redirected outside official municipal site')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 5_000_000:
                    raise ValueError('Source exceeds response size limit')
            html = bytes(data).decode(response.encoding or 'utf-8')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        sections = self.parse_inventory(self._fetch(SOURCE))
        docs = {}
        for section in sections:
            for doc in self.parse_documents(self._fetch(section['url']), section):
                if doc['url'] not in docs:
                    docs[doc['url']] = {**doc, 'procedencias': []}
                provenance = {'titulo': doc['titulo'], 'seccion': doc['seccion'], 'url': section['url']}
                if provenance not in docs[doc['url']]['procedencias']:
                    docs[doc['url']]['procedencias'].append(provenance)
        rows = [{
            'id': 'ferreries-proy-pgou', 'municipio': 'Ferreries', 'codigo_ine': '07023',
            'provincia': 'Illes Balears', 'titulo': 'Pla General d’Ordenació Urbana de Ferreries (PGOU)',
            'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_documental_pgou',
            'descripcion': 'Inventario municipal del PGOU: normativa, documentación ambiental, memorias y cartografía. '
                           'Incluye versiones y rectificaciones enlazadas; no certifica vigencia consolidada.',
            'documentos': list(docs.values()), 'fuentes': [SOURCE] + [s['url'] for s in sections],
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'unavailable: linked PDF cartography has not been vectorized',
        }]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'documents': len(docs), 'source_urls': rows[0]['fuentes'],
                'coverage': 'partial: municipal PGOU document inventory only', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # The inventory has no modification cursor; refresh the complete snapshot.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
