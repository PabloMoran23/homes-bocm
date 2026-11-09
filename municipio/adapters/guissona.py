"""Public Guissona planning/exposure snapshots from its official transparency seat."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://seu-e.cat/ca/web/guissona/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/'
SOURCES = {
    'planejament': BASE + 'planejament-urbanistic',
    'exposicio': BASE + 'projectes-i-documents-tecnics-en-exposicio-publica-211',
}


def _norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def _document_url(url):
    parsed = urlparse(url)
    return (parsed.scheme == 'https' and (
        (parsed.hostname == 'drive.google.com' and (
            re.match(r'^/(?:file/d/|drive/folders/)\w', parsed.path)
            or (parsed.path == '/open' and parse_qs(parsed.query).get('id'))))
        or (parsed.hostname in {'seu-e.cat', 'www.seu-e.cat'} and parsed.path.startswith('/documents/'))))


class GuissonaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://seu-e.cat/ca/web/guissona')

    @staticmethod
    def parse_inventory(html: str, inventory: str) -> list[dict]:
        source = SOURCES[inventory]
        soup = BeautifulSoup(html, 'html.parser')
        # These are static inventories. Refuse changed pagination rather than
        # silently return page one; feedback-widget pagination is unrelated.
        for a in soup.select('a[href]'):
            if a.find_parent(class_='pagination-factchecking'):
                continue
            if ('next' in a.get('rel', []) or _norm(a.get_text(' ', strip=True)) in
                    {'seguent', 'seguent »', 'siguiente', 'next', 'anterior', 'previous'}):
                if a['href'] not in {'', '#', 'javascript:;'} and not a.find_parent(class_='disabled'):
                    raise ValueError('Inventory pagination changed; review crawler before extraction')
        articles = [a for a in soup.select('.journal-content-article')
                    if not a.select_one('.item_indicador, .accessdirecte_element')]
        if not articles or any(a.select_one('table') for a in articles):
            raise ValueError('Missing static inventory or new tabular inventory')
        if inventory == 'planejament' and not any('PLANS URBANÍSTICS' in a.get_text() for a in articles):
            raise ValueError('Missing municipal planning inventory heading')
        rows = {}
        for article in articles:
            footer = article.select_one('.datatable_info_footer')
            updated = None
            if footer:
                match = re.search(r'Actualització:\s*(\d{2}/\d{2}/\d{4})', footer.get_text())
                if match:
                    updated = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
            for p in article.select('p'):
                title = p.get_text(' ', strip=True).strip(' -\u00a0').rstrip(' .')
                links = []
                for a in p.select('a[href]'):
                    url = urljoin(source, a['href'])
                    if _document_url(url) and url not in [d['url'] for d in links]:
                        links.append({'titulo': a.get_text(' ', strip=True), 'url': url,
                                      'source_url': source})
                if not links:
                    continue
                normalized = _norm(title)
                if inventory == 'planejament':
                    if not normalized.startswith(('pla parcial ', 'pla residencial ')):
                        raise ValueError('Unrecognized document-bearing planning entry')
                    kind, phase = 'planeamiento_urbanistico', None
                elif normalized.startswith('aprovacio '):
                    if 'modificacio' not in normalized or 'poum' not in normalized:
                        raise ValueError('Unrecognized planning modification')
                    kind = 'modificacion_planeamiento'
                    phase = ('aprobación inicial' if normalized.startswith('aprovacio inicial ') else
                             'aprobación provisional' if normalized.startswith('aprovacio provisional ') else None)
                elif normalized.startswith(('projecte executiu ', 'reposicio i millores ')):
                    kind, phase = 'proyecto_obra', None
                else:
                    raise ValueError('Unrecognized document-bearing exposure entry')
                # One paragraph is one instrument, even when its title is split
                # between a document link and a municipal context link.
                key = re.sub(r'\s+', ' ', normalized)
                if key in rows:
                    for doc in links:
                        if doc['url'] not in [d['url'] for d in rows[key]['documentos']]:
                            rows[key]['documentos'].append(doc)
                    continue
                rows[key] = {
                    'id': 'guissona-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                    'municipio': 'Guissona', 'provincia': 'Lleida', 'codigo_ine': '25110',
                    'titulo': title, 'tipo': kind, 'fase': phase,
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'source_updated_at': updated, 'url': source, 'url_documento': links[0]['url'],
                    'documentos': links, 'source': 'ayuntamiento', 'origen': inventory,
                    'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                    'coverage': 'Partial municipal inventory; linked document contents not parsed',
                }
        if not rows:
            raise ValueError('No supported municipal instruments found')
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows, captures = [], []
        for inventory, url in SOURCES.items():
            with requests.get(url, timeout=40, stream=True, headers={
                'User-Agent': self.config.get('user_agent', 'municipio-guissona/1.0')
            }) as response:
                response.raise_for_status()
                if urlparse(response.url).hostname not in {'seu-e.cat', 'www.seu-e.cat'}:
                    raise ValueError('Unexpected source redirect')
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > 4_000_000:
                        raise ValueError('Source exceeds response size limit')
                html = content.decode('utf-8')
            rows.extend(self.parse_inventory(html, inventory))
            captures.append((inventory, content))
        self._write(out_jsonl, rows)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            for inventory, content in captures:
                (directory / (inventory + '.html')).write_bytes(content)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES.values()),
                'publication_ready': False, 'coverage': 'partial'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh of both static inventories; no date-based skipping.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
