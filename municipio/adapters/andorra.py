"""Andorra (Teruel): grouped instruments from the municipal PGOU inventory."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://andorraabierta.aytoandorra.es/informacion-institucional/pgou'
DOCUMENT_HOST = 'www.ayuntamientoandorra.es'
LIMITATIONS = [
    'Partial coverage: only instruments linked from the municipal PGOU inventory; '
    'not a complete historical register or an inventory of public works.',
    'Inventory labels and linked files do not establish current legal validity, '
    'approval dates or publication dates; Mod2(2008-07-30) is retained as a source label.',
    'No granted-licence register or verified project geometry; no geocoding.',
    'Document links are retained; live extraction does not download every PDF.',
]


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('[role="main"]')
    if main is None or 'Ayuntamiento de Andorra (Teruel)' not in main.get_text(' ', strip=True):
        raise ValueError('Missing Andorra (Teruel) inventory identity')
    heading = main.find('h1')
    if heading is None or heading.get_text(' ', strip=True) != 'PLAN GENERAL DE ORDENACIÓN URBANA':
        raise ValueError('Missing PGOU inventory heading')
    # The verified source is one unpaginated page. Fail if it gains pagination,
    # rather than quietly treating its first page as a complete snapshot.
    for a in soup.select('a[href]'):
        if 'next' in a.get('rel', []) or re.search(
            r'^(siguiente|next|cargar más|ver más)$', a.get_text(' ', strip=True), re.I
        ) or re.search(r'[?&](page|pagina|offset)=', a['href'], re.I):
            raise ValueError('Inventory pagination needs explicit traversal')

    groups = {}
    section = None
    # Google Sites puts document sections outside its title's role=main.
    for node in soup.find_all(['h2', 'h3', 'p']):
        text = node.get_text(' ', strip=True)
        if node.name in ('h2', 'h3'):
            match = re.fullmatch(r'MODIFICACIÓN PUNTUAL Nº\s*(\d+)', text)
            section = ('mod-' + match[1], text) if match else None
            continue
        links = []
        for a in node.select('a[href]'):
            target = urljoin(source_url, a['href'])
            parts = urlsplit(target)
            if not parts.path.lower().endswith('.pdf'):
                continue
            if parts.hostname != DOCUMENT_HOST or not parts.path.startswith('/wp-content/uploads/'):
                raise ValueError('Unexpected planning document origin: ' + target)
            # Old municipal links use HTTP; same-host HTTPS has been verified.
            secure = urlunsplit(('https', parts.netloc, parts.path, parts.query, ''))
            links.append((target, secure, a.get_text(' ', strip=True)))
        if not links:
            continue
        if section:
            key, title = section
        elif 'Mod2' in text or 'MOD2' in text:
            key = 'mod-2'
            label = re.search(r'Mod2\s*\([^)]*\)', text, re.I)
            if not label:
                raise ValueError('Unrecognized modification 2 label')
            title = 'Modificación 2 del PGOU de Andorra — ' + label[0]
        elif re.search(r'PGO[CU]*U?\s*2007', text, re.I):
            key, title = 'pgou-2007', heading.get_text(' ', strip=True) + ' de Andorra (2007)'
        else:
            raise ValueError('Ungrouped planning documents: ' + text)
        group = groups.setdefault(key, {'titulo': title, 'documents': {}, 'labels': []})
        if text not in group['labels']:
            group['labels'].append(text)
        for original, secure, anchor_label in links:
            if key != 'pgou-2007' and anchor_label == 'PGOU 2007':
                # Cross-reference to the base plan grid, already retained there.
                continue
            document = group['documents'].setdefault(secure, {
                'url': secure, 'source_url': original, 'source_labels': [],
                'inventory_url': source_url,
            })
            if text not in document['source_labels']:
                document['source_labels'].append(text)
    if not groups or 'pgou-2007' not in groups:
        raise ValueError('No documented PGOU instrument found')
    records = []
    for key, group in groups.items():
        records.append({
            'id': 'andorra-plan-' + hashlib.sha256((SOURCE + '#' + key).encode()).hexdigest()[:16],
            'municipio': 'Andorra', 'provincia': 'Teruel', 'codigo_ine': '44025',
            'titulo': group['titulo'],
            'tipo': 'plan general' if key == 'pgou-2007' else 'modificación de planeamiento',
            'url': source_url, 'inventory_url': source_url, 'source': 'ayuntamiento',
            'origen': 'inventario_planeamiento_municipal',
            'documentos': list(group['documents'].values()),
            'descripcion': '\n'.join(group['labels']),
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'fase': None, 'lat': None, 'lon': None,
            'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False, 'coverage': 'partial_current_document_inventory',
        })
    return records


class AndorraAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'municipio-andorra/1.0 (public planning inventory)',
        })
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE or 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Unexpected municipal inventory response')
        rows = parse_inventory(response.text, response.url)
        if self.config.get('capture_dir'):
            captures = Path(self.config['capture_dir'])
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'pgou-inventory.html').write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
