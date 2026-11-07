"""The municipal PGOU document inventory, grouped as one planning instrument."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.ayto-salobrena.es/web/plan-general-de-ordenacion-urbana-2001/'
TITLE = 'Plan General de Ordenación Urbana 2001'
HOST = 'www.ayto-salobrena.es'
SECTIONS = (
    'Plan General de Ordenación Urbana completo (archivo comprimido zip)',
    'Documentación textual (archivos pdf)',
    'Fichas de condiciones urbanísticas (archivos pdf)',
    'Planimetría (archivos pdf)',
)
LIMITATIONS = [
    'Partial coverage: only the currently published PGOU 2001 document inventory; '
    'not a complete register of planning amendments, projects or public works.',
    'No verified approval, agreement or publication dates, current legal validity or project geometry.',
    'Document links retained as published; linked file contents are not parsed or all downloaded.',
    'No verified public register of granted licences; licences disabled.',
]


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    posts = [p for p in soup.select('div.post')
             if p.find('h2') and p.find('h2').get_text(' ', strip=True) == TITLE]
    if len(posts) != 1:
        raise ValueError('Expected exactly one municipal PGOU inventory')
    entry = posts[0].select_one('div.entry')
    if entry is None:
        raise ValueError('Missing PGOU document body')
    # Head rel=next on this old WordPress site means an unrelated sibling page.
    # Body pagination, however, must never be silently treated as a full snapshot.
    if (soup.select('.pagination, .page-links, .page-numbers, .post-navigation')
            or entry.select('a[rel~=next], a.next, nav')
            or any('/page/' in a['href'] or '?page=' in a['href']
                   or '?paged=' in a['href'] for a in entry.select('a[href]'))):
        raise ValueError('Unexpected pagination: inventory coverage needs review')
    sections = []
    documents = []
    seen = set()
    group = None
    for node in entry.find_all(['h4', 'a']):
        if node.name == 'h4':
            group = node.get_text(' ', strip=True)
            if group not in SECTIONS:
                raise ValueError('Unexpected PGOU document section')
            sections.append(group)
            continue
        url = urljoin(source_url, node.get('href', ''))
        parsed = urlparse(url)
        title = node.get_text(' ', strip=True)
        suffix = Path(parsed.path).suffix.lower()
        if (group is None or not title or parsed.scheme not in ('http', 'https')
                or parsed.hostname != HOST
                or not parsed.path.startswith('/web/wp-content/uploads/')
                or suffix not in ('.pdf', '.zip')):
            raise ValueError('Unexpected link in PGOU inventory; refusing partial extraction')
        if url not in seen:
            documents.append({'titulo': title, 'url': url, 'seccion': group,
                              'formato': suffix[1:], 'source_url': source_url})
            seen.add(url)
    if tuple(sections) != SECTIONS or any(
            not any(d['seccion'] == section for d in documents) for section in SECTIONS):
        raise ValueError('Incomplete PGOU inventory')
    if not any(d['formato'] == 'zip' for d in documents):
        raise ValueError('Missing complete plan archive')
    return [{
        'id': 'salobrena-pgou-2001', 'municipio': 'Salobreña',
        'codigo_ine': '18173', 'provincia': 'Granada', 'titulo': TITLE,
        'tipo': 'Plan General de Ordenación Urbana',
        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
        'url': source_url, 'inventory_url': source_url, 'documentos': documents,
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'single_instrument_document_inventory',
        'limitations': LIMITATIONS.copy(),
    }]


class SalobrenaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'})
        response.raise_for_status()
        if response.url != SOURCE or 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Unexpected municipal inventory response')
        response.encoding = 'utf-8'
        rows = parse_inventory(response.text, response.url)
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'pgou.html').write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                  for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows),
                'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': [SOURCE], 'limitations': LIMITATIONS.copy(),
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete refresh of a single instrument; no incremental date assumptions.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        raise NotImplementedError('Licences disabled: no verified granted-licence register')

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
