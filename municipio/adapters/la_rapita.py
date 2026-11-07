"""Public municipal POUM inventory; intentionally partial planning coverage."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://seu.larapita.cat'
SOURCE = BASE + '/urbanismeCategoriaPublic/listPublicacionsAmbCategoria?categoria.id=5&multiseu='
LIMITATIONS = [
    'Only the base POUM published in municipal category 5; later amendments, works and licences are not covered.',
    'Document links retained from the inventory; PDF contents and availability are not verified.',
    'No verified geometry or coordinates; publication_ready is false.',
    'Municipal TLS certificate expired at verification; explicit endpoint-only TLS exception required.',
]


def _numeric_date(text: str) -> str | None:
    m = re.search(r'\b(\d{2})[./](\d{2})[./](\d{4})\b', text)
    return date(int(m[3]), int(m[2]), int(m[1])).isoformat() if m else None


def parse_projects(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1')
    if not heading or 'La Ràpita' not in heading.get_text(' ', strip=True):
        raise ValueError('Missing municipal identity')
    listing = soup.select_one('.llistatAnuncisUrbanisme')
    count = listing.select_one('.resultatsLlistat') if listing else None
    blocks = listing.select('.dElementPublicacioDefecte') if listing else []
    # Narrow, complete base-plan snapshot. A changed count or pagination is an
    # explicit error, never a silently truncated archive.
    if not count or not re.fullmatch(r'1 publicació', count.get_text(' ', strip=True)) or len(blocks) != 1:
        raise ValueError('Expected complete single-POUM inventory; source scope changed')
    if any(node.get_text(strip=True) or node.select('a[href], button, input')
           or node.get('href') for node in listing.select('.pagination, .paginateButtons, a[rel="next"]')):
        raise ValueError('Unexpected pagination in single-plan inventory')
    block = blocks[0]
    title = block.select_one('.titol')
    narrative = block.select_one('.top')
    register = block.select_one('a.registreLink')
    if (not title or title.get_text(strip=True) != 'POUM' or not narrative or not register
            or not re.fullmatch(r'/registrePublic/registrePublicacio/\d+', register.get('href', ''))):
        raise ValueError('Missing POUM provenance')
    description = narrative.get_text(' ', strip=True)
    if not re.search(r"Pla d.Ordenació Urbana Municipal", description):
        raise ValueError('Not a planning instrument')
    documents = []
    for a in block.select('.documentsAdjunts a[href]'):
        if not re.fullmatch(r'/documentPublic/download/\d+', a['href']):
            raise ValueError('Unexpected document provenance')
        link = urljoin(BASE, a['href'])
        if link not in {d['url'] for d in documents}:
            documents.append({'titulo': a.get_text(' ', strip=True), 'url': link, 'source_url': SOURCE})
    if not documents:
        raise ValueError('POUM has no supporting documents')
    approvals = {}
    for p in narrative.select('p'):
        text = p.get_text(' ', strip=True)
        for stage in ('inicial', 'provisional', 'definitiva'):
            if text.startswith('Aprovació ' + stage + ':'):
                approvals[stage] = _numeric_date(text)
    pub = re.search(r'DOGC de (\d{1,2}) de maig de (\d{4})', description)
    # Only the explicit DOGC phrase supplies publication, never the earlier
    # publication-register timestamp or the extraction time.
    publication = date(int(pub[2]), 5, int(pub[1])).isoformat() if pub else None
    timestamp = register.parent.get_text(' ', strip=True)
    registry_url = urljoin(BASE, register['href'])
    return [{
        'id': 'la-rapita-poum-' + register['href'].rsplit('/', 1)[-1],
        'municipio': 'La Ràpita', 'provincia': 'Tarragona', 'codigo_ine': '43136',
        'titulo': 'Pla d’Ordenació Urbana Municipal (POUM) de La Ràpita',
        'tipo': 'POUM', 'fase': 'aprobación definitiva' if approvals.get('definitiva') else None,
        'fecha': None, 'fecha_publicacion': publication,
        'fecha_aprob': approvals.get('definitiva'), 'fecha_acuerdo': approvals.get('definitiva'),
        'fecha_aprobacion_inicial': approvals.get('inicial'),
        'fecha_aprobacion_provisional': approvals.get('provisional'),
        'fecha_registro_publicacion': _numeric_date(timestamp),
        'registro_publicacion_texto': timestamp,
        'descripcion': description, 'url': SOURCE, 'url_registro': registry_url,
        'url_documento': documents[0]['url'], 'documentos': documents,
        'source': 'ayuntamiento', 'origen': 'planejament_municipal',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'coverage': 'base POUM only, not a consolidated inventory of amendments',
    }]


class LaRapitaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        # This exception is explicit in the manifest and only applies to this
        # fixed public endpoint. Redirects are refused, including host changes.
        verify = not self.config.get('allow_expired_certificate', False)
        with requests.get(SOURCE, timeout=(10, 40), stream=True, allow_redirects=False,
                          verify=verify, headers={'User-Agent': 'municipio-la-rapita/1.0'}) as response:
            if response.status_code != 200:
                raise ValueError(f'POUM inventory HTTP {response.status_code}')
            if 'text/html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Expected HTML inventory')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 2_000_000:
                    raise ValueError('Inventory exceeds 2 MB; response not truncated')
        html = bytes(data).decode('utf-8')
        rows = parse_projects(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'planejament.html').write_bytes(data)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'tls_verified': verify, 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
