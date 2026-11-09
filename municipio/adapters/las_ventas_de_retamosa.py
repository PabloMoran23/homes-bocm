"""Snapshot of the official municipal planning document inventory."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://lasventasderetamosa.es/obras-urbanismo/'
LIMITATIONS = [
    'Partial coverage: municipal Urbanismo document inventory only, not all municipal projects.',
    'No granted-licence register verified; application forms and procurement notices excluded.',
    'Inventory supplies no explicit publication/agreement dates or verified vector geometry.',
    'MEMORIAS Y NORMATIVA has modification annotations: excluded pending instrument identification.',
    'No claim that the posted NNSS documents constitute consolidated current planning law.',
]


def _norm(text: str) -> str:
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    return ' '.join(text.upper().split())


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    title = _norm(soup.title.get_text(' ', strip=True) if soup.title else '')
    if 'VENTAS DE RETAMOSA' not in title or 'URBANISMO' not in title:
        raise ValueError('Unexpected municipal inventory page')
    # This source is a single document list. Fail if it acquires pagination;
    # never interpret just the first page as a complete inventory snapshot.
    for a in soup.select('a[href]'):
        if ('next' in a.get('rel', []) or 'page-numbers' in a.get('class', [])
                or _norm(a.get_text(' ', strip=True)) in {'SIGUIENTE', 'NEXT', 'MOSTRAR MAS'}):
            raise ValueError('Inventory pagination requires explicit traversal')
    groups = {'nnss': {}, 'reparcelacion-poligono-5': {}}
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True)
        normalized = _norm(label)
        if normalized in {'NORMAS SUBSIDIARIAS', 'PLANO NNSS ORIGINAL'}:
            group = 'nnss'
        elif re.fullmatch(r'(PROYECTO )?REPARCELACION POLIGONO 5 - TOMO [12]', normalized):
            group = 'reparcelacion-poligono-5'
        else:
            continue
        url = urljoin(source_url, a['href'])
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or parsed.hostname != 'lasventasderetamosa.es'
                or not parsed.path.startswith('/wp-content/uploads/')
                or not parsed.path.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png'))):
            raise ValueError('Unexpected planning document URL: ' + url)
        groups[group][url] = {'titulo': label, 'url': url, 'inventory_url': source_url}
    if not all(groups.values()):
        raise ValueError('Expected named planning instruments missing from inventory')
    rows = []
    for key, documents in groups.items():
        is_nnss = key == 'nnss'
        docs = sorted(documents.values(), key=lambda d: d['url'])
        primary = next((d['url'] for d in docs if _norm(d['titulo']) == 'NORMAS SUBSIDIARIAS'), docs[0]['url'])
        rows.append({
            'id': 'las-ventas-de-retamosa-' + key,
            'municipio': 'Las Ventas de Retamosa', 'codigo_ine': '45183', 'provincia': 'Toledo',
            'titulo': ('Normas Subsidiarias de Planeamiento de Las Ventas de Retamosa' if is_nnss
                       else 'Proyecto de reparcelación del sector Polígono 5 de Las Ventas de Retamosa'),
            'tipo': 'normas subsidiarias de planeamiento' if is_nnss else 'proyecto de reparcelación',
            'url': source_url, 'inventory_url': source_url, 'url_documento': primary,
            'documentos': docs, 'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
            'descripcion': 'Documentación publicada por el Ayuntamiento; fase y vigencia no determinadas por el inventario.',
            'fase': None, 'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'No verified georeferenced geometry extracted; scanned plans are document links only',
            'coverage': 'partial_municipal_document_inventory',
        })
    return rows


class LasVentasDeRetamosaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://lasventasderetamosa.es')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=(10, 45), stream=True, headers={
            'User-Agent': 'municipio-las-ventas-de-retamosa/1.0',
        }) as response:
            response.raise_for_status()
            if response.url.rstrip('/') != SOURCE.rstrip('/'):
                raise ValueError('Unexpected inventory redirect')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 4_000_000:
                    raise ValueError('Inventory exceeds response size limit')
            rows = parse_inventory(content.decode('utf-8'))
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo-live.html').write_bytes(content)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temporary = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'partial_municipal_document_inventory', 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Refresh the complete bounded inventory, rather than appending duplicate tomes.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': LIMITATIONS[1]}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
