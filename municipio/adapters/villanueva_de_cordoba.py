"""Current official planning inventory; no inferred approvals or licence grants."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.villanuevadecordoba.com/w/servicios/urbanismo/'
DOCUMENT_HOSTS = {'www.juntadeandalucia.es', 'bop.dipucordoba.es',
                  'www.villanuevadecordoba.com'}
LIMITATIONS = [
    'Partial coverage: only the current static municipal Urbanismo inventory; no historical or news archive.',
    'Inventory presence does not establish current legal validity, execution or a licence grant.',
    'Dates are not exposed by the inventory and are left null; linked bulletins have their own publication and agreement dates.',
    'No verified geometry; no coordinates inferred. General ordinances and application forms excluded.',
]


def _key(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().rstrip('.').split())


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    content = BeautifulSoup(html, 'html.parser').select_one('.entry-content')
    if content is None or 'NORMAS' not in content.get_text(' ', strip=True).upper():
        raise ValueError('Municipal planning inventory missing or changed')
    # This source is a static document list. Refuse a newly paginated layout
    # rather than silently returning its first page.
    if content.select('.page-links, .pagination, a[rel~=next]'):
        raise ValueError('Inventory now paginated; traversal needs review')
    records = {}
    for a in content.select('a[href]'):
        title = ' '.join(a.get_text(' ', strip=True).split())
        if re.match(r'^Plan General de Ordenación Urbanística de Villanueva de Córdoba\b', title, re.I):
            kind = 'PGOU'
        elif re.match(r'^Avance de identificación y delimitación de asentamientos urbanísticos\b', title, re.I):
            kind = 'avance de planeamiento de asentamientos en suelo no urbanizable'
        else:
            continue
        original = urljoin(source_url, a['href'])
        parts = urlsplit(original)
        if parts.scheme not in ('http', 'https') or parts.hostname not in DOCUMENT_HOSTS:
            raise ValueError('Unexpected planning document host')
        if not parts.path.lower().endswith('.pdf'):
            raise ValueError('Planning inventory document is no longer a PDF')
        # Municipal inventory still links BOJA over HTTP; use its tested HTTPS equivalent.
        target = urlunsplit(('https', parts.netloc, parts.path, parts.query, ''))
        identity = _key(title)
        if identity not in records:
            records[identity] = {
                'id': 'villanueva-de-cordoba-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
                'municipio': 'Villanueva de Córdoba', 'provincia': 'Córdoba', 'codigo_ine': '14069',
                'titulo': title.rstrip('.'), 'tipo': kind, 'source': 'ayuntamiento',
                'origen': 'inventario_municipal_planeamiento', 'url': source_url,
                'inventory_url': source_url, 'url_documento': target, 'documentos': [],
                'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'fase': None, 'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'coverage': 'current_municipal_planning_inventory',
            }
        doc = {'titulo': title, 'url': target, 'url_inventario': original,
               'tipo': 'documento enlazado por el inventario municipal'}
        if not any(d['url'] == target for d in records[identity]['documentos']):
            records[identity]['documentos'].append(doc)
    if not records:
        raise ValueError('No usable named planning instruments in municipal inventory')
    return list(records.values())


class VillanuevaDeCordobaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        capture_dir = self.config.get('capture_dir')
        capture = Path(capture_dir) if capture_dir else None
        if capture:
            capture.mkdir(parents=True, exist_ok=True)
        source_urls = [SOURCE]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-villanueva-de-cordoba/1.0'
            response = session.get(SOURCE, timeout=45)
            response.raise_for_status()
            if response.url.rstrip('/') != SOURCE.rstrip('/'):
                raise ValueError('Unexpected inventory redirect')
            rows = parse_inventory(response.text)
            if capture:
                (capture / 'urbanismo.html').write_bytes(response.content)
            for row in rows:
                for index, doc in enumerate(row['documentos']):
                    result = session.get(doc['url'], timeout=60)
                    result.raise_for_status()
                    if urlsplit(result.url).hostname not in DOCUMENT_HOSTS or not result.content.startswith(b'%PDF-'):
                        raise ValueError('Linked planning document did not return an official PDF')
                    doc['url_final'] = result.url
                    doc['sha256'] = hashlib.sha256(result.content).hexdigest()
                    source_urls.append(doc['url'])
                    if capture:
                        (capture / f"{row['id']}-{index}.pdf").write_bytes(result.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': list(dict.fromkeys(source_urls)),
                'limitations': LIMITATIONS, 'coverage': 'current_municipal_planning_inventory'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Replace the full current snapshot; no incremental cursor exists here.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
