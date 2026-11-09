"""Herrera's official transparency inventory of PGOU modifications.

One record per instrument, not per drawing or announcement. No claim of
current legal validity, granted licences, approval dates or spatial accuracy.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE_URL = (
    'https://transparencia.herrera.es/es/transparencia/indicadores-de-transparencia/'
    'indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00019/'
)
LIMITATIONS = [
    'Partial coverage: only PGOU modifications in the municipal transparency inventory; '
    'not the complete PGOU, PBOM, works or licence registers.',
    'Document availability does not establish approval, legal validity or execution.',
    'No publication/agreement dates or coordinates inferred; PDF contents not parsed.',
]


def parse_inventory(html: str, source_url: str = SOURCE_URL) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    # This inventory has no observed pagination. Fail if the CMS adds it,
    # rather than silently treating page one as the complete inventory.
    if soup.select('.pagination, .pager, a[rel~=next], [data-next-page]'):
        raise ValueError('Pagination detected; inventory traversal must be reviewed')
    for anchor in soup.select('a[href]'):
        label = anchor.get('aria-label') or anchor.get_text(' ', strip=True)
        if re.fullmatch(r'(siguiente(?: página)?|next(?: page)?|[»›])', label, re.I):
            raise ValueError('Pagination detected; inventory traversal must be reviewed')
    galleries = soup.select('section.gallery.link-gallery')
    if not galleries:
        raise ValueError('Missing municipal document galleries')
    records = {}
    for gallery in galleries:
        heading = gallery.select_one('h4.gallery-title')
        if heading is None:
            raise ValueError('Document gallery without instrument heading')
        title = heading.get_text(' ', strip=True)
        match = re.fullmatch(r'(\d+)\s*[ªºa.]?\s*MODIFICACI[ÓO]N\s+PGOU', title, re.I)
        if not match:
            raise ValueError(f'Unrecognized instrument gallery: {title}')
        number = str(int(match.group(1)))
        docs = {}
        for anchor in gallery.select('a[href]'):
            target = urljoin(source_url, anchor['href'])
            parsed = urlparse(target)
            if not parsed.path.lower().endswith('.pdf'):
                continue
            expected = f'/export/sites/herrera/es/transparencia/.galleries/IND-50-/MODIFICACION-{number}-PGOU/'
            if (parsed.scheme != 'https' or parsed.hostname != 'transparencia.herrera.es'
                    or not parsed.path.startswith(expected)):
                raise ValueError(f'Document outside instrument provenance: {target}')
            docs.setdefault(target, {
                'titulo': anchor.get_text(' ', strip=True) or anchor.get('title', ''),
                'url': target, 'source_url': source_url,
            })
        if not docs:
            raise ValueError(f'Instrument lacks PDF documents: {title}')
        if number in records:
            raise ValueError(f'Duplicate instrument gallery: {number}')
        records[number] = {
            'id': f'herrera-pgou-modificacion-{number}',
            'municipio': 'Herrera', 'provincia': 'Sevilla', 'codigo_ine': '41050',
            'titulo': title, 'tipo': 'planeamiento_urbanistico',
            'url': source_url, 'inventory_url': source_url,
            'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
            'documentos': list(docs.values()),
            'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'partial_pgou_modification_inventory',
        }
    if not records:
        raise ValueError('No planning instruments found')
    return list(records.values())


class HerreraAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE_URL, timeout=(10, 40), headers={
            'User-Agent': 'municipio-herrera-inventory/1.0',
        })
        response.raise_for_status()
        if response.url != SOURCE_URL:
            raise ValueError(f'Unexpected inventory redirect: {response.url}')
        rows = parse_inventory(response.text)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            captures = Path(capture_dir)
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'inventory-live.html').write_text(response.text, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {
            'count': len(rows), 'written': len(rows), 'live_records': len(rows),
            'source_urls': [SOURCE_URL], 'limitations': LIMITATIONS,
            'documents': sum(len(row['documentos']) for row in rows),
        }

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                     for row in rows), encoding='utf-8')
        temporary.replace(output)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Reconcile the complete current inventory; no date-based watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
