"""Snapshot of Cabrera de Mar's official current-planning inventory."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.cabrerademar.cat'
SOURCE = BASE + '/ajuntament/normativa/179-urbanisme/planejament-vigent'
LIMITATIONS = [
    'Partial municipal coverage: current-planning inventory only; excludes public-exhibition inventory, works, licences and acoustic map.',
    'Vigente is the municipal inventory classification, not an independently verified approval agreement.',
    'Approval/agreement/publication dates are not extracted from PDFs; page update dates are separate metadata.',
    'Document and RPUC links are retained as provenance; linked PDF contents and RPUC dossiers are not parsed.',
    'No verified geometry or coordinates; publication_ready=false.',
]


def parse_page(html: str, url: str) -> tuple[list[str], dict | None]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#readspeakerPage')
    if content is None or content.select_one('h1') is None:
        raise ValueError('Missing municipal planning content: ' + url)
    # Fail explicitly if the reviewed tree becomes a paginated inventory.
    if soup.select('.pagination, .paginator, .pager, a[rel~=next]'):
        raise ValueError('Pagination detected; inventory traversal must be reviewed')
    for a in content.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'següent', 'següents', 'siguiente', 'next', '›', '»'}:
            raise ValueError('Pagination detected')
    children = set()
    for a in content.select('.widgetMenu a[href]'):
        target = urljoin(url, a['href'])
        path = urlsplit(target)
        if path.netloc == urlsplit(BASE).netloc and path.path.startswith(urlsplit(url).path.rstrip('/') + '/'):
            if path.query or path.fragment:
                raise ValueError('Unexpected inventory child URL: ' + target)
            if path.path == urlsplit(SOURCE).path + '/mapa-de-soroll-i-capacitat-acustica':
                continue
            children.add(target.rstrip('/'))
    if children:
        return sorted(children), None
    title = content.h1.get_text(' ', strip=True)
    if not (title == 'POUM' or re.match(r'^(modificació puntual|pla especial|pla de millora urbana)\b', title, re.I)):
        raise ValueError('Unsupported or empty planning category: ' + title)
    docs = {}
    for a in soup.select('#page-documents a[href], #page-links a[href], #readspeakerPage .widgetMenu a[href]'):
        target = urljoin(url, a['href'])
        parts = urlsplit(target)
        is_doc = parts.scheme == 'https' and parts.netloc == urlsplit(BASE).netloc and parts.path.startswith('/media/repository/')
        is_register = bool(re.fullmatch(r'https://dtes\.gencat\.cat/rpucportal/#/consulta/detallExpedient/\d+(?:/documents)?', target))
        if is_doc or is_register:
            docs.setdefault(target, {'titulo': a.get_text(' ', strip=True), 'url': target,
                                     'source_page': url, 'tipo': 'registro_planeamiento' if is_register else 'documento'})
    if not any(d['tipo'] == 'documento' for d in docs.values()):
        raise ValueError('Planning instrument has no attached source documents: ' + url)
    updated = content.select_one('.updated')
    match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', updated.get_text()) if updated else None
    updated_date = datetime.strptime(match[1], '%d.%m.%Y').date().isoformat() if match else None
    kind = 'POUM' if title == 'POUM' else ('modificacion_planeamiento' if title.lower().startswith('modificació') else 'planeamiento_derivado')
    return [], {
        'id': 'cabrera-de-mar-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Cabrera de Mar', 'provincia': 'Barcelona', 'codigo_ine': '08029',
        'titulo': title, 'tipo': kind, 'fase': 'vigente',
        'fase_provenance': SOURCE, 'url': url, 'source': 'ayuntamiento',
        'origen': 'planejament_vigent', 'documentos': list(docs.values()),
        'url_documento': next(d['url'] for d in docs.values() if d['tipo'] == 'documento'),
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'fecha_actualizacion_pagina': updated_date,
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
    }


class CabreraDeMarAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        with requests.get(url, timeout=30, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-cabrera-de-mar/1.0')
        }) as response:
            response.raise_for_status()
            if response.url.rstrip('/') != url.rstrip('/'):
                raise ValueError('Unexpected source redirect: ' + response.url)
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected HTML inventory')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 3_000_000:
                    raise ValueError('Source exceeds size limit')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            dest = Path(capture_dir)
            dest.mkdir(parents=True, exist_ok=True)
            (dest / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(body)
        return body.decode('utf-8-sig')

    def backfill_proyectos(self, out_jsonl: Path):
        pending, seen, rows = [SOURCE], set(), []
        while pending:
            url = pending.pop(0)
            if url in seen:
                continue
            if len(seen) >= 100:
                raise ValueError('Inventory exceeds reviewed safety bound; no partial output written')
            seen.add(url)
            children, row = parse_page(self._fetch(url), url)
            pending.extend(children)
            if row:
                rows.append(row)
        if not rows:
            raise ValueError('No usable planning instruments')
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temp = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(seen),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Refresh the full current inventory; no timestamp-based truncation.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence source'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
