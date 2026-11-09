"""The official PEAU document inventory; one instrument, multiple documents.

This is partial municipal coverage, not a register of permissions or a statement
of the instrument's present legal status. Upload paths are never used as dates.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://baztanhobetzen.baztan.eus/baztan-hobetzen-cast/resultados/'
HOST = 'baztanhobetzen.baztan.eus'
LIMITATIONS = [
    'Cobertura parcial: únicamente el inventario documental del PEAU de los Cascos de Baztan.',
    'No incluye el Plan Municipal y sus modificaciones del listado municipal de 2021, ni obras o licencias.',
    'Las fases son etiquetas documentales; no acreditan el estado jurídico actual ni aprobación definitiva.',
    'Sin fechas de publicación, acuerdo o aprobación verificadas; sin geometría ni coordenadas.',
]


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    if urlparse(source_url).hostname != HOST:
        raise ValueError('Unexpected document inventory host')
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('article .entry-content')
    if content is None or 'PEAU de los Cascos de Baztan' not in content.get_text(' ', strip=True):
        raise ValueError('Missing identified PEAU inventory')
    # This is an unpaginated document page. Fail if that contract changes.
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if ('next' in a.get('rel', []) or
                (a in content.descendants and
                 (label in {'siguiente', 'next', 'hurrengoa', '»'} or
                  re.search(r'/page/\d+|[?&](?:page|paged)=\d+', a['href'])))):
            raise ValueError('Inventory pagination requires review; refusing partial output')
    if content.select('.pagination, .page-links, .nav-links'):
        raise ValueError('Inventory pagination requires review')

    documents = {}
    section = None
    for node in content.find_all(['p', 'h2', 'h3', 'h4', 'h5']):
        text = node.get_text(' ', strip=True)
        if not node.select('a[href]') and (text.startswith('FASE ') or text == 'Memoria del proceso participativo'):
            section = text
        for a in node.select('a[href]'):
            target = urldefrag(urljoin(source_url, a['href']))[0]
            parsed = urlparse(target)
            if not parsed.path.lower().endswith('.pdf'):
                continue
            if parsed.scheme != 'https' or parsed.hostname != HOST or not parsed.path.startswith('/wp-content/uploads/'):
                raise ValueError('Unexpected document provenance: ' + target)
            label = a.get_text(' ', strip=True)
            if not label or section is None:
                raise ValueError('Document lacks label or section')
            documents.setdefault(target, {'titulo': label, 'url': target,
                                          'source_url': source_url, 'seccion': section})
    labels = ' '.join(doc['titulo'].casefold() for doc in documents.values())
    if not all(word in labels for word in ('memoria informativa', 'memoria justificativa', 'normas urbanísticas', 'calificación')):
        raise ValueError('Incomplete or changed PEAU document inventory')
    return [{
        'id': 'baztan-peau-cascos', 'municipio': 'Baztan', 'codigo_ine': '31050',
        'provincia': 'Navarra', 'titulo': 'Plan Especial de Actuación Urbana de los Cascos de Baztan',
        'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
        'origen': 'inventario_documental_peau', 'url': source_url, 'inventory_url': source_url,
        'documentos': list(documents.values()), 'coverage': 'partial_single_instrument_document_inventory',
        'limitations': list(LIMITATIONS), 'geometry_status': 'unavailable', 'publication_ready': False,
    }]


def _write(path: Path, rows: list[dict]) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    temp.replace(path)
    return {'count': len(rows), 'written': len(rows)}


class BaztanAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'municipio-baztan/1.0 (public planning document inventory)'})
        response.raise_for_status()
        if urldefrag(response.url)[0].rstrip('/') != SOURCE.rstrip('/'):
            raise ValueError('Unexpected inventory redirect')
        if 'text/html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML inventory')
        rows = parse_inventory(response.text, response.url)
        capture_dir = self.config.get('evidence_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'live-documentacion.html').write_bytes(response.content)
        return {**_write(out_jsonl, rows), 'source_urls': [SOURCE],
                'coverage': 'partial_single_instrument_document_inventory',
                'limitations': list(LIMITATIONS), 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full replacement of this single inventory; no date watermark exists.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**_write(out_jsonl, []), 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
