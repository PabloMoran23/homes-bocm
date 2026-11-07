"""Snapshot of Manzanares' official planning document inventory (not licences)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.manzanares.es/ayuntamiento/urbanismo'
POM = 'Plan de Ordenación Municipal'
BASE_LABELS = {
    'Catálogo de bienes y espacios protegidos', 'Fichas Urbanísticas',
    'Eliminación de barreras urbanísticas y mejora estética del acerado',
    'Nuevas Alineaciones del Polígono Industrial de Manzanares.',
    'Planos de Información', 'Alineaciones', 'Planos de Ordenación',
    'Texto Refundido Normativa POM',
}
CAD_LABELS = {
    'POM cartografía (archivo dwg)', 'POM zonificación (archivo dwg)',
    'BASE_Manzanares (archivo dwg)', 'POM_Rustica (archivo dwg)',
}
SECTOR = 'Normas Urbanísticas del Plan Parcial del PAU del Sector 5 (anuncio del BOP)'


class ManzanaresAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='manzanares', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        view = soup.select_one('.view-urbanismo')
        content = view.select_one('.view-content') if view else None
        if content is None:
            raise ValueError('Missing official Urbanismo inventory')
        # A changed/paginated inventory needs a crawler review, never a partial success.
        if soup.select('.pager a[href], a[rel~="next"], .pagination a[href]'):
            raise ValueError('Paginated inventory requires crawler review')
        for a in view.select('a[href]'):
            if a.get_text(' ', strip=True).strip(' »›').lower() in {'siguiente', 'next', 'más', 'ver más'}:
                raise ValueError('Continuation link requires crawler review')
        groups: dict[str, dict[str, Any]] = {}
        section = None
        for block in content.find_all(recursive=False):
            if block.name == 'h3':
                section = block.get_text(' ', strip=True)
                continue
            for a in block.select('a[href]'):
                label = a.get_text(' ', strip=True)
                key = title = kind = None
                if section == POM:
                    match = re.fullmatch(r'Modificación puntual n[º°o]\s*(\d+)(?:\s*[-–:].*)?', label, re.I)
                    if match:
                        key = 'pom-mod-' + str(int(match[1]))
                        title = f'{POM} de Manzanares — Modificación puntual nº {int(match[1])}'
                        kind = 'modificacion_planeamiento'
                    elif label == SECTOR:
                        key, title, kind = 'plan-parcial-sector-5', 'Plan Parcial del PAU del Sector 5', 'plan_parcial'
                    elif label in BASE_LABELS:
                        key, title, kind = 'pom', POM + ' de Manzanares', 'plan_ordenacion_municipal'
                    else:
                        raise ValueError(f'Unreviewed document in POM section: {label}')
                elif section == 'Otros' and label in CAD_LABELS:
                    key, title, kind = 'pom', POM + ' de Manzanares', 'plan_ordenacion_municipal'
                if key is None:
                    continue  # Other regulations, instructions and concession studies excluded.
                url = urljoin(SOURCE, a['href'])
                parsed = urlsplit(url)
                if (parsed.scheme != 'https' or parsed.hostname != 'www.manzanares.es'
                        or not parsed.path.startswith('/sites/default/files/docs/urbanismo/')
                        or not parsed.path.lower().endswith(('.pdf', '.dwg'))):
                    raise ValueError(f'Unexpected planning document URL: {url}')
                row = groups.setdefault(key, {
                    'id': 'manzanares-proy-' + key, 'municipio': 'Manzanares',
                    'provincia': 'Ciudad Real', 'codigo_ine': '13053',
                    'titulo': title, 'tipo': kind, 'url': SOURCE,
                    'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
                    'source_entity_type': 'documento',
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                    'fecha_aprob': None, 'fase': None,
                    'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                    'cobertura': 'Inventario documental municipal; sin verificación de vigencia ni de fechas de aprobación.',
                })
                doc = {'titulo': label, 'url': url, 'url_fuente': SOURCE, 'seccion_fuente': section}
                if not any(d['url'] == url for d in row['documentos']):
                    row['documentos'].append(doc)
        if 'pom' not in groups or not any(k.startswith('pom-mod-') for k in groups):
            raise ValueError('Inventory does not expose the reviewed POM and modifications')
        return list(groups.values())

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=(10, 45), stream=True,
                          headers={'User-Agent': 'municipio-manzanares/1.0'}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Inventory exceeds response limit; no partial output written')
                chunks.append(chunk)
            raw = b''.join(chunks)
        rows = self.parse_projects(raw.decode('utf-8'))
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_bytes(raw)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'document_links': sum(len(r['documentos']) for r in rows),
                'coverage': 'Complete reviewed planning inventory on one page; partial municipal coverage'}

    @staticmethod
    def _write(path: Path, rows: list[dict[str, Any]]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
