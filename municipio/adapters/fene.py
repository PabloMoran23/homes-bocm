"""Fene's municipal PXOM document inventory (one instrument, partial coverage)."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.fene.gal/portal-cidadan/pxom/gl'
LIMITATIONS = [
    'Partial coverage: only the municipal PXOM document inventory; excludes other instruments, works and licences.',
    'Publication and agreement/approval dates are absent from this inventory and remain null.',
    'Document links are retained as published; PDF/ZIP contents and legal currency are not interpreted.',
    'No verified geometry; no coordinates inferred from the municipality or map viewer.',
]


def parse_inventory(html: str | bytes) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('#Subheader h1.title')
    content = soup.select_one('#Content .sections_group')
    if not heading or heading.get_text(' ', strip=True) != 'PXOM' or not content:
        raise ValueError('Fene PXOM inventory structure missing')

    # The reviewed inventory is a single page. Refuse newly paginated responses
    # rather than silently retaining only the first page of an instrument.
    if soup.select_one('[rel~=next], .load_more'):
        raise ValueError('Pagination detected; review Fene inventory traversal')
    for pager in soup.select('.pager, .pagination, .pager_wrapper'):
        # The municipal template includes empty pager divs on this single page.
        if pager.get_text(strip=True) or pager.select_one('a[href], button, input'):
            raise ValueError('Pagination detected; review Fene inventory traversal')
    for a in content.select('a[href]'):
        label = (a.get_text(' ', strip=True) + ' ' + a.get('title', '')).lower().strip()
        if a['href'] not in ('', '#') and any(
            word in label for word in ('seguinte', 'siguiente', 'next', 'cargar máis', 'cargar más')
        ):
            raise ValueError('Continuation link detected in Fene inventory')

    documents = {}
    titles = content.select('h3.entry-title')
    for title_node in titles:
        a = title_node.select_one('a[href]')
        if not a:
            raise ValueError('Inventory document has no link')
        title = a.get_text(' ', strip=True)
        target = urljoin(SOURCE, a['href'])
        parsed = urlparse(target)
        if (not title or parsed.scheme != 'https' or parsed.hostname not in {'fene.gal', 'www.fene.gal'}
                or not parsed.path.startswith('/media/documentos/')
                or not parsed.path.lower().endswith(('.pdf', '.zip'))):
            raise ValueError('Unexpected document entry in Fene PXOM inventory')
        documents.setdefault(target, {
            'titulo': title, 'url': target, 'source_url': SOURCE,
            'href_original': a['href'],
        })
    labels = [d['titulo'].lower() for d in documents.values()]
    if ('memoria' not in labels or not any(t.startswith('normas urban') for t in labels)
            or not any(t.startswith('estudo económico') for t in labels)):
        raise ValueError('PXOM lacks its core planning documents')

    return [{
        'id': 'fene-pxom', 'municipio': 'Fene', 'codigo_ine': '15035',
        'provincia': 'A Coruña', 'titulo': 'PXOM de Fene',
        'tipo': 'planeamiento urbanístico', 'fase': None,
        'url': SOURCE, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
        'origen': 'inventario_documental_pxom',
        'descripcion': 'PXOM: documentación municipal de memoria, normas urbanísticas y estudios anexos.',
        'documentos': list(documents.values()),
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
        'limitations': list(LIMITATIONS),
    }]


class FeneAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.fene.gal')

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.get(SOURCE, timeout=30, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-fene/1.0'),
        }) as response:
            response.raise_for_status()
            if response.url != SOURCE or 'text/html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Unexpected response for Fene PXOM inventory')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 3_000_000:
                    raise ValueError('Fene inventory exceeds reviewed response bound')
            # The live page declares ISO-8859-1 in its meta charset, without an
            # HTTP charset. Let the HTML parser read that declaration.
            html = bytes(body)
        rows = parse_inventory(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'pxom.html').write_bytes(body)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'document_count': len(rows[0]['documentos']), 'limitations': list(LIMITATIONS),
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full current document snapshot, stable instrument identity; not an event feed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
