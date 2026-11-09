"""Arévalo's municipal planning document tabs, a partial documentary inventory."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://arevalo.es/servicios-municipales/urbanismo/normativa-tramitacion/'
LIMITATIONS = [
    'Solo inventario documental municipal Normativa tramitación; no incluye las 44 entradas del PLAU autonómico observadas en la investigación.',
    'La fase documental describe la versión enlazada, no el estado actual del expediente. PLAU contiene publicaciones posteriores para las modificaciones 27 y 28.',
    'Sin fechas de publicación o acuerdo verificadas en este inventario, sin geometría y sin registro de licencias concedidas.',
]
NUMBER = re.compile(r'modificaci[oó]n\s+puntual\s+n[.\sº°o]*\s*(\d+)\b', re.I)


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1')
    if not heading or 'normativa tramitación' not in ' '.join(heading.get_text().lower().split()):
        raise ValueError('Unexpected municipal inventory page')
    # This source currently has all tabs embedded in one response. Stop rather
    # than silently producing an incomplete snapshot if paging is introduced.
    if soup.select('a[rel~=next], .pagination, .nav-links, .pgd-pagination, [data-next-page]'):
        raise ValueError('Pagination introduced; traversal must be reviewed')
    panels = soup.select('.pgd-tabpanel')
    if not panels:
        raise ValueError('Municipal document panels missing')
    records = {}
    for panel in panels:
        label = soup.find(id=panel.get('aria-labelledby', ''))
        if label is None:
            raise ValueError('Document panel has no title')
        title = label.get_text(' ', strip=True)
        match = NUMBER.search(title)
        if not match:
            # Forms and unrelated material cannot become planning records.
            continue
        number = match[1]
        documents = []
        for anchor in panel.select('a.pgd-doc-link[href]'):
            name = anchor.select_one('.pgd-doc-name')
            if name is None:
                raise ValueError('Document title missing')
            name = name.get_text(' ', strip=True)
            doc_number = NUMBER.search(name)
            if not doc_number or doc_number[1] != number:
                raise ValueError('Document belongs to a different or unknown instrument')
            target = urljoin(url, anchor['href'])
            parsed = urlparse(target)
            if (parsed.scheme != 'https' or parsed.hostname != 'arevalo.es'
                    or not parsed.path.startswith('/wp-content/uploads/')
                    or not parsed.path.lower().endswith('.pdf')):
                raise ValueError('Unexpected municipal document URL')
            if not any(d['url'] == target for d in documents):
                documents.append({'titulo': name, 'url': target, 'source_url': url})
        if not documents:
            raise ValueError('Named instrument has no documents')
        if number in records:
            raise ValueError('Ambiguous duplicate instrument panels')
        phase = re.search(r'aprobación\s+(inicial|provisional|definitiva)', title, re.I)
        records[number] = {
            'id': f'arevalo-modificacion-puntual-{number}',
            'municipio': 'Arévalo', 'codigo_ine': '05016', 'provincia': 'Ávila',
            'titulo': title, 'tipo': 'modificación puntual de planeamiento',
            'numero_modificacion': number,
            'fase_documental': phase[0].lower() if phase else None,
            'estado_actual_verificado': False,
            'fecha_publicacion': None, 'fecha_acuerdo': None,
            'url': url, 'url_documento': documents[0]['url'], 'documentos': documents,
            'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
            'coverage': 'partial_municipal_document_inventory',
            'limitations': list(LIMITATIONS),
            'publication_ready': False, 'geometry_status': 'unavailable',
        }
    if not records:
        raise ValueError('No genuine named planning instruments found')
    return list(records.values())


class ArevaloAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='arevalo', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://arevalo.es')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-arevalo/1.0')})
        response.raise_for_status()
        if response.url != SOURCE:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory-live.html').write_text(response.text, encoding='utf-8')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE],
                'coverage': 'partial_municipal_document_inventory',
                'limitations': list(LIMITATIONS), 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full current documentary snapshot; state is deliberately not a cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
