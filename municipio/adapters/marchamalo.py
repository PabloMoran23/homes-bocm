"""Marchamalo's single-page municipal planning document inventory.

Drive links are documentary references published by the municipality, not an
attempt to enumerate folder contents or infer the legal status of a plan.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.marchamalo.com/ayuntamiento/normativa/normativa-urbanistica/'
GROUPS = {
    'PGOU – Plan General de Ordenación Urbana': 'PGOU',
    'PLANES PARCIALES': 'Plan parcial',
    'PLANES ESPECIALES': 'Plan especial',
    'ESTUDIOS DE DETALLE': 'Estudio de detalle',
}
LIMITATIONS = [
    'Snapshot of the municipal planning inventory only; not all projects or public works.',
    'Drive folder contents, including individual PGOU modifications, are not enumerated.',
    'Named entries without a document link are excluded and reported separately.',
    'No granted licences, verified approval/publication dates or project geometry extracted.',
    'Listing under municipal normativa does not establish current legal validity.',
]


def _document(anchor):
    url = anchor['href']
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'drive.google.com':
        raise ValueError('Unexpected planning document host')
    match = re.fullmatch(r'/(?:file/d/|drive/folders/)([\w-]+)(?:/edit|/view)?/?', parsed.path)
    identifier = match[1] if match else None
    if parsed.path == '/folderview':
        ids = parse_qs(parsed.query).get('id', [])
        identifier = ids[0] if len(ids) == 1 else None
    if not identifier:
        raise ValueError('Unrecognized Drive document URL')
    return {
        'titulo': anchor.get_text(' ', strip=True).lstrip('>+ ').strip(),
        'url': url,
        'drive_id': identifier,
        'tipo': 'carpeta' if parsed.path == '/folderview' or '/folders/' in parsed.path else 'documento',
        'provenance_url': SOURCE,
    }


def parse_inventory(html: str) -> tuple[list[dict], list[str]]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#main-content-block')
    if content is None:
        raise ValueError('Missing municipal planning inventory')
    # This reviewed source is a single page. Fail explicitly if pagination is
    # introduced, rather than returning just its first page.
    if soup.select('[rel~=next], .pagination, .page-numbers, .page-links') or any(
        a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', 'siguiente página'}
        for a in content.select('a[href]')
    ):
        raise ValueError('Paginated inventory requires crawler review')
    rows, unlinked, seen_groups = {}, [], set()
    group = None
    pgou = None

    def add(title, kind, doc):
        key = (kind, title)
        if key not in rows:
            stable = kind + ':' + title
            rows[key] = {
                'id': 'marchamalo-plan-' + hashlib.sha256(stable.encode()).hexdigest()[:16],
                'municipio': 'Marchamalo', 'provincia': 'Guadalajara', 'codigo_ine': '19171',
                'titulo': title, 'tipo': kind,
                'url': SOURCE, 'inventory_url': SOURCE,
                'source': 'ayuntamiento', 'origen': 'inventario_normativa_urbanistica',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None,
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'geometry_status': 'unavailable',
                'documentos': [], 'coverage': 'municipal_inventory_linked_entries',
            }
        row = rows[key]
        if doc['drive_id'] not in {d['drive_id'] for d in row['documentos']}:
            row['documentos'].append(doc)
        return row

    for paragraph in content.find_all('p'):
        text = paragraph.get_text(' ', strip=True)
        if text.startswith('>'):
            label = text.lstrip('> ').strip()
            if label not in GROUPS:
                raise ValueError('Unreviewed planning category: ' + label)
            group = GROUPS[label]
            seen_groups.add(group)
            if group == 'PGOU':
                anchor = paragraph.select_one('a[href]')
                if anchor is None:
                    raise ValueError('PGOU has no document reference')
                pgou = add('Plan General de Ordenación Urbana de Marchamalo', group, _document(anchor))
            continue
        if not text.startswith('+'):
            continue
        label = text.lstrip('+ ').strip()
        if group is None:
            raise ValueError('Instrument outside planning category')
        anchors = paragraph.select('a[href]')
        if not anchors:
            unlinked.append(group + ': ' + label)
            continue
        if group == 'PGOU':
            # These are subordinate collections/technical documents, not
            # separate named instruments. Retain every municipal reference.
            for anchor in anchors:
                doc = _document(anchor)
                if doc['drive_id'] not in {d['drive_id'] for d in pgou['documentos']}:
                    pgou['documentos'].append(doc)
        else:
            pattern = {'Plan parcial': r'SP\.', 'Estudio de detalle': r'SUE\s+\d', 'Plan especial': r'PERI\b'}[group]
            if not re.match(pattern, label, re.I):
                raise ValueError('Unreviewed instrument label: ' + label)
            for anchor in anchors:
                add(group + ' ' + label, group, _document(anchor))
    if seen_groups != set(GROUPS.values()) or len(rows) < 2:
        raise ValueError('Incomplete or empty municipal planning inventory')
    return list(rows.values()), unlinked


class MarchamaloAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='marchamalo', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.marchamalo.com')

    @staticmethod
    def _write(out_jsonl, rows):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(output)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=30, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-marchamalo/1.0'),
        })
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE.rstrip('/'):
            raise ValueError('Unexpected municipal inventory redirect')
        rows, unlinked = parse_inventory(response.text)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'unlinked_entries': unlinked, 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh of this finite inventory. No dates support a watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
