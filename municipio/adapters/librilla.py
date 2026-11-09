"""Municipal PGMO document inventory; no inferred approvals or geometry."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


SOURCE = 'https://www.librilla.es/plan-general-municipal-ordenacion.asp'
LIMITATIONS = [
    'Cobertura parcial: solo el inventario documental municipal del PGMO; no un histórico municipal completo.',
    'La etiqueta Modificaciones Aprobación Provisional es el título de la fuente; no confirma vigencia ni aprobación definitiva.',
    'No se extraen fechas de publicación o acuerdo: la página no las identifica para el instrumento.',
    'Documentos enlazados, no descargados por el adaptador; disponibilidad y contenido PDF no verificados.',
    'Sin geometría ni coordenadas verificadas; licencias concedidas fuera de cobertura.',
]


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    block = soup.select_one('#noticias')
    heading = block.find('h2') if block else None
    if not heading or not heading.get_text(' ', strip=True).startswith('Plan General Municipal de Ordenación'):
        raise ValueError('Missing municipal PGMO inventory heading')
    # This is a single document list. Refuse new pagination rather than silently
    # returning its first page. Navigation for font size/contrast is unrelated.
    if soup.select('[rel~=next], .pagination, .paginacion, .pager'):
        raise ValueError('Pagination detected; review inventory before extraction')
    for a in block.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if label in {'siguiente', 'next', '»', '›'} or 'pagina=' in a['href'].lower() or 'page=' in a['href'].lower():
            raise ValueError('Pagination detected; review inventory before extraction')
    documents = {}
    for a in block.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        if not parsed.path.lower().endswith('.pdf'):
            continue
        if (parsed.scheme not in {'http', 'https'} or
                parsed.hostname != 'descargas.librilla.es' or
                not parsed.path.startswith('/pgom/')):
            raise ValueError('Unexpected document provenance in PGMO inventory')
        title = a.get_text(' ', strip=True)
        if not title:
            raise ValueError('Untitled PGMO document')
        documents.setdefault(target, {'titulo': title, 'url': target, 'source_url': url})
    if not documents:
        raise ValueError('PGMO inventory contains no source documents')
    return [{
        'id': 'librilla-pgmo',
        'municipio': 'Librilla', 'codigo_ine': '30023', 'provincia': 'Murcia',
        'titulo': heading.get_text(' ', strip=True),
        'tipo': 'planeamiento_urbanistico',
        'url': url, 'inventory_url': url,
        'source': 'ayuntamiento', 'origen': 'inventario_documental_pgmo',
        'documentos': list(documents.values()),
        'coverage': 'partial_current_document_inventory',
        'limitations': list(LIMITATIONS),
        'publication_ready': False, 'geometry_status': 'unavailable',
    }]


class LibrillaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'municipio-librilla/1.0 (public planning inventory)',
        })
        response.raise_for_status()
        if urlparse(response.url)._replace(query='', fragment='') != urlparse(SOURCE):
            raise ValueError('Unexpected PGMO inventory redirect')
        if 'text/html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('PGMO inventory is not HTML')
        response.encoding = 'utf-8'
        html = response.text
        rows = parse_inventory(html, SOURCE)
        if self.config.get('capture_dir'):
            capture_dir = Path(self.config['capture_dir'])
            capture_dir.mkdir(parents=True, exist_ok=True)
            (capture_dir / 'pgmo.html').write_text(html, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows),
                'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': [SOURCE], 'limitations': list(LIMITATIONS),
                'coverage': 'partial_current_document_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full replacement of this small current inventory, not an append-only history.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
