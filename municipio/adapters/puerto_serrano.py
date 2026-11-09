"""Current Puerto Serrano planning inventory on its official transparency portal."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'gobiernoabierto.dipucadiz.es'
PREFIX = '_indicadorespublicosv2_WAR_gestionindicadorestransparenciav2portlet_'
SOURCE = (
    f'https://{HOST}/catalogo-de-informacion-publica?'
    'p_p_id=indicadorespublicosv2_WAR_gestionindicadorestransparenciav2portlet'
    '&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&p_p_col_id=column-1'
    f'&p_p_col_pos=2&p_p_col_count=4&{PREFIX}seccionId=7&{PREFIX}entidadId=2001'
)
INSTRUMENT = re.compile(
    r'^(?:ESTUDIO DE DETALLE|PLAN GENERAL|PLAN PARCIAL|PLAN ESPECIAL|'
    r'MODIFICACI[ÓO]N|INNOVACI[ÓO]N|PROYECTO DE (?:URBANIZACI[ÓO]N|REPARCELACI[ÓO]N))\b',
    re.I,
)


def official_url(value: str, base: str) -> str:
    url = urljoin(base, value)
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != HOST:
        raise ValueError('Unexpected source host or protocol')
    return url


def check_page(soup):
    if 'Ayuntamiento de Puerto Serrano' not in soup.get_text(' ', strip=True):
        raise ValueError('Missing municipality identity')
    # This inventory is currently unpaginated. Fail explicitly if that changes.
    for node in soup.select('a[href], [onclick], .pagination, .lfr-pagination'):
        text = node.get_text(' ', strip=True).lower()
        target = node.get('href', '') + node.get('onclick', '')
        if (node.get('rel') and 'next' in node['rel']) or text in {'siguiente', 'next', '›', '»'} or re.search(r'[?&][^=&]*(?:cur|start|page)=\d+', target, re.I) or node.select_one('.pagination, .lfr-pagination'):
            raise ValueError('Pagination detected; refusing incomplete inventory')
    if soup.select_one('.pagination, .lfr-pagination'):
        raise ValueError('Pagination detected; review crawler')


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    check_page(soup)
    sections = soup.select('.contenido_indicadores_seccion')
    if not sections:
        raise ValueError('Missing urbanism inventory container')
    rows = {}
    for section in sections:
        for item in section.select('li[onclick]'):
            title = item.get_text(' ', strip=True).lstrip('> ').strip()
            if not INSTRUMENT.match(title):
                continue
            match = re.search(r"window\.open\('([^']+)'", item['onclick'])
            if not match:
                raise ValueError('Instrument has no detail link')
            target = official_url(match.group(1), url)
            query = parse_qs(urlparse(target).query)
            if query.get(PREFIX + 'entidadId') != ['2001']:
                raise ValueError('Instrument belongs to another entity')
            identifier = query.get(PREFIX + 'indicadorId', [''])[0]
            if not identifier.isdigit():
                raise ValueError('Missing instrument identifier')
            rows.setdefault(identifier, {'id': 'puerto-serrano-plan-' + identifier,
                'titulo': title, 'url': target, 'inventory_url': url,
                'municipio': 'Puerto Serrano', 'codigo_ine': '11029', 'provincia': 'Cádiz',
                'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
                'origen': 'inventario_transparencia_urbanismo',
                'publication_ready': False, 'geometry_status': 'unavailable'})
    if not rows:
        raise ValueError('No named planning instruments found')
    return list(rows.values())


def parse_detail(html: str, row: dict) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    check_page(soup)
    block = soup.select_one('.indicador_detalle')
    heading = block.select_one('h3') if block else None
    if heading is None or heading.get_text(' ', strip=True) != row['titulo']:
        raise ValueError('Detail title does not match inventory')
    documents = {}
    for node in block.select('.indicador_detalle_distribuciones_item'):
        match = re.search(r"location\.href\s*=\s*'([^']+)'", node.get('onclick', ''))
        anchor = node.select_one('a[href]')
        value = match.group(1) if match else (anchor['href'] if anchor else None)
        if value is None:
            raise ValueError('Distribution without a resource link')
        target = official_url(value, row['url'])
        if not urlparse(target).path.startswith('/uploads/indicadores/'):
            raise ValueError('Unexpected document provenance')
        documents.setdefault(target, {'titulo': node.get_text(' ', strip=True),
                                     'url': target, 'source_url': row['url']})
    if not documents:
        raise ValueError('Planning instrument has no source documents')
    result = {**row, 'documentos': list(documents.values())}
    for node in block.select('.indicador_detalle_datacion'):
        # CMS creation/modification dates are neither agreement nor approval dates.
        if node.get_text(' ', strip=True).startswith('Fecha de creación:'):
            result['fecha_creacion_ficha'] = node.get_text(' ', strip=True).split(':', 1)[1].strip()
    return result


class PuertoSerranoAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=45, headers={'User-Agent': 'municipio-inventory/1.0'})
        response.raise_for_status()
        official_url(response.url, url)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        rows = parse_inventory(self._fetch(SOURCE))
        rows = [parse_detail(self._fetch(row['url']), row) for row in rows]
        return {**self._write(out_jsonl, rows), 'coverage': 'current_transparency_planning_inventory',
                'source_urls': [SOURCE] + [r['url'] for r in rows], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
