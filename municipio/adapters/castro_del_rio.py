"""Public municipal planning-document inventory; no granted-licence coverage."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://castrodelrio.es/urbanismo-y-obras-publicas/'
LIMITATIONS = [
    'Partial coverage: municipal urban-planning document inventory, not a complete current planning register or works inventory.',
    'Publication dates belong to municipal web pages; agreement and approval dates are not extracted from attachments.',
    'Legacy external attachment URLs are retained as published; their contents and availability are not verified by this adapter.',
    'Mobility guide and the inventory self-link are excluded. No granted licences are extracted.',
    'No verified geometry or coordinates; publication_ready is false.',
]


def _text(node):
    return node.get_text(' ', strip=True)


def _official(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.netloc == 'castrodelrio.es'


class CastroDelRioAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://castrodelrio.es')

    @staticmethod
    def parse_inventory(html: str, source_url: str = SOURCE) -> list[str]:
        soup = BeautifulSoup(html, 'html.parser')
        # No pagination is present in the reviewed live inventory. Fail closed if
        # introduced: never return a first page while claiming a full snapshot.
        if soup.select('.pagination, .wp-pagenavi, .nav-links, a[rel~=next], .load-more, [data-next-page]'):
            raise ValueError('Inventory pagination detected; crawler needs review')
        for a in soup.select('a[href]'):
            if re.search(r'/page/\d+|[?&]paged?=\d+', a['href']) or _text(a).lower() in {'siguiente', 'next', 'cargar más'}:
                raise ValueError('Inventory pagination detected; crawler needs review')
        links = []
        for a in soup.select('article .vcex-blog-entry-title a[href]'):
            title = _text(a)
            url = urljoin(source_url, a['href'])
            if title in {'Guía de Movilidad', 'Urbanismo y obras públicas'}:
                continue
            if not re.match(r'^(Plan Parcial|Modificación de las normas subsidiarias|Tramitación de innovación|P\.G\.O\.U\.)', title):
                raise ValueError(f'Unreviewed inventory entry: {title}')
            if not _official(url):
                raise ValueError('Non-municipal planning detail URL')
            if url not in links:
                links.append(url)
        if not links:
            raise ValueError('Municipal planning inventory missing or changed')
        return links

    @staticmethod
    def parse_project(html: str, source_url: str) -> dict[str, Any]:
        if not _official(source_url):
            raise ValueError('Expected official municipal source URL')
        soup = BeautifulSoup(html, 'html.parser')
        article = soup.select_one('article.single-blog-article')
        heading = article.select_one('h1.entry-title') if article else None
        content = article.select_one('.single-blog-content') if article else None
        if not heading or not content:
            raise ValueError('Missing municipal planning detail content')
        title = _text(heading)
        if not re.match(r'^(Plan Parcial|Modificación de las normas subsidiarias|Tramitación de innovación|P\.G\.O\.U\.)', title):
            raise ValueError('Not a supported planning instrument')
        documents = {}
        for a in content.select('a[href]'):
            url = urljoin(source_url, a['href'])
            parsed = urlparse(url)
            if parsed.scheme not in {'http', 'https'}:
                continue
            if not (parsed.path.lower().endswith('.pdf') or
                    (parsed.hostname == 'e-admin.eprinsa.es' and '/castrodelrio/firmadigital/' in parsed.path)):
                continue
            block = a.find_parent('p')
            # Older PGOU tables place labels in the adjacent column of a row.
            if not block:
                block = a.find_parent(class_='vc_row')
            label = _text(block) if block else _text(a)
            documents.setdefault(url, {
                'titulo': label, 'url': url, 'source_url': source_url,
                'provenance': 'Enlace publicado por el Ayuntamiento; contenido no analizado',
            })
        if not documents:
            raise ValueError('Planning instrument lacks linked source documents')
        timestamp = article.select_one('time[itemprop=datePublished]')
        published = None
        if timestamp and timestamp.get('datetime'):
            published = date.fromisoformat(timestamp['datetime']).isoformat()
        return {
            'id': 'castro-del-rio-proy-' + hashlib.sha256(source_url.encode()).hexdigest()[:16],
            'municipio': 'Castro del Río', 'provincia': 'Córdoba', 'codigo_ine': '14019',
            'titulo': title, 'tipo': 'planeamiento_urbanistico',
            'fase': None, 'fecha': None, 'fecha_publicacion': published,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': source_url, 'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
            'descripcion': _text(content), 'documentos': list(documents.values()),
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'Sin geometría verificada en la ficha municipal',
        }

    def _fetch(self, url: str) -> str:
        if not _official(url):
            raise ValueError('Refusing non-municipal source')
        with requests.get(url, timeout=40, stream=True, headers={
            'User-Agent': 'municipio-castro-del-rio/1.0',
        }) as response:
            response.raise_for_status()
            if not _official(response.url) or 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Unexpected source redirect or content type')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 3_000_000:
                    raise ValueError('Municipal HTML exceeds response size bound')
            html = body.decode('utf-8')
        if self.config.get('capture_dir'):
            target = Path(self.config['capture_dir'])
            target.mkdir(parents=True, exist_ok=True)
            (target / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(path: Path, rows: list[dict[str, Any]]):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        urls = self.parse_inventory(self._fetch(SOURCE))
        # Fetch and validate the entire snapshot before replacing the output.
        rows = [self.parse_project(self._fetch(url), url) for url in urls]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, *urls],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
