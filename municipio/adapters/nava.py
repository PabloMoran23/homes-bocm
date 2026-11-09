"""Complete snapshot of Nava's municipal planning-document inventory."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.ayto-nava.es/urbanismo-y-vivienda'
# Reviewed instrument headings, not individual files: nested building fichas and
# annexes belong to their parent instrument. Fail if the inventory changes scope.
SECTIONS = {
    'Normas Subsidiarias': ('normas-subsidiarias', 'Normas Subsidiarias de Nava'),
    'Revisión parcial de las normas subsidiarias': (
        'revision-parcial-nnss', 'Revisión parcial de las normas subsidiarias de Nava'),
    'Normativa Parque Empresarial de la Sidra': (
        'parque-empresarial-sidra', 'Plan Especial del Parque Empresarial de la Sidra — normativa publicada'),
    'Plan Especial de Ceceda': ('plan-especial-ceceda', 'Plan Especial de Ceceda'),
    'PERMEUN': ('permeun', 'PERMEUN — Nava'),
}


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    articles = [a for a in soup.select('.journal-content-article')
                if a.select_one('.titulo h2') and
                a.select_one('.titulo h2').get_text(' ', strip=True) == 'Urbanismo']
    if len(articles) != 1:
        raise ValueError('Expected one Nava Urbanismo article')
    article = articles[0]
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if ('next' in a.get('rel', []) or label in {'siguiente', 'next', '»', '›'}
                or 'siguiente' in a.get('aria-label', '').casefold()):
            raise ValueError('Pagination detected; review inventory before extracting')
    if article.select('.pagination, .lfr-pagination, .pager'):
        raise ValueError('Paginated inventory is unsupported')
    detail = article.select_one('.detalle')
    if detail is None:
        raise ValueError('Missing planning inventory content')
    headings = detail.find_all('h3')
    names = [h.get_text(' ', strip=True) for h in headings]
    if len(names) != len(SECTIONS) or set(names) != set(SECTIONS):
        raise ValueError('Planning sections changed, missing or duplicated; review source')
    rows = []
    for heading, name in zip(headings, names):
        links = []
        for sibling in heading.next_siblings:
            if getattr(sibling, 'name', None) in {'h2', 'h3'}:
                break
            if getattr(sibling, 'name', None):
                links.extend(sibling.select('a[href]'))
        documents = {}
        for a in links:
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            is_file = (parsed.path == '/c/document_library/get_file'
                       and len(query.get('uuid', [])) == 1
                       and query.get('groupId') == ['118304'])
            is_document = parsed.path.startswith('/documents/118304/')
            if (parsed.scheme != 'https' or parsed.netloc != 'www.ayto-nava.es'
                    or not (is_file or is_document)):
                # Contact paragraph after the last list is outside the inventory.
                if not a.find_parent('li'):
                    continue
                raise ValueError(f'Unexpected document URL in {name}: {url}')
            title = a.get_text(' ', strip=True)
            if not title:
                raise ValueError(f'Unlabelled document in {name}')
            documents.setdefault(url, {'titulo': title, 'url': url, 'source_url': SOURCE,
                                       'seccion': name})
        if not documents:
            raise ValueError(f'No documents for {name}')
        key, title = SECTIONS[name]
        rows.append({
            'id': 'nava-plan-' + key, 'municipio': 'Nava', 'codigo_ine': '33040',
            'provincia': 'Asturias', 'titulo': title, 'titulo_fuente': name,
            'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'url': SOURCE, 'inventory_url': SOURCE,
            'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
            'documentos': list(documents.values()),
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'No verified instrument geometry extracted',
            'coverage': 'Municipal document inventory only; not a complete planning history',
        })
    return rows


class NavaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=(15, 45), stream=True,
                          headers={'User-Agent': 'municipio-nava/1.0'}) as response:
            response.raise_for_status()
            if response.url.rstrip('/') != SOURCE:
                raise ValueError('Unexpected planning inventory redirect')
            if 'text/html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Expected HTML inventory')
            content = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                content.extend(chunk)
                if len(content) > 3_000_000:
                    raise ValueError('Inventory exceeds reviewed 3 MB response limit')
            html = content.decode('utf-8')
        rows = parse_inventory(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_bytes(content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'documents': sum(len(r['documentos']) for r in rows),
                'coverage': 'complete single-page inventory; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Refresh the entire snapshot, including removals; no incremental date cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0,
                'reason': 'No verified granted-licence register; forms are excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
