"""Ceutí's single-page municipal planning document inventory.

Records represent instruments, never individual downloads or licence forms.
Dates and legal status are not inferred from document names/upload directories.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://ceuti.es/urbanismo/'
LIMITATIONS = [
    'Partial coverage: only the current single-page municipal Urbanismo inventory; not a historical register.',
    'Dates and approval status are not extracted from linked PDFs; upload paths and page modification dates are not instrument dates.',
    'No verified geometry or coordinates; publication_ready is false.',
    'No public granted-licence register verified; licence extraction is disabled.',
]


def _norm(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().upper().split())


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.post-content')
    if content is None:
        raise ValueError('Missing municipal inventory content')
    # This source is a single page, not a paginated search. Stop if that changes.
    if soup.select('a[rel~=next], .pagination, .page-numbers, .nav-links'):
        raise ValueError('Pagination detected; source requires a new traversal implementation')
    headings = {_norm(h.get_text(' ', strip=True)) for h in content.find_all('h2')}
    if not {'URBANISMO', 'PGMO', 'AVANCE MODIFICACION PUNTUAL IX PGMO'} <= headings:
        raise ValueError('Expected planning sections missing')
    groups: dict[str, list[dict]] = {}
    titles = {
        'pgmo': 'Plan General Municipal de Ordenación de Ceutí (PGMO)',
        'mp-i': 'Modificación puntual I del PGMO de Ceutí',
        'mp-ii': 'Modificación puntual II del PGMO de Ceutí',
        'mp-ix': 'Avance de la modificación puntual IX del PGMO de Ceutí',
        'plan-parcial': 'Plan parcial, usos y destinos del suelo — PGMO de Ceutí',
    }
    for anchor in content.select('a[href]'):
        heading = anchor.find_previous('h2')
        section = _norm(heading.get_text(' ', strip=True)) if heading else ''
        label = anchor.get_text(' ', strip=True)
        normalized = _norm(label)
        if section not in {'PGMO', 'AVANCE MODIFICACION PUNTUAL IX PGMO'}:
            continue
        if section.startswith('AVANCE'):
            if normalized == 'MODELO SOLICITUD INICIO EVALUACION AMBIENTAL':
                continue  # Blank application form, not a project document.
            key = 'mp-ix'
        elif normalized.startswith('PLAN PARCIAL, USOS Y DESTINOS'):
            key = 'plan-parcial'
        elif 'MODIFICACION 2' in normalized:
            key = 'mp-ii'
        elif 'MOD_PUNTUAL_I' in normalized or 'MODIFICACION PUNTUAL I DEL PGMO' in normalized:
            key = 'mp-i'
        elif normalized in {'NORMAS URBANISTICAS', 'PLANO GENERAL'} or normalized.startswith('ORDENACION ESTRUCTURAL MODIFICADA'):
            key = 'pgmo'
        else:
            raise ValueError(f'Unclassified planning document: {label}')
        target = urljoin(source_url, anchor['href'])
        parsed = urlsplit(target)
        if parsed.scheme != 'https' or parsed.hostname not in {'ceuti.es', 'www.ceuti.es'} or not parsed.path.lower().endswith('.pdf'):
            raise ValueError(f'Unexpected planning document URL: {target}')
        docs = groups.setdefault(key, [])
        if not any(d['url'] == target for d in docs):
            docs.append({'titulo': label, 'url': target, 'inventory_url': source_url})
    if set(groups) != set(titles):
        raise ValueError('Incomplete or changed planning inventory')
    if any(len(groups[k]) < n for k, n in {'pgmo': 2, 'mp-i': 2, 'mp-ii': 2, 'mp-ix': 4, 'plan-parcial': 1}.items()):
        raise ValueError('Expected instrument documents missing')
    return [{
        'id': 'ceuti-plan-' + key, 'municipio': 'Ceutí', 'codigo_ine': '30018',
        'provincia': 'Murcia', 'titulo': titles[key],
        'tipo': 'instrumento de planeamiento', 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': source_url, 'url_documento': docs[0]['url'], 'documentos': docs,
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
        'descripcion': 'Documentación agrupada del inventario municipal: ' + '; '.join(d['titulo'] for d in docs),
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'unavailable', 'coverage': 'current_document_inventory',
    } for key, docs in sorted(groups.items())]


class CeutiAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://ceuti.es')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-ceuti/1.0'),
        }) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname not in {'ceuti.es', 'www.ceuti.es'} or urlsplit(response.url).path.rstrip('/') != '/urbanismo':
                raise ValueError('Unexpected inventory redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Inventory exceeds 3 MB limit')
                chunks.append(chunk)
            payload = b''.join(chunks)
            html = payload.decode('utf-8-sig')
            rows = parse_inventory(html, response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo-live.html').write_bytes(payload)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(output)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)  # Complete current snapshot, no date cursor.

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': LIMITATIONS[-1]}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
