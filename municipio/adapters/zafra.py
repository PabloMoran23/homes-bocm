"""Zafra: complete document snapshot of SITEX's current PGOU refundido package."""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://sitex.juntaex.es/SITEX/ptofiguras/viewrefundido/212'
LIMITATIONS = [
    'Only the current SITEX PGOU.R-001 refundido package; not all municipal planning or public works.',
    'Related figures not incorporated into the refundido are retained as references, not asserted to be invalid.',
    'Document update dates are not publication, agreement or approval dates.',
    'No verified project geometry or granted-licence register; publication_ready is false.',
    'Document URLs are inventoried; PDF/image contents are not parsed or geometrically referenced.',
]


def _date(value: str) -> str | None:
    if not re.fullmatch(r'\d{2}/\d{2}/\d{4}', value):
        return None
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    package = soup.find(id='divplaneamiento212')
    heading = package.find('h1') if package else None
    if (not heading or not heading.find('span')
            or heading.find('span').get_text(strip=True) != 'Zafra'
            or "Refundido vigente de la figura 'PGOU.R-001'" not in heading.get_text(' ', strip=True)):
        raise ValueError('SITEX no longer identifies the current Zafra PGOU package')
    files = soup.find(id='vistadeficherosrefundidos212')
    if package is None or files is None:
        raise ValueError('Missing SITEX document inventory')
    # This source is one static package, not the paginated regional search.
    # Refuse changed pagination instead of returning an incomplete first page.
    if package.select('.pagination, .paging, .paginator, a[rel="next"]'):
        raise ValueError('Unexpected pagination in current-plan package')
    figures = {}
    for row in package.find_all('tr'):
        label = row.find('th')
        if label and label.get_text(' ', strip=True) in ('Tenidas en cuenta', 'NO tenidas en cuenta'):
            incorporated = label.get_text(' ', strip=True) == 'Tenidas en cuenta'
            group = []
            for span in row.find_all('span', onclick=True):
                match = re.search(r'addTab\("(/SITEX/ptofiguras/viewsigcat/\d+)"', span['onclick'])
                if not match:
                    raise ValueError('Unrecognized related-figure link')
                group.append({'referencia': span.get_text(strip=True),
                              'url': urljoin(SOURCE, match[1])})
            figures['incorporadas' if incorporated else 'no_incorporadas'] = group
    if not figures.get('incorporadas') or 'no_incorporadas' not in figures:
        raise ValueError('Missing refundido inclusion/exclusion provenance')
    documents = {}
    for anchor in files.find_all('a', href=True):
        target = urljoin(SOURCE, anchor['href'])
        parsed = urlparse(target)
        if not parsed.path.startswith('/SITEX/downloads/archivos/'):
            continue  # "Mostrar hojas" toggles are not documents.
        if parsed.scheme != 'https' or parsed.hostname != 'sitex.juntaex.es':
            raise ValueError('Unexpected document host')
        # The official download endpoint encodes the source-relative filename.
        # Decode for provenance only; always retain the original download URL.
        try:
            relative = base64.b64decode(parsed.path.rsplit('/', 1)[-1], validate=True).decode('utf-8')
        except (ValueError, UnicodeError) as exc:
            raise ValueError('Unrecognized SITEX document path') from exc
        if not relative.startswith('planeamiento_escaneado_refundido/212/'):
            raise ValueError('Document belongs to another package')
        row = anchor.find_parent('tr')
        first_cell = row.find('td') if row else None
        updated = _date(first_cell.get_text(' ', strip=True)) if first_cell else None
        documents[target] = {
            'url': target, 'nombre': relative.rsplit('/', 1)[-1],
            'ruta_fuente': relative, 'fecha_actualizacion': updated,
            'source_url': SOURCE,
        }
    names = {doc['nombre'] for doc in documents.values()}
    if not {'NormativaRefundida.pdf', 'CatalogoRefundido.pdf'} <= names:
        raise ValueError('Missing normative or catalogue documents')
    return [{
        'id': 'zafra-sitex-refundido-212', 'municipio': 'Zafra',
        'codigo_ine': '06158', 'provincia': 'Badajoz',
        'titulo': heading.get_text(' ', strip=True),
        'tipo': 'Plan General de Ordenación Urbana (refundido)',
        'estado_fuente': 'Refundido vigente', 'referencia': 'PGOU.R-001',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': SOURCE, 'source': 'junta_extremadura', 'origen': 'sitex_planeamiento',
        'organismo_fuente': 'Junta de Extremadura — SITEX',
        'documentos': list(documents.values()), 'figuras_refundidas': figures,
        'descripcion': 'Inventario documental del refundido vigente del PGOU de Zafra. '
                       'La relación de modificaciones incorporadas y no incorporadas procede de SITEX.',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified instrument geometry extracted',
        'coverage': 'single_current_refundido_package', 'limitations': LIMITATIONS,
    }]


class ZafraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-zafra/1.0')
        }) as response:
            response.raise_for_status()
            if response.url != SOURCE:
                raise ValueError('Unexpected SITEX redirect')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 4_000_000:
                    raise ValueError('SITEX package exceeds response bound')
            html = content.decode('utf-8')
        rows = parse_inventory(html)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'sitex_refundido_live.html').write_bytes(content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'documents': len(rows[0]['documentos']), 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete replacement snapshot; never mark a partial page as incremental completion.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
