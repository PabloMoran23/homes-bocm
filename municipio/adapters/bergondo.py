"""Bergondo's four municipal planning document inventories (partial coverage)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://www.bergondo.gal/areas-e-servizos/urbanismo/'
INVENTORIES = {
    'borrador-do-plan-xeral-de-ordenacion-municipal-pxom/': 'draft',
    'modificacion-puntual-das-nnss/': 'amendments',
    'plans-especiais/': 'special',
    'proxectos-de-urbanizacion/': 'works',
}
LIMITATIONS = [
    'Partial coverage: four municipal urbanismo inventories, not all municipal works or historical planning.',
    'Phases are those displayed on the inventory, not independently verified current legal status or execution.',
    'No granted licences, coordinates or geometry extracted.',
    'Document links retained as published; legacy andaina downloads may return 406 and the Rio Maior ZIP returned 404 during research.',
    'No instrument publication dates inferred from WordPress metadata, upload paths or bulletin URL dates.',
]
MONTHS = {m: i for i, m in enumerate(
    ['xaneiro', 'febreiro', 'marzo', 'abril', 'maio', 'xuño', 'xullo', 'agosto',
     'setembro', 'outubro', 'novembro', 'decembro'], 1)}


def _space(text):
    return ' '.join(text.split())


def _agreement(text):
    # Only dates explicitly following an approval order or a plenary session.
    match = re.search(
        r'(?:sesión extraordinaria que tivo lugar o (?:\w+ )?|'
        r'Aprobada def[\w]* por orde .*? o |Aprobada definitivamente pola orde .*? do )'
        r'(\d{1,2}) de (\w+) de (\d{4})', text, re.I)
    if not match:
        return None
    from datetime import date
    return date(int(match[3]), MONTHS[match[2].lower()], int(match[1])).isoformat()


def parse_inventory(html: str, url: str, kind: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('article .entry')
    if content is None:
        raise ValueError(f'Missing municipal inventory content: {url}')
    if soup.select('a[rel~=next], .pagination a, .page-links a, .nav-links a') or any(
        a.get_text(' ', strip=True).casefold() in {'seguinte', 'siguiente', 'next', 'máis', 'ver máis'}
        for a in content.select('a[href]')
    ):
        raise ValueError('Pagination detected: review traversal before accepting partial output')

    # Each group is an instrument, never one row per attachment.
    groups = []
    if kind == 'draft':
        heading = soup.select_one('h1')
        if heading is None or 'Borrador' not in heading.get_text():
            raise ValueError('Unrecognized PXOM draft inventory')
        groups = [(heading.get_text(' ', strip=True), content)]
    else:
        selector = {'amendments': 'p', 'special': 'p', 'works': 'dt'}[kind]
        current_title, fragments = None, []
        # Flatten to the actual blocks while preserving their document order.
        for block in content.select('p, dt'):
            text = _space(block.get_text(' ', strip=True))
            starts = (kind == 'amendments' and bool(re.match(r'Aprobación .*Modificación puntual ', text, re.I))) or (
                kind == 'special' and text.upper().startswith('PLAN ESPECIAL ')) or (
                kind == 'works' and block.name == selector)
            if starts:
                if current_title:
                    groups.append((current_title, BeautifulSoup(''.join(fragments), 'html.parser')))
                current_title, fragments = text, []
            if current_title:
                fragments.append(str(block))
        if current_title:
            groups.append((current_title, BeautifulSoup(''.join(fragments), 'html.parser')))

    rows = []
    for title, group in groups:
        text = _space(group.get_text(' ', strip=True))
        docs = {}
        for a in group.select('a[href]'):
            target = urljoin(url, a['href'])
            if urlparse(target).scheme not in {'https', 'http'}:
                continue
            docs.setdefault(target, {'titulo': _space(a.get_text(' ', strip=True)), 'url': target,
                                     'provenance_url': url})
        if not docs:
            raise ValueError(f'Instrument without document links: {title}')
        phase = 'borrador' if kind == 'draft' else (
            'aprobación definitiva' if 'aprobación definitiva' in text.lower() else
            'aprobación inicial' if 'aprobación inicial' in text.lower() else None)
        identity_title = re.sub(r'^Aprobación .*?(?=Modificación puntual)', '', title, flags=re.I)
        identity = urlparse(url).path + '#' + identity_title.casefold()
        row = {
            'id': 'bergondo-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:20],
            'municipio': 'Bergondo', 'codigo_ine': '15008', 'provincia': 'A Coruña',
            'titulo': title, 'tipo': 'proyecto de urbanización' if kind == 'works' else 'planeamiento urbanístico',
            'url': url, 'inventory_url': url, 'source': 'ayuntamiento',
            'origen': 'inventario_municipal_urbanismo', 'documentos': list(docs.values()),
            'descripcion': text, 'geometry_status': 'unavailable', 'publication_ready': False,
        }
        if phase:
            row['fase'] = phase
        agreement = _agreement(text)
        if agreement:
            row['fecha_acuerdo'] = agreement
        expediente = re.search(r'EXP:\s*([\dA-Z/]+)', text)
        if expediente:
            row['expediente'] = expediente[1]
        rows.append(row)
    if not rows:
        raise ValueError(f'No instruments found: {url}')
    if len({row['id'] for row in rows}) != len(rows):
        raise ValueError('Duplicate instrument headings require review')
    return rows


class BergondoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl: Path):
        rows, source_urls = [], []
        capture_dir = self.config.get('evidence_dir')
        for path, kind in INVENTORIES.items():
            response = requests.get(urljoin(ROOT, path), timeout=40,
                                    headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            if urlparse(response.url).hostname not in {'bergondo.gal', 'www.bergondo.gal'}:
                raise ValueError('Unexpected inventory redirect')
            if capture_dir:
                target = Path(capture_dir)
                target.mkdir(parents=True, exist_ok=True)
                (target / (kind + '.html')).write_bytes(response.content)
            rows.extend(parse_inventory(response.content, response.url, kind))
            source_urls.append(response.url)
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': source_urls, 'limitations': LIMITATIONS,
                'coverage': 'four_municipal_urbanismo_inventories', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full inventory snapshot; no date-based filtering or deletion claims.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
