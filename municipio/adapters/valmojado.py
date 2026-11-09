"""Valmojado's municipal planning document inventory (complete page snapshot)."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.valmojado.com/normas-subsidarias/'


def _norm(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                   if not unicodedata.combining(c))


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1.entry-title')
    content = soup.select_one('article .entry-content')
    if not heading or _norm(heading.get_text(' ', strip=True)) not in (
        'normas subsidarias', 'normas subsidiarias'
    ) or content is None:
        raise ValueError('Valmojado planning inventory markup/title missing')
    # The observed inventory is one static page. Refuse newly introduced paging
    # instead of silently returning only the first page.
    if soup.select('[rel~=next], .pagination, .page-numbers, .post-page-numbers, .page-links'):
        raise ValueError('Inventory pagination detected; traversal must be reviewed')
    groups = {}
    for a in content.select('a[href]'):
        target = urljoin(source_url, a['href'])
        if not urlparse(target).path.lower().endswith('.pdf'):
            continue
        if (urlparse(target).scheme != 'https' or
                urlparse(target).hostname not in ('www.valmojado.com', 'valmojado.com')):
            raise ValueError('Unexpected document host in municipal inventory')
        title = a.get_text(' ', strip=True)
        label = _norm(title)
        sector = re.fullmatch(r'plan parcial ordenacion sector\s+(\d+)\.?', label)
        if sector:
            key = 'sector-' + str(int(sector[1]))
            instrument = f'Plan Parcial Ordenación SECTOR {int(sector[1])}'
            kind = 'plan parcial'
            role = 'plan parcial'
        else:
            key, instrument, kind = 'nnss', 'Normas Subsidiarias de Valmojado', 'normas subsidiarias'
            if re.fullmatch(r'normas subsidi?arias valmojado\.?', label):
                role = 'normas urbanísticas'
            elif label.startswith('anexo def. conceptos valmojado'):
                role = 'anexo de conceptos'
            elif label.startswith('doc. memoria justificativa valmojado'):
                role = 'memoria justificativa'
            elif re.match(r'^\d+\s*[–-]\s*ord\s+\d+', label):
                role = 'plano de ordenación'
            else:
                raise ValueError(f'Unclassified inventory document: {title}')
        row = groups.setdefault(key, {
            'id': 'valmojado-planeamiento-' + key,
            'municipio': 'Valmojado', 'codigo_ine': '45180', 'provincia': 'Toledo',
            'titulo': instrument, 'tipo': kind,
            'url': source_url, 'inventory_url': source_url,
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'coverage': 'Inventario documental municipal; sin garantía de vigencia ni histórico completo',
            'documentos': [],
        })
        if not any(d['url'] == target for d in row['documentos']):
            row['documentos'].append({'titulo': title, 'url': target, 'tipo': role,
                                      'source_url': source_url})
    if 'nnss' not in groups or not any(
        d['tipo'] == 'normas urbanísticas' for d in groups['nnss']['documentos']
    ):
        raise ValueError('No principal Normas Subsidiarias document found')
    return sorted(groups.values(), key=lambda r: r['id'])


class ValmojadoAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='valmojado', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'
        })
        response.raise_for_status()
        if (urlparse(response.url).hostname not in ('www.valmojado.com', 'valmojado.com')
                or urlparse(response.url).path.rstrip('/') != '/normas-subsidarias'):
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'inventory.html').write_text(response.text, encoding='utf-8')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [response.url],
                'documents': sum(len(r['documentos']) for r in rows),
                'coverage': 'current_document_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh of a single inventory, without a date-based truncation.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
