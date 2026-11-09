"""Ares: one PXOM instrument, with all documents in its municipal inventory."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://concellodeares.gal/es/planes/'
TITLE = 'PLAN XERAL DE ORDENACIÓN MUNICIPAL DE ARES'
VERSION = 'APROBACIÓN DEFINITIVA PXOM 2020'
LIMITATIONS = [
    'Cobertura parcial: únicamente el documento refundido PXOM 2020 del inventario municipal; '
    'no incluye correcciones posteriores ni la documentación de los ámbitos suspendidos aprobados después.',
    'La fecha de aprobación corresponde a la orden citada por la página para esta versión; '
    'no afirma aprobación íntegra ni vigencia actual de todos los ámbitos.',
    'Sin fecha de publicación verificada, licencias concedidas ni geometría extraída. '
    'Las carpetas de subida de los PDF no son fechas de publicación ni de acuerdo.',
    'Se conservan todos los enlaces del inventario; no se verifica el contenido de cada PDF en cada ejecución.',
]


def _text(element):
    return element.get_text(' ', strip=True)


def _official(url):
    parts = urlsplit(url)
    return parts.scheme == 'https' and parts.netloc in {'concellodeares.gal', 'www.concellodeares.gal'}


def parse_projects(html: str, url: str = SOURCE) -> list[dict[str, Any]]:
    """Parse the observed single-page inventory; fail on ambiguity or pagination."""
    if not _official(url):
        raise ValueError('Unexpected Ares inventory origin')
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('a[rel~=next], link[rel~=next], .pagination, .page-numbers, .nav-links'):
        raise ValueError('Ares inventory has pagination: extraction must be revised, not truncated')
    contents = soup.select('main .page-content')
    if len(contents) != 1:
        raise ValueError('Missing or ambiguous Ares inventory content')
    main = contents[0]
    blocks = [b for b in main.select('.elementor-text-editor')
              if any(_text(h) == TITLE for h in b.select('h5'))]
    if len(blocks) != 1:
        raise ValueError('Expected one named Ares PXOM document inventory')
    block = blocks[0]
    headings = [_text(h) for h in block.select('h5')]
    if headings.count(TITLE) != 1 or headings.count(VERSION) != 1:
        raise ValueError('Unrecognized or ambiguous Ares PXOM version')
    descriptions = [_text(p) for p in block.select('p')
                    if _text(p).startswith('Documento refundido do PGOM de Ares conforme á orde de aprobación definitiva')]
    if len(descriptions) != 1:
        raise ValueError('Missing unambiguous plan provenance narrative')
    dates = re.findall(r'\b\d{2}/\d{2}/\d{4}\b', descriptions[0])
    if len(dates) != 1:
        raise ValueError('Missing unambiguous approval order date')
    approval = datetime.strptime(dates[0], '%d/%m/%Y').date().isoformat()
    documents = {}
    section = None
    for node in block.find_all(['h5', 'a']):
        if node.name == 'h5':
            heading = _text(node)
            if heading in (TITLE, VERSION):
                section = None
            elif (heading == 'ÍNDICE DOCUMENTOS:' or heading == 'INFORMES SUFICIENCIA'
                  or re.match(r'^DOCUMENTO [IVX]+:', heading)):
                section = heading
            else:
                raise ValueError(f'Unknown instrument/document section: {heading}')
            continue
        target = urljoin(url, node.get('href', ''))
        if not urlsplit(target).path.lower().endswith('.pdf'):
            continue
        if section is None or not _official(target) or not urlsplit(target).path.startswith('/wp-content/uploads/'):
            raise ValueError('PDF outside the recognized municipal document sections')
        label = _text(node)
        if not label:
            raise ValueError('Unlabelled planning document')
        documents.setdefault(target, {'titulo': label, 'url': target, 'seccion': section,
                                      'source_url': url})
    paths = [urlsplit(u).path.rsplit('/', 1)[-1] for u in documents]
    required = {'00_PGOM_ARES_2020_INDICE.pdf', '03_PGOM_ARES_2020_MEMORIA_XUSTIFICATIVA.pdf',
                '05_PGOM_ARES_2020_NORMATIVA.pdf'}
    if not required.issubset(paths):
        raise ValueError('Missing core PXOM documents; forms/navigation alone are not a plan')
    return [{
        'id': 'ares-pxom-2020', 'municipio': 'Ares', 'codigo_ine': '15004',
        'provincia': 'A Coruña', 'titulo': TITLE + ' — documento refundido PXOM 2020',
        'tipo': 'PXOM', 'fase': 'documento refundido', 'fase_fuente': VERSION,
        'descripcion': descriptions[0], 'fecha': None, 'fecha_publicacion': None,
        'fecha_acuerdo': None, 'fecha_aprob': approval,
        'fecha_aprob_provenance': {'url': url, 'texto': descriptions[0], 'alcance': 'orden citada para la versión 2020'},
        'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
        'documentos': list(documents.values()), 'coverage': 'PXOM 2020 document inventory only',
        'limitations': list(LIMITATIONS), 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }]


class AresAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='ares', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://concellodeares.gal')

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-ares/1.0')})
        response.raise_for_status()
        if not _official(response.url) or urlsplit(response.url).path.rstrip('/') != '/es/planes':
            raise ValueError('Unexpected Ares inventory redirect')
        # Capture the exact live response when requested for a local audit.
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'planes.html').write_bytes(response.content)
        rows = parse_projects(response.text, response.url)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'documents': len(rows[0]['documentos']),
                'source_urls': [response.url], 'limitations': list(LIMITATIONS), 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # A complete refresh of this inventory; state is deliberately not a date cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
