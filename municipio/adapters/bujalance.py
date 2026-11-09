"""Municipal PGOU document inventory, exposed by the public WordPress API."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

INVENTORY_URL = 'https://bujalance.es/ayuntamiento/ayuntamiento-documentos/'
API_URL = 'https://bujalance.es/wp-json/wp/v2/pages?search=pgou'
LIMITATIONS = [
    'Cobertura parcial: sección PGOU de Normativa Municipal; no registro exhaustivo de actuaciones.',
    'Documentos agrupados por instrumento; la corrección de Ancha de Palomino se conserva como documento del PGOU.',
    'Sin inferir vigencia, fase de ejecución, fechas de acuerdo o aprobación ni geometría.',
    'Los enlaces se conservan tal como los publica el inventario; no se verifica cada documento en cada ejecución.',
    'No se extraen licencias concedidas, noticias, formularios ni anuncios de contratación.',
]


def parse_inventory(page: dict) -> list[dict]:
    """Parse only the planning section, never ordinance or navigation links."""
    if page.get('link', '').rstrip('/') != INVENTORY_URL.rstrip('/'):
        return []
    soup = BeautifulSoup(page['content']['rendered'], 'html.parser')
    if soup.select('a[rel~=next], .pagination, .page-links'):
        raise ValueError('Unexpected embedded pagination in inventory')
    headings = [h for h in soup.select('h2') if h.get_text(' ', strip=True).startswith('PGOU Bujalance y Morente')]
    if len(headings) != 1:
        raise ValueError('Expected one PGOU Bujalance y Morente section')
    heading = headings[0]
    title = heading.get_text(' ', strip=True)
    documents = []
    seen = set()
    context = ''
    for node in heading.next_elements:
        if getattr(node, 'name', None) == 'h2':
            break
        if getattr(node, 'name', None) in ('strong', 'h3'):
            context = node.get_text(' ', strip=True)
        if getattr(node, 'name', None) != 'a' or not node.get('href'):
            continue
        target = urljoin(INVENTORY_URL, node['href'])
        parsed = urlparse(target)
        if parsed.scheme != 'https' or parsed.hostname not in {
            'bujalance.es', 'www.bujalance.es', 'www.juntadeandalucia.es', 'ws132.juntadeandalucia.es'
        }:
            raise ValueError(f'Unexpected planning document URL: {target}')
        label = node.get_text(' ', strip=True)
        if not label:
            raise ValueError('Unlabelled planning document')
        if target in seen:
            continue
        seen.add(target)
        documents.append({'titulo': label, 'url': target, 'contexto_fuente': context,
                          'inventory_url': INVENTORY_URL})
    # A page heading alone is not an instrument record: require technical evidence.
    if not any('memoria' in d['url'].lower() for d in documents) or not any('nnuu' in d['url'].lower() for d in documents):
        raise ValueError('PGOU technical documents missing')
    return [{
        'id': 'bujalance-plan-' + hashlib.sha256((INVENTORY_URL + '#pgou').encode()).hexdigest()[:16],
        'municipio': 'Bujalance', 'provincia': 'Córdoba', 'codigo_ine': '14012',
        'titulo': title, 'tipo': 'instrumento de planeamiento',
        'url': INVENTORY_URL, 'inventory_url': INVENTORY_URL,
        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
        'source_api_url': API_URL, 'source_page_id': page['id'],
        'documentos': documents, 'coverage': 'partial_current_document_inventory',
        'publication_ready': False, 'geometry_status': 'unavailable',
    }]


class BujalanceAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = {}
        source_urls = []
        seen_pages = set()
        expected_pages = None
        total_items = 0
        expected_items = None
        page_number = 1
        while True:
            url = API_URL if page_number == 1 else f'{API_URL}&page={page_number}'
            response = requests.get(url, timeout=45, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            if urlparse(response.url).hostname != 'bujalance.es':
                raise ValueError('Unexpected API redirect')
            pages = int(response.headers['X-WP-TotalPages'])
            items = int(response.headers['X-WP-Total'])
            if pages < 1 or items < 1:
                raise ValueError('Empty inventory search')
            if expected_pages is None:
                expected_pages, expected_items = pages, items
            if (pages, items) != (expected_pages, expected_items):
                raise ValueError('Inventory changed during pagination; retry')
            data = response.json()
            if not isinstance(data, list) or not data:
                raise ValueError('Missing inventory page')
            source_urls.append(url)
            capture_dir = self.config.get('evidence_dir')
            if capture_dir:
                capture = Path(capture_dir)
                capture.mkdir(parents=True, exist_ok=True)
                (capture / f'pages-pgou-{page_number}.json').write_bytes(response.content)
            for item in data:
                if item['id'] in seen_pages:
                    raise ValueError('Repeated page during pagination')
                seen_pages.add(item['id'])
                total_items += 1
                for row in parse_inventory(item):
                    rows[row['id']] = row
            if page_number == expected_pages:
                break
            page_number += 1
        if total_items != expected_items:
            raise ValueError('Incomplete API inventory')
        if not rows:
            raise ValueError('No usable municipal planning inventory found')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows.values()), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': source_urls + [INVENTORY_URL],
                'api_pages': expected_pages, 'coverage': 'partial_current_document_inventory',
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh of this small inventory; no guessed date cursor or state mutation.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
