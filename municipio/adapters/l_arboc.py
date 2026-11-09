"""L'Arboç: complete HTML POUM document inventory, grouped as one instrument."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/arboc/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme')
LIMITATIONS = [
    'Partial coverage: only the POUM document inventory, last updated 28/06/2018; '
    'not a complete or certified consolidated inventory of current planning.',
    'Publication dates belong to inventory sections, not approval agreements; '
    'approval date and current legal phase are unknown.',
    'No verified geometry or coordinates; linked PDFs are retained, not geocoded.',
    'No granted-licence register, public works archive or procurement extraction.',
]


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    if urlparse(source_url)._replace(query='', fragment='') != urlparse(SOURCE):
        raise ValueError('Unexpected municipal inventory URL')
    soup = BeautifulSoup(html, 'html.parser')
    tables = [t for t in soup.select('table')
              if [h.get_text(' ', strip=True) for h in t.select('thead th')]
              == ['Normativa', 'Data de publicació', 'Enllaç', 'Documents', 'Més informació']]
    if len(tables) != 1:
        raise ValueError('Expected one municipal normative document table')
    table = tables[0]
    container = table.parent
    # The verified DataTable paginates locally over all embedded rows. Refuse
    # server pagination / lazy loading rather than silently scraping page one.
    scripts = ' '.join(s.get_text() for s in container.select('script'))
    if (re.search(r'["\']?(?:serverSide|bServerSide)["\']?\s*:\s*true', scripts, re.I)
            or re.search(r'["\']?(?:ajax|sAjaxSource)["\']?\s*:', scripts)
            or container.select('a[rel~=next], .pagination, .lfr-pagination, .search-container')):
        raise ValueError('Unverified inventory pagination or remote data loading')
    sections, documents = [], {}
    for row in table.select('tbody tr'):
        cells = row.find_all('td', recursive=False)
        if not cells:
            continue
        if len(cells) != 5:
            raise ValueError('Inventory row schema changed')
        label = cells[0].get_text(' ', strip=True)
        if not label.startswith('POUM - '):
            continue  # acoustic map and unrelated regulations are not projects
        if label not in {'POUM - Normativa', 'POUM - Memòria ambiental', 'POUM - Annexos'}:
            raise ValueError('Unknown POUM section; review instrument grouping')
        raw_date = cells[1].get_text(' ', strip=True)
        published = datetime.strptime(raw_date, '%d-%m-%Y').date().isoformat() if raw_date else None
        links = []
        for a in cells[3].select('a[href]'):
            url = urljoin(source_url, a['href'])
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname != 'seu-e.cat' or not parsed.path.startswith('/documents/8061681/'):
                raise ValueError('Unexpected POUM document provenance')
            title = a.get_text(' ', strip=True)
            if not title:
                raise ValueError('Untitled POUM document')
            links.append(url)
            document = documents.setdefault(url, {'titulo': title, 'url': url, 'secciones': []})
            if label not in document['secciones']:
                document['secciones'].append(label)
        if not links:
            raise ValueError('POUM section contains no documents')
        sections.append({'titulo': label, 'fecha_publicacion': published, 'documentos': list(dict.fromkeys(links))})
    if not sections or not any(s['titulo'] == 'POUM - Normativa' for s in sections):
        raise ValueError('No documented POUM normative instrument found')
    dates = {s['fecha_publicacion'] for s in sections}
    return [{
        'id': 'l-arboc-poum', 'municipio': "L'Arboç", 'codigo_ine': '43016',
        'provincia': 'Tarragona', 'titulo': "Pla d'ordenació urbanística municipal de l'Arboç (POUM)",
        'tipo': 'POUM', 'fase': None, 'fecha': None,
        'fecha_publicacion': next(iter(dates)) if len(dates) == 1 else None,
        'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': source_url, 'source': 'ayuntamiento', 'origen': 'inventario_normativa_urbanistica',
        'descripcion': 'Instrumento agrupado a partir de las secciones documentales del POUM: '
                       + '; '.join(s['titulo'] for s in sections),
        'secciones': sections, 'documentos': list(documents.values()),
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False, 'limitations': LIMITATIONS,
    }]


class LArbocAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://seu-e.cat/ca/web/arboc')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-l-arboc/1.0')
        }) as response:
            response.raise_for_status()
            if urlparse(response.url)._replace(query='', fragment='') != urlparse(SOURCE):
                raise ValueError('Unexpected inventory redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Inventory exceeds response limit; nothing truncated')
                chunks.append(chunk)
            raw = b''.join(chunks)
            rows = parse_inventory(raw.decode('utf-8'), response.url)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'live-inventory.html').write_bytes(raw)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'live_records': len(rows), 'source_urls': [SOURCE],
                'document_count': len(rows[0]['documentos']), 'publication_ready': False,
                'coverage': 'complete embedded table; POUM sections grouped; partial municipal coverage',
                'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete snapshot; no incremental watermark based on old publication dates.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
