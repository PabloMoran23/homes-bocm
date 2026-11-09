"""Monesterio's published municipal planning-document inventory (partial coverage)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://monesterio.es/plantilla.php?enlace=normativa'


def _normal(text):
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    panels = [p for p in soup.select('.contenidop')
              if p.select_one('#titulo') and p.select_one('#titulo').get_text(strip=True) == 'NORMATIVA']
    if len(panels) != 1 or 'Ayuntamiento de Monesterio' not in panels[0].get_text(' ', strip=True):
        raise ValueError('Missing or ambiguous Monesterio Normativa panel')
    panel = panels[0]
    # The verified source is one unpaginated inventory. Fail on newly introduced
    # pagination rather than silently return only its first page.
    if soup.select('.pagination, .paginacion, a[rel~=next], a[rel~=prev]'):
        raise ValueError('Pagination introduced; inventory traversal needs review')
    for a in panel.select('a[href]'):
        if re.search(r'(?:pagina|page|offset|start)=', a['href'], re.I) or _normal(a.get_text()) in {'siguiente', 'next', 'anterior'}:
            raise ValueError('Pagination introduced; inventory traversal needs review')
    groups = {}
    for a in panel.select('a[href]'):
        title = ' '.join(a.get_text(' ', strip=True).split())
        norm = _normal(title)
        if not re.match(r'^(?:aprobacion modificacion puntual \d+ de las normas subsidiarias|normas subsidiarias de planeamiento municipal|plan general municipal de monesterio)(?:\b|$)', norm):
            continue
        target = urljoin(SOURCE, a['href'])
        parsed = urlparse(target)
        if parsed.scheme != 'https' or parsed.netloc != 'monesterio.es' or not re.fullmatch(r'/documentos/[^/]+\.pdf', parsed.path, re.I) or parsed.query:
            raise ValueError('Unexpected planning document URL')
        block = a.parent
        text = block.get_text(' ', strip=True)
        match = re.search(r'Fecha de Alta:\s*(\d{2}/\d{2}/\d{4})', text)
        alta = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None
        description = text.split('Descripción:', 1)[1].strip() if 'Descripción:' in text else None
        # Each named instrument is one record; repeated document entries retain
        # their own metadata and links, without conflating a modification and NNSS.
        key = norm
        if key not in groups:
            groups[key] = {
                'id': 'monesterio-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Monesterio', 'codigo_ine': '06085', 'provincia': 'Badajoz',
                'titulo': title, 'tipo': 'instrumento de planeamiento',
                'url': SOURCE, 'inventory_url': SOURCE, 'url_documento': target,
                'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None, 'documentos': [],
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'geometry_status': 'unavailable',
                'coverage': 'Published municipal inventory; historical documents, legal validity not determined',
            }
        document = {'url': target, 'titulo': title, 'descripcion': description,
                    'fecha_alta_portal': alta, 'source_url': SOURCE}
        if document not in groups[key]['documentos']:
            groups[key]['documentos'].append(document)
    if not groups:
        raise ValueError('No named planning instruments in municipal inventory')
    return list(groups.values())


class MonesterioAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://monesterio.es')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=30, stream=True,
                          headers={'User-Agent': 'municipio-monesterio/1.0'}) as response:
            response.raise_for_status()
            if response.url != SOURCE:
                raise ValueError('Unexpected inventory redirect')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 2_000_000:
                    raise ValueError('Inventory exceeds 2 MB; refusing partial extraction')
            html = body.decode(response.encoding or 'utf-8')
        rows = parse_inventory(html)
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'normativa.html').write_bytes(body)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'complete single-page Normativa inventory; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'Application forms are not granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
