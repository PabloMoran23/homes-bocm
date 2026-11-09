"""Current municipal NNSS document inventory; no inferred approvals or geometry."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://tarazonadelamancha.es/normativa-municipal/'
HOST = 'tarazonadelamancha.es'


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if not main or not main.find('h1', string=re.compile('Normativa Municipal')):
        raise ValueError('Missing municipal normative inventory')
    # This inventory is a static page. Changed pagination must never be ignored.
    if soup.select('[rel~=next], [rel~=prev]') or main.select(
        '.pagination, .page-numbers, .nav-links, .post-page-numbers'
    ):
        raise ValueError('Pagination detected; inventory coverage requires review')
    for a in main.select('a[href]'):
        if re.search(r'/page/\d|[?&](?:page|paged|offset)=', a['href']):
            raise ValueError('Paginated inventory requires review')
    groups = {}
    for a in main.select('a[href]'):
        label = a.get_text(' ', strip=True)
        normalized = _norm(label)
        if not normalized.startswith('revision '):
            continue
        href = urljoin(url, a['href'])
        target = urlparse(href)
        if (target.hostname != HOST or not target.path.startswith('/wp-content/uploads/')
                or not target.path.lower().endswith('.pdf')):
            raise ValueError('Unexpected planning document URL')
        if 'modif' in normalized:
            year = re.search(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)', normalized)
            if not year:
                raise ValueError('Modification without an identifiable year')
            key = 'modificacion-' + year[0]
            title = 'Revisión de Normas Subsidiarias de Planeamiento — Modificación puntual ' + year[0]
        elif 'normas subsidiarias de planeamiento' in normalized and 'volumen iv' in normalized:
            key = 'revision-nnss'
            title = 'Revisión de Normas Subsidiarias de Planeamiento — Volumen IV'
        else:
            raise ValueError('Unrecognized planning document; grouping requires review')
        if key not in groups:
            groups[key] = {
                'id': 'tarazona-de-la-mancha-plan-' + key,
                'municipio': 'Tarazona de la Mancha', 'provincia': 'Albacete',
                'codigo_ine': '02073', 'titulo': title,
                'tipo': 'instrumento de planeamiento', 'url': SOURCE,
                'source': 'ayuntamiento', 'origen': 'inventario_normativa_municipal',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None,
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'coverage': 'Inventario documental parcial; no acredita vigencia ni aprobación.',
                'documentos': [],
            }
        # Retain both the heading and link text: one live heading disagrees with
        # its linked chapter. Do not silently repair or invent a missing PDF.
        p = a.find_parent('p')
        previous = p.find_previous_sibling() if p else None
        heading = previous.get_text(' ', strip=True) if previous and previous.name == 'ul' else label
        documents = groups[key]['documentos']
        document = next((d for d in documents if d['url'] == href), None)
        if document is None:
            document = {'url': href, 'titulo': label, 'rotulos_inventario': [], 'source_url': SOURCE}
            documents.append(document)
        if heading not in document['rotulos_inventario']:
            document['rotulos_inventario'].append(heading)
    if not groups:
        raise ValueError('No usable planning documents found')
    return list(groups.values())


class TarazonaDeLaManchaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'municipio-tarazona-de-la-mancha/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST or urlparse(response.url).path != urlparse(SOURCE).path:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text)
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'normativa-municipal.html').write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'source_urls': [SOURCE], 'coverage': 'current_partial_planning_inventory'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
