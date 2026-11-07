"""Municipal transparency indicator 50: grouped planning documents, no licences."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = (
    'https://transparencia.lapuebladelrio.es/es/transparencia/'
    'indicadores-de-transparencia/indicador/'
    '50.-PLAN-GENERAL-DE-ORDENACION-URBANA-PGOU-Y-LOS-MAPAS-Y-PLANOS-QUE-LO-DETALLAN/'
)
DOCUMENT_PATH = '/export/sites/lapuebladelrio/es/transparencia/.galleries/IND-50-/'
TITLES = {
    'adaptacion-parcial': 'Adaptación parcial del planeamiento de La Puebla del Río',
    'normas-subsidiarias': 'Normas Subsidiarias de La Puebla del Río (NN.SS.)',
    'pgom': 'Plan General de Ordenación Municipal de La Puebla del Río (PGOM)',
    'pou': 'Plan de Ordenación Urbana de La Puebla del Río (POU)',
}
LIMITATIONS = [
    'Cobertura parcial: inventario documental del indicador municipal 50; no registro completo de expedientes ni obras.',
    'PGOM agrupa avance y documento previo a aprobación inicial; no se acredita aprobación inicial ni vigencia.',
    'No se extraen fechas de publicación, acuerdo o aprobación: el inventario no las identifica inequívocamente para cada instrumento.',
    'Se conservan enlaces documentales; no se comprueba individualmente todo el contenido de los PDF.',
    'Sin licencias concedidas verificadas ni coordenadas; ITACA es un inventario toponímico excluido.',
]


def pagination_urls(soup: BeautifulSoup) -> list[str]:
    """Independent gallery queries: avoid a Cartesian product of page combinations."""
    urls = set()
    for a in soup.select('a[href]'):
        href = a['href']
        if 'pagegalleryfiles' not in href:
            continue
        target = urlparse(urljoin(SOURCE, href))
        if target.hostname != urlparse(SOURCE).hostname or target.path.rstrip('/') != urlparse(SOURCE).path.rstrip('/'):
            raise ValueError('Unexpected pagination target')
        pairs = parse_qsl(target.query)
        if not pairs or any(not re.fullmatch(r'pagegalleryfiles-\d+-\d+', k) or not v.isdigit() or int(v) < 1 for k, v in pairs):
            raise ValueError('Unsupported gallery pagination')
        for key, value in pairs:
            if int(value) > 1:
                urls.add(SOURCE + '?' + urlencode({key: value}))
    return sorted(urls)


def parse_page(html: str, page_url: str = SOURCE) -> tuple[dict, list[str]]:
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.documentacion')
    if article is None:
        raise ValueError('Missing municipal planning inventory')
    # Confirm the server actually selected every requested gallery page.
    active = {tuple(pair) for a in article.select('a.currentpagelink[href]')
              for pair in parse_qsl(urlparse(a['href']).query)}
    if any(pair not in active for pair in parse_qsl(urlparse(page_url).query)):
        raise ValueError('Requested gallery page not active (pagination ignored)')
    groups: dict[str, dict] = {}
    section = None
    for node in article.find_all(['h3', 'h4', 'a']):
        text = node.get_text(' ', strip=True)
        if node.name == 'h3':
            if text.startswith('50.1.'):
                section = 'adaptacion-parcial'
            elif text.startswith('50.2.'):
                section = 'normas-subsidiarias'
            elif text.startswith('50.3.'):
                section = None  # ITACA is not an urban planning instrument.
            elif text.startswith('50.4'):
                section = 'avances'
            elif text not in {'Memoria y Ordenanzas', 'Memoria de Información y de Ordenación',
                              'Información pública del Avance del PGOM y del POU de La Puebla del Río'}:
                section = None
            continue
        if node.name != 'a' or not node.get('href'):
            continue
        url = urljoin(SOURCE, node['href'])
        parsed = urlparse(url)
        if parsed.hostname != urlparse(SOURCE).hostname or not parsed.path.startswith(DOCUMENT_PATH) or not parsed.path.lower().endswith('.pdf'):
            continue
        key = section
        version = None
        if section == 'avances':
            if '/Avance-PGOM/' in parsed.path:
                key, version = 'pgom', 'avance'
            elif '/Avance-POU/' in parsed.path:
                key, version = 'pou', 'avance'
            else:
                gallery = node.find_parent('section', class_='gallery')
                heading = gallery.select_one('.gallery-title') if gallery else None
                label = heading.get_text(' ', strip=True) if heading else ''
                if label == 'PGOM-DOC_PREVIO_APROB_INICIAL':
                    key, version = 'pgom', 'documento previo a aprobación inicial'
                elif label == 'INFORME PARTICIPACIÓN AVANCE PGOM':
                    key, version = 'pgom', 'informe participación avance'
                else:
                    raise ValueError('Unclassified planning document: ' + url)
        if key not in TITLES:
            continue
        group = groups.setdefault(key, {'titulo': TITLES[key], 'documentos': {}})
        doc = {'titulo': text, 'url': url, 'inventory_urls': [page_url]}
        if version:
            doc['version_documental'] = version
        group['documentos'][url] = doc
    if not groups:
        raise ValueError('No supported planning documents')
    return groups, pagination_urls(article)


class LaPueblaDelRioAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        pending, visited, groups = [SOURCE], [], {}
        captures = self.config.get('capture_dir')
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            # Fail rather than silently truncate an unexpectedly expanded inventory.
            if len(visited) >= 100:
                raise ValueError('Inventory exceeds 100 pages; review required')
            response = requests.get(url, timeout=45, headers={
                'User-Agent': 'MunicipalPlanningInventory/1.0',
            })
            response.raise_for_status()
            if (urlparse(response.url).hostname != urlparse(SOURCE).hostname
                    or urlparse(response.url).path.rstrip('/') != urlparse(SOURCE).path.rstrip('/')):
                raise ValueError('Unexpected inventory redirect')
            page, more = parse_page(response.text, url)
            if captures:
                folder = Path(captures)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f'inventory-{len(visited):02d}.html').write_text(response.text, encoding='utf-8')
            visited.append(url)
            for key, group in page.items():
                merged = groups.setdefault(key, {'titulo': group['titulo'], 'documentos': {}})
                for doc_url, doc in group['documentos'].items():
                    if doc_url in merged['documentos']:
                        previous = merged['documentos'][doc_url]
                        if url not in previous['inventory_urls']:
                            previous['inventory_urls'].append(url)
                    else:
                        merged['documentos'][doc_url] = doc
            pending.extend(u for u in more if u not in visited and u not in pending)
        if set(groups) != set(TITLES):
            raise ValueError('Expected planning instrument missing; review inventory')
        rows = []
        for key, group in sorted(groups.items()):
            rows.append({
                'id': 'la-puebla-del-rio-plan-' + key,
                'municipio': 'La Puebla del Río', 'codigo_ine': '41079',
                'provincia': 'Sevilla', 'titulo': group['titulo'],
                'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
                'origen': 'inventario_documental_planeamiento', 'url': SOURCE,
                'documentos': sorted(group['documentos'].values(), key=lambda d: d['url']),
                'publication_ready': False, 'geometry_status': 'unavailable',
            })
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows),
                'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': visited, 'coverage': 'current_document_inventory',
                'limitations': LIMITATIONS}

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Refresh the complete inventory, including document changes/deletions.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
