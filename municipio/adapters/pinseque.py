"""Grouped instruments from Pinseque's official planning document inventory."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

INVENTORY_URL = 'https://pinseque.es/areas/urbanismo/'
GENERAL_TITLE = 'NNSS de Pinseque homologación al Plan General de Ordenación Urbana'
MODIFICATION = re.compile(r'^(?:Modificación puntual|MPGOU)\s+n[º°.]\s*(\d+)\b', re.I)
LIMITATIONS = [
    'Inventario documental de planeamiento, no registro completo de proyectos u obras.',
    'Sin licencias concedidas, geometría, fases ni fechas de aprobación inferidas.',
    'Fechas y referencias conservadas en los títulos documentales sin normalizar.',
    'No incluye el tablón de la sede electrónica ni verifica la vigencia jurídica.',
]


def parse_inventory(html: str, url: str = INVENTORY_URL) -> tuple[list[dict], list[str]]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find('h2', string=lambda t: t and t.strip() == GENERAL_TITLE)
    if heading is None:
        raise ValueError('Planning inventory heading missing')
    # The closest shared content container includes PGOU maps and the numbered list.
    container = next((p for p in heading.parents if p.find('strong', string=lambda t: t and MODIFICATION.match(t.strip()))), None)
    if container is None:
        raise ValueError('Numbered planning inventory missing')
    if container.select('a[rel~=next], .pagination, .nav-links, .page-links'):
        raise ValueError('Unexpected pagination; refusing partial inventory')
    groups: dict[str, dict] = {}
    current = None
    for node in container.find_all(['h2', 'p', 'a']):
        title = node.get_text(' ', strip=True)
        if node is heading:
            current = 'pgou'
            groups[current] = {'titulo': GENERAL_TITLE, 'documentos': []}
        elif node.name == 'p' and node.find('strong'):
            match = MODIFICATION.match(title)
            # Reset even for an instrument with no links, preventing cross-assignment.
            current = f'mpgou-{int(match[1])}' if match else None
            if match:
                if current in groups:
                    raise ValueError(f'Duplicate instrument heading: {current}')
                groups[current] = {'titulo': title, 'documentos': []}
        elif node.name == 'h2':
            current = None
        elif node.name == 'a' and current and node.get('href'):
            target = urljoin(url, node['href'])
            parsed = urlparse(target)
            if not parsed.path.lower().endswith('.pdf'):
                continue
            if parsed.scheme != 'https' or parsed.hostname not in {'pinseque.es', 'www.pinseque.es'}:
                raise ValueError(f'Unexpected document origin: {target}')
            docs = groups[current]['documentos']
            if any(d['url'] == target for d in docs):
                continue
            docs.append({'titulo': title or Path(parsed.path).name, 'url': target,
                         'inventory_url': url})
    rows, missing = [], []
    for key, group in groups.items():
        if not group['documentos']:
            missing.append(group['titulo'])
            continue
        rows.append({
            'id': f'pinseque-plan-{key}', 'municipio': 'Pinseque',
            'codigo_ine': '50209', 'provincia': 'Zaragoza',
            **group, 'tipo': 'instrumento de planeamiento urbanístico',
            'url': group['documentos'][0]['url'], 'inventory_url': url,
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'publication_ready': False, 'geometry_status': 'unavailable',
        })
    if not rows or not any(r['id'] == 'pinseque-plan-pgou' for r in rows):
        raise ValueError('No usable PGOU inventory')
    return rows, missing


class PinsequeAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(INVENTORY_URL, timeout=45,
                                headers={'User-Agent': 'municipal-inventory/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in {'pinseque.es', 'www.pinseque.es'}:
            raise ValueError('Unexpected inventory redirect')
        rows, missing = parse_inventory(response.text, response.url)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows),
                'source_urls': [response.url], 'coverage': 'current_planning_document_inventory',
                'headings_without_documents': missing, 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public grant register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
