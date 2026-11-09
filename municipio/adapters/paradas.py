"""Paradas: current municipal planning document inventory (partial coverage)."""
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

SOURCE_URL = ('https://transparencia.paradas.es/es/transparencia/'
              'indicadores-de-transparencia/indicador/PLANEAMIENTO-Y-GESTION./')
HOST = 'transparencia.paradas.es'
DOCUMENT_PATH = '/export/sites/paradas/es/transparencia/.galleries/'
LIMITATIONS = [
    'Inventario documental de PLANEAMIENTO Y GESTIÓN; cobertura municipal parcial.',
    'No incluye el inventario separado de convenios, otras fuentes, obras ni licencias.',
    'No se verifica vigencia, aprobación ni contenido de cada PDF; las etiquetas son del portal.',
    'Sin fechas de acuerdo/publicación normalizadas ni coordenadas verificadas.',
    'Algunos documentos están enlazados bajo instrumentos diferentes en el propio portal.',
]


def _key(title: str) -> str:
    text = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode().lower()
    # The same Los Alberos number 3 instrument appears twice, with accent and
    # punctuation variations. Do not merge different modifications by shared PDFs.
    return re.sub(r'[^a-z0-9]+', '', text)


def parse_inventory(html: str, url: str = SOURCE_URL) -> list[dict]:
    if urlparse(url).hostname != HOST:
        raise ValueError('Unexpected inventory host')
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.sg-indicador-trans')
    if article is None:
        raise ValueError('Missing municipal indicator article')
    # This is a single document, not a search result. Fail closed if the CMS
    # introduces pagination, rather than quietly returning the first page.
    if soup.select('a[rel~=next], .pagination a[href], .paginacion a[href], .pager a[href]'):
        raise ValueError('Pagination detected: inventory traversal must be reviewed')
    for a in article.select('a[href]'):
        if _key(a.get_text(' ', strip=True)) in {'siguiente', 'next', 'masresultados'}:
            raise ValueError('Pagination detected: inventory traversal must be reviewed')
    records = {}
    for block in article.select('div.contentblock'):
        heading = block.find('h3', recursive=False)
        if heading is None:
            continue
        title = heading.get_text(' ', strip=True)
        normalized = _key(title)
        if not normalized.startswith(('modificacion', 'estudiodedetalle', 'planespecial',
                                       'aprobaciondeldocumentodeavance')):
            continue
        documents = []
        section = None
        for node in block.find_all(['h4', 'a']):
            if node.name == 'h4' and 'gallery-title' in node.get('class', []):
                section = node.get_text(' ', strip=True)
            if node.name != 'a' or not node.get('href'):
                continue
            target = urljoin(url, node['href'])
            parsed = urlparse(target)
            if (parsed.scheme != 'https' or parsed.hostname != HOST
                    or not parsed.path.startswith(DOCUMENT_PATH)
                    or not parsed.path.lower().endswith('.pdf')):
                continue
            document = {'titulo': node.get_text(' ', strip=True), 'url': target,
                        'source_url': url}
            if section:
                document['seccion_fuente'] = section
            documents.append(document)
        if not documents:
            raise ValueError(f'Planning instrument lacks documents: {title}')
        if normalized not in records:
            records[normalized] = {
                'id': 'paradas-plan-' + hashlib.sha256(normalized.encode()).hexdigest()[:20],
                'municipio': 'Paradas', 'provincia': 'Sevilla', 'codigo_ine': '41071',
                'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'url': documents[0]['url'], 'inventory_url': url,
                'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
                'titulos_fuente': [], 'documentos': [],
                'publication_ready': False, 'geometry_status': 'unavailable',
                'limitations': list(LIMITATIONS),
            }
        row = records[normalized]
        if title not in row['titulos_fuente']:
            row['titulos_fuente'].append(title)
        for document in documents:
            # Keep distinct source section labels for repeated links.
            if document not in row['documentos']:
                row['documentos'].append(document)
    if not records:
        raise ValueError('No supported planning instruments found')
    return list(records.values())


class ParadasAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE_URL, timeout=45, headers={
            'User-Agent': 'municipio-paradas/1.0 (public planning inventory)'})
        response.raise_for_status()
        if urlparse(response.url).path != urlparse(SOURCE_URL).path:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [response.url],
                'coverage': 'current_planning_document_inventory_partial',
                'limitations': list(LIMITATIONS), 'publication_ready': False}

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                        encoding='utf-8')
        temp.replace(output)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full current snapshot; no incremental cursor claiming historical coverage.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
