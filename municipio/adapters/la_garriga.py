"""Public planning inventories on La Garriga's canonical municipal website."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.lagarriga.cat'
URBANISME = BASE + '/ajuntament-seu-electronica/informacio-oficial/2181-urbanisme'
SOURCES = {
    'en_tramit': URBANISME + '/planejament-i-gestio-urbanistica-en-tramit',
    'aprovada_definitivament': URBANISME + '/planejament-i-gestio-urbanistica-aprovada-definitivament',
}
HEADINGS = {
    'en_tramit': 'Planejament i gestió urbanística en tràmit',
    'aprovada_definitivament': 'Planejament i gestió urbanística aprovada definitivament',
}


def _norm(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


def _publication(label: str) -> str | None:
    # Only explicit publication labels, never filenames, certificate dates or
    # the page's misleadingly old "darrera actualització" timestamp.
    match = re.search(r'publicacio.*?\b(?:BOPB|DOGC)\s+(\d{1,2})[-/](\d{1,2})[-/](\d{4})',
                      _norm(label), re.I)
    if not match:
        return None
    return date(int(match[3]), int(match[2]), int(match[1])).isoformat()


def _supported(title: str) -> bool:
    text = _norm(title)
    if 'junta de compensacio' in text or 'estatuts' in text:
        return False
    return any(term in text for term in (
        'modificacio puntual', 'projecte', 'pla especial', "pla d'actuacio",
        'estudi detall', 'estudi de detall', 'reparcel·lacio', 'urbanitzacio',
        "pla d'ordenacio"))


class LaGarrigaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='la-garriga', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html: str, inventory: str) -> list[dict]:
        source = SOURCES[inventory]
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.find('h1')
        table = soup.select_one('#cos_info1 table')
        if not heading or heading.get_text(' ', strip=True) != HEADINGS[inventory] or table is None:
            raise ValueError('Missing municipal planning inventory heading/table')
        # These are complete single-page tables. Fail closed if pagination is
        # introduced; never treat the first page as a complete snapshot.
        if soup.select('[rel~=next], .pagination, .paginacio, .paginador, .pager'):
            raise ValueError('Pagination detected; inventory crawler needs review')
        for a in soup.select('a[href]'):
            if _norm(a.get_text(' ', strip=True)) in {'seguent', 'seguents', 'siguiente', 'next', '»', '›'}:
                raise ValueError('Next-page link detected')
        groups = []
        current = None
        for tr in table.select('tbody tr'):
            cells = tr.find_all('td', recursive=False)
            if len(cells) != 3:
                raise ValueError('Unexpected inventory row structure')
            title = cells[0].get_text(' ', strip=True)
            if title:
                current = {'titulo': title, 'documentos': []}
                groups.append(current)
            elif current is None:
                raise ValueError('Document without an instrument heading')
            anchors = cells[2].select('a[href]')
            if not anchors:
                raise ValueError('Inventory document row has no link')
            label = cells[1].get_text(' ', strip=True)
            for anchor in anchors:
                url = urljoin(source, anchor['href'])
                if urlparse(url).scheme not in {'https', 'http'} or not urlparse(url).hostname:
                    raise ValueError('Invalid document URL')
                if not any(d['url'] == url for d in current['documentos']):
                    current['documentos'].append({
                        'titulo': label, 'url': url, 'source_url': source,
                        'fecha_publicacion': _publication(label),
                    })
        rows = []
        for group in groups:
            title = group['titulo']
            if not _supported(title):
                continue
            normalized = _norm(title)
            match = re.search(r'aprovacio (inicial|provisional|definitiva)', normalized)
            phase = 'aprobación ' + match[1] if match else None
            docs = group['documentos']
            rows.append({
                'id': 'la-garriga-proy-' + hashlib.sha256(_norm(title).encode()).hexdigest()[:16],
                'municipio': 'La Garriga', 'provincia': 'Barcelona', 'codigo_ine': '08088',
                'titulo': title, 'tipo': 'instrumento_urbanistico', 'fase': phase,
                'fase_fuente': title if phase else None,
                'inventario_fuente': inventory, 'source': 'ayuntamiento',
                'origen': 'inventario_planeamiento_municipal', 'url': source,
                'url_documento': docs[0]['url'], 'documentos': docs,
                'fecha': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                # Multiple documents can have different publication dates.
                # Each date belongs to its document, not to the instrument.
                'fecha_publicacion': None,
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'coverage': 'Public HTML inventory metadata; linked document contents not parsed',
            })
        if not rows:
            raise ValueError('No supported planning instruments found')
        ids = [r['id'] for r in rows]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate instrument headings require review')
        return rows

    def _fetch(self, url: str) -> str:
        with requests.get(url, timeout=(10, 40), stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-la-garriga/1.0'),
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'www.lagarriga.cat':
                raise ValueError('Unexpected municipal source redirect')
            chunks = []
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Municipal inventory exceeds response size limit')
                chunks.append(chunk)
            html = b''.join(chunks).decode('utf-8')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / (url.rsplit('/', 1)[-1] + '.html')).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = []
        for inventory, source in SOURCES.items():
            rows.extend(self.parse_inventory(self._fetch(source), inventory))
        # A moved/repeated instrument must be reconciled explicitly, not emitted
        # twice or silently overwritten. Today the supported groups are disjoint.
        ids = [r['id'] for r in rows]
        documents = [d['url'] for r in rows for d in r['documentos']]
        if len(ids) != len(set(ids)) or len(documents) != len(set(documents)):
            raise ValueError('Overlapping instruments/documents require inventory reconciliation')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES.values()),
                'publication_ready': False, 'coverage': 'partial municipal planning inventories'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
