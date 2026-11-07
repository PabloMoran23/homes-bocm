"""Vilamarxant's local forest-fire prevention plan, from the official SIGIF inventory.

Complete snapshot of the municipal PLPIF section; not a general works or licence
register. Regional/demarcation plans and burning regulations are outside scope.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://prevencionincendiosgva.es'
DETAIL = BASE + '/Planificacion/DetallePlanesMunicipio/532'
INVENTORY = BASE + '/Planificacion/PLPIFList'
LIMITATIONS = [
    'Cobertura parcial: solo el PLPIF municipal publicado en SIGIF; no inventario general de obras ni planeamiento urbanístico.',
    'La aprobación del plan no acredita ejecución de sus actuaciones ni concesión de licencias.',
    'Se retienen enlaces al plan, resolución e informes anuales; no se extrae geometría ni se evalúan revisiones pendientes.',
    'Fecha de resolución autonómica y fecha de publicación DOGV separadas; sin fecha de acuerdo municipal extraída.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # The observed DataTables pagination is client-side: all rows are in HTML.
    # Fail rather than silently accepting a new server-paginated inventory.
    if re.search(r'[\"\']?serverSide[\"\']?\s*:\s*true', html, re.I):
        raise ValueError('Server-side pagination requires crawler review')
    if soup.select('a[rel~=next], .pagination a[href], a.next[href]'):
        raise ValueError('Unreviewed inventory pagination')
    return soup


def _document_url(href, page):
    url = urljoin(page, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'prevencionincendiosgva.es', 'dogv.gva.es'}:
        raise ValueError('Unexpected document provenance: ' + url)
    if not parsed.path.lower().endswith(('.zip', '.pdf')):
        raise ValueError('Expected a plan archive or official PDF')
    return url


def parse_inventory(detail_html: str, inventory_html: str) -> list[dict]:
    detail, inventory = _soup(detail_html), _soup(inventory_html)
    identity = detail.select('#tablaMunicipio tbody tr')
    if len(identity) != 1 or [_text(c) for c in identity[0].select('td')][:3] != ['Vilamarxant', '46256', 'Valencia']:
        raise ValueError('Municipality identity does not match Vilamarxant / 46256 / Valencia')
    table = detail.select_one('#tablaPLPIF')
    listing = inventory.select_one('#tablaValencia')
    if table is None or listing is None:
        raise ValueError('Missing official PLPIF inventory tables')
    if [_text(c) for c in table.select('thead th')][:5] != ['PLPIF', 'Fecha Resolución', 'Resolución', 'Expediente', 'Informes Anuales']:
        raise ValueError('PLPIF detail schema changed')
    expected = ['Municipio', 'Estado', 'Resolución', 'Fecha Resolución', 'DOGV', 'Fecha DOGV', 'Vigencia']
    if [_text(c) for c in listing.select('thead th')] != expected:
        raise ValueError('PLPIF listing schema changed')
    matches = [tr for tr in listing.select('tbody tr') if tr.select('td') and _text(tr.select('td')[0]) == 'Vilamarxant']
    plan_rows = table.select('tbody tr')
    if len(matches) != 1 or len(plan_rows) != 1:
        raise ValueError('Missing or ambiguous municipal PLPIF')
    cells = matches[0].select('td')
    if len(cells) != 7 or _text(cells[1]) != 'Aprobado':
        raise ValueError('PLPIF approval state requires review')
    approval = datetime.strptime(_text(cells[3]), '%d/%m/%Y').date().isoformat()
    publication = datetime.strptime(_text(cells[5]), '%d/%m/%Y').date().isoformat()
    resolution = _text(cells[2])
    if not re.fullmatch(r'\d{4}/\d+', resolution):
        raise ValueError('Missing official resolution identifier')
    documents = {}
    for i, cell in enumerate(plan_rows[0].select('td')):
        for a in cell.select('a[href]'):
            url = _document_url(a['href'], DETAIL)
            documents[url] = {'titulo': _text(a), 'url': url,
                              'rol': {0: 'plan_completo', 2: 'resolucion', 3: 'expediente', 4: 'informe_anual'}.get(i, 'documento'),
                              'source_url': DETAIL}
    if not any(d['rol'] == 'plan_completo' for d in documents.values()):
        raise ValueError('PLPIF lacks the plan document')
    # Cross-check the independently served list against the municipality detail.
    listed_links = [_document_url(a['href'], INVENTORY) for a in matches[0].select('a[href]')]
    if len(listed_links) < 2 or any(u not in documents for u in listed_links):
        raise ValueError('Detail and listing document identities disagree')
    if not any(d['rol'] == 'resolucion' and d['titulo'] == resolution for d in documents.values()):
        raise ValueError('Detail and listing resolution identifiers disagree')
    return [{
        'id': 'vilamarxant-plpif-' + hashlib.sha256(listed_links[0].encode()).hexdigest()[:16],
        'municipio': 'Vilamarxant', 'codigo_ine': '46256', 'provincia': 'Valencia',
        'titulo': 'Plan local de prevención de incendios forestales del término municipal de Vilamarxant',
        'tipo': 'plan_local_prevencion_incendios_forestales', 'fase': 'aprobado',
        'estado_fuente': _text(cells[1]), 'resolucion': resolution,
        'fecha_aprob': approval, 'fecha_resolucion': approval,
        'fecha_publicacion': publication, 'fecha_acuerdo': None,
        'vigencia_texto_fuente': _text(cells[6]),
        'url': DETAIL, 'inventory_url': INVENTORY,
        'source': 'generalitat_valenciana', 'origen': 'sigif_inventario_plpif',
        'documentos': list(documents.values()),
        'date_provenance': {'fecha_aprob': INVENTORY + ' — Fecha Resolución (Estado: Aprobado)',
                            'fecha_publicacion': INVENTORY + ' — Fecha DOGV'},
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False, 'coverage': 'municipal_plpif_only',
    }]


class VilamarxantAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('evidence_dir')
        pages = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-vilamarxant/1.0 (public planning inventory)'
            for name, url in [('sigif-detail.html', DETAIL), ('sigif-list.html', INVENTORY)]:
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if response.url != url:
                    raise ValueError('Unexpected source redirect: ' + response.url)
                if captures:
                    folder = Path(captures)
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / name).write_bytes(response.content)
                pages.append(response.content.decode('utf-8-sig'))
        rows = parse_inventory(*pages)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [DETAIL, INVENTORY],
                'coverage': 'municipal_plpif_only', 'limitations': LIMITATIONS,
                'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
