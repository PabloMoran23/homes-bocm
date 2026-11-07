"""Partial snapshot of the official in-process planning inventory (2.2 / 2.3)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.torroella-estartit.cat/ca/planejament-gestio-i-execucio-urbanistica-en-.html'
LIMITATIONS = [
    'Partial coverage: only sections 2.2 and 2.3 of the municipal in-process inventory; not a historical register.',
    'Section 2.1, current planning/RPUC inventories and regional PLATER consultation documents are outside this adapter scope.',
    'Dates remain null: HTML has no explicit publication/agreement dates; PDF contents and filename dates are not parsed.',
    'Attachments are retained as municipal inventory references, not individually fetched or guaranteed accessible by the adapter.',
    'No verified project geometry or granted-licence register; publication_ready=false.',
]


def _text(node) -> str:
    return ' '.join(node.get_text(' ', strip=True).split())


def _normal(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold()) if not unicodedata.combining(c))


class TorroellaDeMontgriAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.torroella-estartit.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('.page_content .resum')
        heading = soup.find(['h1', 'h2'], string=re.compile('Planejament, gestió i execució'))
        if content is None or heading is None:
            raise ValueError('Missing municipal planning inventory heading/content')
        # Fail rather than silently returning just the first page if the site changes.
        for a in soup.select('a[href]'):
            if (a.get('rel') and 'next' in a['rel']) or _normal(_text(a)) in {
                'seguent', 'seguent pagina', 'pagina seguent', 'next', 'siguiente', '»', '›',
            }:
                if a['href'] not in ('', '#'):
                    raise ValueError('Inventory pagination detected; traversal must be implemented')
        if soup.select('.pagination, .paginacio, .paginacion, .pager'):
            raise ValueError('Inventory pagination markup detected')

        section = None
        seen_sections = []
        rows = {}
        for block in content.find_all(['p', 'ul'], recursive=False):
            text = _text(block)
            marker = re.match(r'^(2\.[123])\.\s', text)
            if marker:
                section = marker[1]
                seen_sections.append(section)
                continue
            if text.startswith('ALTRES DOCUMENTS'):
                section = 'other'
                continue
            if section not in ('2.2', '2.3') or not text:
                continue
            links = block.select('a[href]')
            if not links:
                raise ValueError('Ungrouped instrument text in supported inventory sections')
            # The first title is either plain text before <br> or the first link.
            prefix = []
            for child in block.children:
                if getattr(child, 'name', None) in ('a', 'br'):
                    break
                prefix.append(child.get_text(' ', strip=True) if hasattr(child, 'get_text') else str(child))
            title = ' '.join(' '.join(prefix).split()) or _text(links[0])
            norm = _normal(title)
            if not (norm.startswith(('aprovacio inicial', 'aprovacio definitiva')) and
                    any(word in norm for word in ('projecte', 'pla de millora', 'pla general'))):
                raise ValueError(f'Unrecognized instrument title: {title}')
            docs = {}
            for a in links:
                url = urljoin(SOURCE, a['href'])
                parsed = urlparse(url)
                if parsed.scheme != 'https' or parsed.hostname not in {
                    'www.torroella-estartit.cat', 'drive.torroella-estartit.cat',
                }:
                    raise ValueError(f'Unreviewed document host: {url}')
                if not (parsed.path.lower().endswith('.pdf') or
                        (parsed.hostname == 'drive.torroella-estartit.cat' and parsed.path.startswith('/s/'))):
                    raise ValueError(f'Unreviewed document link: {url}')
                docs[url] = {'titulo': _text(a), 'url': url, 'source_url': SOURCE,
                             'provenance': 'enlace del inventario municipal; contenido no analizado'}
            exp = re.search(r'\bexp\.?\s*(\d+[A-Z])\b', title, re.I)
            expediente = exp[1].upper() if exp else None
            identity = expediente or re.sub(r'^aprovacio (inicial|definitiva)( del| de la)?\s*', '', norm)
            key = hashlib.sha256(identity.encode()).hexdigest()[:16]
            if key in rows:
                raise ValueError('Repeated instrument identity; review grouping before extraction')
            rows[key] = {
                'id': 'torroella-de-montgri-proy-' + key,
                'municipio': 'Torroella de Montgrí', 'codigo_ine': '17199', 'provincia': 'Girona',
                'titulo': title, 'expediente': expediente,
                'tipo': ('estudio_detalle' if 'estudi de detall' in norm else
                         'proyecto_urbanizacion' if re.search(r'projecte\s+(?:d[’\']\s*)?urbanitzacio', norm)
                         else 'planeamiento_urbanistico'),
                'fase': 'aprobación definitiva' if norm.startswith('aprovacio definitiva') else 'aprobación inicial',
                'fase_source': title,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_urbanismo_en_tramite',
                'source_section': section, 'documentos': list(docs.values()),
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'coverage': 'partial: inventory sections 2.2 and 2.3 only',
            }
        if seen_sections != ['2.1', '2.2', '2.3'] or not rows:
            raise ValueError('Missing/reordered inventory sections or no usable instruments')
        if {row['source_section'] for row in rows.values()} != {'2.2', '2.3'}:
            raise ValueError('Supported inventory section empty; source review required')
        return list(rows.values())

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=(15, 45), stream=True,
                          headers={'User-Agent': self.config.get('user_agent', 'municipio-torroella/1.0')}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'www.torroella-estartit.cat':
                raise ValueError('Unexpected inventory redirect')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Inventory response exceeds 4 MB')
            html = data.decode('utf-8')
        rows = self.parse_projects(html)
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'live-inventory.html').write_bytes(data)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete refresh of this bounded snapshot, not an append-only history.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
