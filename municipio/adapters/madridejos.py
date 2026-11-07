"""Madridejos: complete snapshot of the municipal planning document inventory."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://madridejos.es/madridejos-transparente/'
          'informacion-medioambiental-y-urbanistica/'
          'normativa-vigente-en-materia-de-gestion-urbanistica/')
LIMITATIONS = [
    'Partial municipal coverage: only the current planning inventory, not all works or historical proceedings.',
    'Documents are grouped by instrument; their presence does not independently establish current legal validity.',
    'No licence grants extracted. No verified geometry or coordinates.',
    'Dates and phases are not extracted from PDF contents; upload paths and document drafting dates are not approval dates.',
]


def _norm(text):
    return unicodedata.normalize('NFKD', text.replace('–', '-').replace('—', '-')).encode('ascii', 'ignore').decode().upper()


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('article .entry-content')
    if content is None or 'NORMAS URBANISTICAS' not in _norm(content.get_text(' ', strip=True)):
        raise ValueError('Missing municipal planning inventory')
    # This source is a single page. Fail rather than emit an incomplete snapshot
    # if WordPress introduces pagination (including multipage page content).
    if (soup.select('[rel~=next], .pagination, .page-numbers, .page-links, .av-pagination')
            or content.select('a[href*="/page/"], a[href*="?page="], a[href*="?paged="]')):
        raise ValueError('Inventory pagination detected; traversal must be implemented')
    groups: dict[str, list[dict]] = {}
    titles = {'pom': 'Plan de Ordenación Municipal de Madridejos (POM)'}
    for anchor in content.select('a[href]'):
        target = urljoin(url, anchor['href'])
        if not urlparse(target).path.lower().endswith('.pdf'):
            continue
        if urlparse(target).hostname != 'madridejos.es':
            raise ValueError('Unexpected document host')
        label = ' '.join(anchor.get_text(' ', strip=True).split())
        normalized = _norm(label)
        modification = re.fullmatch(
            r'MODIFICACION PUNTUAL N[º°O]?\s*(\d+) DEL PLAN DE ORDENACION MUNICIPAL DE MADRIDEJOS', normalized)
        if modification:
            key = 'modificacion-' + str(int(modification[1]))
            titles[key] = label
        elif (normalized in {'PORTADA CARPETA', 'LISTA DE PLANOS', 'MEMORIA INFORMATIVA', 'MEMORIA JUSTIFICATIVA'}
              or re.fullmatch(r'NORMATIVA MAYO DE 2004', normalized)
              or re.match(r'^[IO]-\d+\s*[.\-–]', normalized)):
            key = 'pom'
        else:
            # Do not silently attach a newly added instrument to the base POM.
            raise ValueError(f'Unclassified planning attachment: {label}')
        doc = {'titulo': label, 'url': target, 'source_url': url}
        bucket = groups.setdefault(key, [])
        if not any(d['url'] == target for d in bucket):
            bucket.append(doc)
    base_labels = {_norm(d['titulo']) for d in groups.get('pom', [])}
    if not {'MEMORIA INFORMATIVA', 'MEMORIA JUSTIFICATIVA', 'NORMATIVA MAYO DE 2004'} <= base_labels:
        raise ValueError('Incomplete POM document inventory')
    rows = []
    for key, documents in groups.items():
        identity = url + '#' + key
        rows.append({
            'id': 'madridejos-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
            'municipio': 'Madridejos', 'codigo_ine': '45087', 'provincia': 'Toledo',
            'titulo': titles[key], 'tipo': 'instrumento de planeamiento urbanístico',
            'url': next((d['url'] for d in documents if _norm(d['titulo']) == 'MEMORIA JUSTIFICATIVA'), documents[0]['url']),
            'inventory_url': url,
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
            'documentos': documents,
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'coverage': 'current_document_inventory',
        })
    return rows


class MadridejosAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'municipio-madridejos/1.0 (public planning inventory)'})
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE.rstrip('/'):
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            captures = Path(capture_dir)
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'inventory.html').write_text(response.text, encoding='utf-8')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE],
                'coverage': 'current_document_inventory', 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete refresh: the source has no reliable incremental publication date.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
