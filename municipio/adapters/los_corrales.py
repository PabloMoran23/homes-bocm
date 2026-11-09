"""Reviewed document inventories of Los Corrales (Sevilla), INE 41037."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://transparencia.loscorrales.es'
PREFIX = BASE + '/es/transparencia/indicadores-de-transparencia/indicador/'
SOURCES = {
    '50': PREFIX + 'Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00075/',
    '53': PREFIX + 'Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00074/',
    '55': PREFIX + 'Usos-y-destinos-del-suelo-00074/',
    '62': PREFIX + 'Obras-de-infraestructura-realizadas-y-o-las-aprobadas-pendientes-de-ejecucion-00074/',
}
PBOM = {
    'PBOM_INDICE-GENERAL.pdf', '01_MEMORIA-comprimido.pdf',
    '20260416_respuesta-informe-supervision.pdf', '02_CARTOGRAFIA-INFORMACION-1.pdf',
    '03_CARTOGRAFIA-ORDENACION.pdf', '04_DOC-INICIAL-ESTRATEGICO.pdf',
    '05_RESUMEN-EJECUTIVO.pdf', '06_MEMORIA-RESUMEN-VIS.pdf',
}
DETAIL = {
    'APROBACION-DEFINITIVA-ESTUDIO-DE-DETALLE-CALE-SOSA-14-Y-16.pdf',
    'eTablonEdicto_41037_660-1.pdf', 'CO0525FCC_RESUMEN_EJECUTIVO_F.pdf',
    'CO0525FCC_ESTUDIO_DE_DETALLE_F.pdf',
}
EXCLUDED = {
    'Informe-innecesariedad-de-tramitacion-de-Avance-de-Planeamiento.pdf',
    'Edicto-innecesariedad-tramitacion-Avance-Planeamiento.pdf',
}
TITLES = {
    'pgou': 'Plan General de Ordenación Urbanística de Los Corrales',
    'pbom': 'Plan Básico de Ordenación Municipal de Los Corrales',
    'peri-sunc-1': 'Plan Especial de Reforma Interior del sector SUNC-1 de Los Corrales',
    'mp1-pgou': 'Modificación puntual nº 1 del PGOU de Los Corrales',
    'estudio-sosa-14-16': 'Estudio de detalle de las parcelas de calle Sosa 14 y 16',
    'alumbrado': 'Proyecto de alumbrado público de Los Corrales',
}


def classify(section: str, path: str) -> str | None:
    """Explicit reviewed associations; new unidentified documents require review."""
    name = unquote(path.rsplit('/', 1)[-1])
    if section == '50':
        if name.startswith('PGOU-PUBLICACION-EN-BOJA-'):
            return 'pgou'
        if name in PBOM:
            return 'pbom'
    elif section == '53':
        if '/MP1-PGOU-LOS-CORRALES/' in path:
            return 'mp1-pgou'
        if name.upper() == 'PERI-SUNC-1-LOS-CORRALES.PDF':
            return 'peri-sunc-1'
    elif section == '55':
        if name in EXCLUDED:
            return None
        if name in DETAIL:
            return 'estudio-sosa-14-16'
    elif section == '62' and name == 'Proyecto-Alumbrado-Publico-Los-Corrales_sign_document.pdf':
        return 'alumbrado'
    raise ValueError(f'Unreviewed document in section {section}: {path}')


def parse_inventory(html: str, url: str, section: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    # Inventories currently render all documents in HTML. Refuse partial output
    # if the publisher introduces pagination rather than silently taking page 1.
    if soup.select('.pagination, .pager, [rel="next"], [data-next-page]'):
        raise ValueError('Pagination detected; inventory needs review')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', '»', '›'} and a['href'] not in {'', '#'}:
            raise ValueError('Pagination detected; inventory needs review')
    groups = {}
    gallery = f'/export/sites/loscorrales/es/transparencia/.galleries/IND-{section}-/'
    found = False
    for a in soup.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        if not parsed.path.startswith(gallery):
            continue
        found = True
        if parsed.hostname != urlparse(BASE).hostname or parsed.scheme != 'https':
            raise ValueError('Unexpected document origin')
        key = classify(section, parsed.path)
        if key is None:
            continue
        if not parsed.path.lower().endswith('.pdf'):
            raise ValueError('Expected a PDF document')
        row = groups.setdefault(key, {
            'id': 'los-corrales-' + key, 'municipio': 'Los Corrales',
            'codigo_ine': '41037', 'provincia': 'Sevilla', 'titulo': TITLES[key],
            'tipo': 'proyecto_obra_publica' if key == 'alumbrado' else 'planeamiento_urbanistico',
            'source': 'ayuntamiento', 'origen': 'inventario_documental_transparencia',
            'url': target, 'inventory_url': url, 'documentos': [],
            'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'Inventario documental parcial; no acredita vigencia ni ejecución.',
        })
        if target not in {d['url'] for d in row['documentos']}:
            row['documentos'].append({'titulo': a.get_text(' ', strip=True), 'url': target,
                                      'inventory_url': url})
    if not found or not groups:
        raise ValueError(f'No supported instrument/project documents in section {section}')
    return list(groups.values())


class LosCorralesAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Municipal-document-inventory/1.0'
            for section, url in SOURCES.items():
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if response.url.rstrip('/') != url.rstrip('/'):
                    raise ValueError(f'Unexpected inventory redirect: {response.url}')
                capture = self.config.get('evidence_dir')
                if capture:
                    folder = Path(capture)
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / f'source-{section}.html').write_text(response.text, encoding='utf-8')
                rows.extend(parse_inventory(response.text, response.url, section))
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': list(SOURCES.values()),
                'coverage': 'partial_current_document_inventories', 'publication_ready': False}

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(output)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Reconcile a complete snapshot; no unsupported date-based incremental filter.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
