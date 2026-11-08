"""Municipal PGOU document inventory, not a licence or approval register."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://vidreres.cat/pgou/'
SECTIONS = {'Documents PGOU', 'Modificacions PGOU', 'Plans especials', 'Altres'}


def _text(node):
    return unicodedata.normalize('NFC', ' '.join(node.get_text(' ', strip=True).split()))


def _document_url(href):
    url = urljoin(SOURCE, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not (
        (parsed.hostname == 'drive.google.com' and re.fullmatch(r'/file/d/[\w-]+/view', parsed.path))
        or (parsed.hostname in {'vidreres.cat', 'www.vidreres.cat'}
            and parsed.path.startswith('/wp-content/uploads/') and parsed.path.lower().endswith('.pdf'))
    ):
        raise ValueError(f'Unreviewed planning document URL: {url}')
    return url


class VidreresAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://vidreres.cat')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        article = soup.select_one('article#the-post')
        content = article.select_one('.entry-content') if article else None
        if not content or not article.select_one('h1') or _text(article.select_one('h1')).lower() != 'pgou':
            raise ValueError('Missing municipal PGOU inventory')
        if article.select('a[rel~=next], .page-links, .pagination, .nav-links') or any(
            re.search(r'/pgou/(?:\d+|page/)|[?&](?:page|paged)=', a['href'])
            or _text(a).lower() in {'següent', 'siguiente', 'next'}
            for a in article.select('a[href]')
        ):
            raise ValueError('Inventory pagination detected; refusing partial snapshot')
        rows = {}
        seen_sections = set()
        section = None
        excluded = []
        for node in content.find_all(['h3', 'p'], recursive=False):
            title = _text(node)
            if node.name == 'h3':
                if title not in SECTIONS:
                    raise ValueError(f'Unreviewed inventory section: {title}')
                section = title
                seen_sections.add(section)
                continue
            links = node.select('a[href]')
            if not links:
                if title:
                    raise ValueError('Unexpected inventory text without documents')
                continue
            if section == 'Altres' and title == 'Plànol delimitació Vidreres':
                excluded.append(title)  # A map alone does not identify a planning instrument.
                continue
            if section == 'Documents PGOU':
                key, name, kind = 'pgou', 'PGOU de Vidreres', 'PGOU'
            elif section == 'Modificacions PGOU' and title.startswith('MP PGOU '):
                key, name, kind = title.casefold(), title, 'modificacion_planeamiento'
            elif section == 'Plans especials' and title.startswith(('PEU ', 'PEUA ')):
                key, name, kind = title.casefold(), title, 'plan_especial'
            elif section == 'Altres' and title.startswith('PPU '):
                key, name, kind = title.casefold(), title, 'plan_parcial'
            else:
                raise ValueError(f'Unreviewed inventory entry: {title}')
            row = rows.setdefault(key, {
                'id': 'vidreres-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Vidreres', 'codigo_ine': '17213', 'provincia': 'Girona',
                'titulo': name, 'tipo': kind, 'fase': None,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
                'source_section': section, 'source_entity_type': 'documento', 'documentos': [],
                'source_page_fecha_publicacion': None,
                'descripcion': 'Instrumento identificado por el inventario municipal; sin fecha de acuerdo ni fase verificadas.',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'limitations': ['Coverage limited to municipal PGOU inventory; legal currency and document contents not verified.',
                                'No verified project geometry or instrument dates.'],
            })
            for a in links:
                doc = {'titulo': title, 'texto_enlace': _text(a),
                       'url': _document_url(a['href']), 'source_url': SOURCE,
                       'provenance': 'linked_by_municipal_inventory'}
                if doc not in row['documentos']:
                    row['documentos'].append(doc)
        if seen_sections != SECTIONS or 'pgou' not in rows or len(rows) < 2:
            raise ValueError('Incomplete or empty PGOU inventory structure')
        # The visible date belongs to the page, never to any instrument agreement.
        page_date = article.select_one('.single-post-meta .date')
        if page_date:
            match = re.fullmatch(r'(\d{1,2}) de juliol de (\d{4})', _text(page_date))
            if match:
                from datetime import date
                for row in rows.values():
                    row['source_page_fecha_publicacion'] = date(int(match[2]), 7, int(match[1])).isoformat()
        owners = {}
        for key, row in rows.items():
            for doc in row['documentos']:
                owners.setdefault(doc['url'], set()).add(key)
        for row in rows.values():
            shared = [url for url in dict.fromkeys(d['url'] for d in row['documentos']) if len(owners[url]) > 1]
            if shared:
                row['shared_document_urls'] = shared
                row['limitations'].append('Source reuses document links across instruments; associations retained as published, not resolved.')
            row['excluded_inventory_entries'] = excluded
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.get(SOURCE, timeout=35, stream=True,
                          headers={'User-Agent': 'municipio-vidreres/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname not in {'vidreres.cat', 'www.vidreres.cat'}:
                raise ValueError('Unexpected redirect away from municipality')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Inventory exceeds reviewed response size')
                chunks.append(chunk)
            raw = b''.join(chunks)
        rows = self.parse_projects(raw.decode('utf-8'))
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'pgou.html').write_bytes(raw)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Refresh the whole unpaginated inventory, not an append-only news feed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No granted licence register verified'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
