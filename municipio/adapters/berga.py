"""Berga's official POUM document inventory; one instrument, many documents."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

LANDING = 'https://ajberga.cat/pla-dordenacio-urbanistica-municipal-de-berga-poum'
SOURCE = 'https://ajberga.cat/media/import/poum/poum/index.htm'
TITLE = "Pla d'Ordenació Urbanística Municipal de Berga (POUM)"
LIMITATIONS = [
    'Partial coverage: municipal base POUM archive only; later amendments and other projects are not inventoried.',
    'PDF links retained as components of one plan, not separate approved projects; individual PDF availability is not checked by the adapter.',
    'DOGC date is publication, not agreement or approval; agreement and approval dates are not extracted from PDFs.',
    'No verified geometry or coordinates; no granted-licence register extracted.',
]


def parse_projects(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    text = ' '.join(soup.get_text(' ', strip=True).split())
    if "PLA D'ORDENACIÓ URBANÍSTICA MUNICIPAL DE BERGA" not in text.upper():
        raise ValueError('Missing Berga plan heading')
    # This archive is a single HTML inventory. Fail on new navigation/continuations
    # instead of silently ignoring a newly paginated or restructured inventory.
    if soup.select('[rel~=next], iframe, frame, form'):
        raise ValueError('Unexpected continuation or interactive inventory')
    documents = {}
    publication_dates = set()
    approval_documents = []
    for anchor in soup.select('a[href]'):
        href = anchor['href'].strip()
        if href.startswith('#'):
            continue
        target = urljoin(SOURCE, href)
        parsed = urlsplit(target)
        if (parsed.scheme != 'https' or parsed.netloc != 'ajberga.cat'
                or not parsed.path.startswith('/media/import/poum/poum/')
                or not parsed.path.lower().endswith('.pdf') or parsed.query or parsed.fragment):
            raise ValueError(f'Unexpected archive link; review coverage: {target}')
        label = ' '.join(anchor.get_text(' ', strip=True).split())
        row = anchor.find_parent('tr')
        context = ' '.join(row.get_text(' ', strip=True).split()) if row else label
        documents.setdefault(target, {
            'url': target, 'titulo': label or parsed.path.rsplit('/', 1)[-1],
            'contexto_fuente': context, 'inventory_url': SOURCE,
        })
        if 'APROVACIÓ DEFINITIVA' in label.upper() and 'DOGC' in label.upper():
            approval_documents.append(target)
            match = re.search(r'DOGC\s+(\d+)\s*-\s*(\d{2}/\d{2}/\d{4})', label, re.I)
            if match:
                publication_dates.add(datetime.strptime(match[2], '%d/%m/%Y').date().isoformat())
    paths = [urlsplit(u).path for u in documents]
    if not approval_documents or not all(any('/' + part + '/' in p for p in paths)
                                         for part in ('memoria', 'normes', 'planols', 'fitxes')):
        raise ValueError('Incomplete POUM inventory: missing approval notice or document sections')
    if len(set(approval_documents)) != 1 or len(publication_dates) > 1:
        raise ValueError('Ambiguous POUM publication notices')
    return [{
        'id': 'berga-poum-' + hashlib.sha256(SOURCE.encode()).hexdigest()[:16],
        'municipio': 'Berga', 'provincia': 'Barcelona', 'codigo_ine': '08022',
        'titulo': TITLE, 'tipo': 'POUM', 'fase': 'aprobación definitiva',
        'fecha': None, 'fecha_publicacion': next(iter(publication_dates), None),
        'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': LANDING, 'inventory_url': SOURCE, 'url_documento': approval_documents[0],
        'documentos': list(documents.values()),
        'source': 'ayuntamiento', 'origen': 'inventario_documental_poum',
        'descripcion': 'Inventario municipal del POUM: memoria, fichas, normas y planos; documentos agrupados en un único instrumento.',
        'date_provenance': {'fecha_publicacion': {'url': SOURCE, 'label': 'DOGC publication notice'}},
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'unavailable', 'coverage': 'base_poum_document_inventory',
        'limitations': LIMITATIONS.copy(),
    }]


class BergaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://ajberga.cat')

    def _fetch(self, url: str, name: str) -> tuple[str, dict]:
        with requests.get(url, timeout=30, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-berga/1.0'),
        }) as response:
            response.raise_for_status()
            if response.url != url or 'text/html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Unexpected official source redirect or content type')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 2_000_000:
                    raise ValueError('Inventory exceeds response size limit; extraction aborted')
            raw = bytes(data)
            # Legacy archive explicitly declares ISO-8859-1 in its HTML.
            encoding = 'iso-8859-1' if b'charset=iso-8859-1' in raw.lower() else 'utf-8'
            capture = self.config.get('evidence_dir')
            if capture:
                directory = Path(capture)
                directory.mkdir(parents=True, exist_ok=True)
                (directory / name).write_bytes(raw)
            return raw.decode(encoding), {
                'url': url, 'sha256': hashlib.sha256(raw).hexdigest(),
                'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'capture': name if capture else None,
            }

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        landing, landing_provenance = self._fetch(LANDING, 'poum-landing-live.html')
        links = BeautifulSoup(landing, 'html.parser').select('a[href]')
        if SOURCE not in {urljoin(LANDING, a['href']) for a in links}:
            raise ValueError('Official POUM landing page no longer links the archive')
        html, provenance = self._fetch(SOURCE, 'poum-index-live.html')
        rows = parse_projects(html)
        for row in rows:
            row['source_provenance'] = [landing_provenance, provenance]
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [LANDING, SOURCE],
                'documents': len(rows[0]['documentos']), 'publication_ready': False,
                'limitations': LIMITATIONS.copy()}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete single-instrument snapshot; no timestamp cursor or page cap.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
