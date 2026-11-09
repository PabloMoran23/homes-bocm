"""Noblejas: current municipal NNSS document inventory (partial coverage)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://noblejas.es'
URBANISMO = BASE + '/area-urbanismo/'
ORDENACION = BASE + '/ordenacion-municipal/'
SOURCES = (ORDENACION, URBANISMO)


def _documents(main, source):
    """Yield section, document caption and URL in DOM order, never navigation."""
    section = caption = ''
    for node in main.select('h2, h3, a[href]'):
        text = node.get_text(' ', strip=True)
        if node.name == 'h3':
            section, caption = text, ''
        elif node.name == 'h2':
            caption = text
        else:
            target = urljoin(source, node['href'])
            parsed = urlparse(target)
            if (parsed.scheme == 'https' and parsed.hostname == 'noblejas.es'
                    and parsed.path.startswith('/wp-content/uploads/')):
                if not caption:
                    raise ValueError('Document without caption')
                yield section, caption, target


def parse_inventory(html: str, source: str) -> list[dict]:
    if source not in SOURCES:
        raise ValueError('Unknown Noblejas inventory')
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.find('main')
    expected = 'Ordenación municipal' if source == ORDENACION else 'Urbanismo'
    if main is None or not main.find('h1', string=re.compile(expected, re.I)):
        raise ValueError('Missing municipal inventory heading')
    # These inventories are single Elementor pages. A future paginated layout
    # must be implemented explicitly; it must never silently become page one.
    if main.select('a[rel~=next], .pagination, .page-numbers, .elementor-pagination'):
        raise ValueError('Pagination detected; inventory coverage needs review')
    groups = {}
    for section, caption, target in _documents(main, source):
        if source == ORDENACION:
            key, title, kind = 'nnss', 'Normas Subsidiarias de Planeamiento de Noblejas — documentación municipal', 'normas subsidiarias'
        else:
            modification = re.match(r'Modificación\s+puntual\s+n[º°o]?\s*(\d+)\b', section, re.I)
            if modification:
                key, title, kind = 'mp-' + modification[1], section, 'modificación puntual de NNSS'
            elif re.search(r'Proyecto de reparcelación ua-66', section, re.I):
                key, title, kind = 'reparcelacion-ua-66', section, 'proyecto de reparcelación'
            else:
                continue
        if key not in groups:
            groups[key] = {
                'id': 'noblejas-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Noblejas', 'provincia': 'Toledo', 'codigo_ine': '45115',
                'titulo': title, 'tipo': kind, 'url': source, 'inventory_url': source,
                'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None, 'documentos': [],
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'geometry_status': 'unavailable',
            }
        record = groups[key]
        doc = {'titulo': caption, 'url': target, 'source_url': source}
        if doc not in record['documentos']:
            record['documentos'].append(doc)
        # Only an explicit definitive-approval caption supplies an approval date.
        match = re.search(r'APROBACION DEFINITIVA CPOTU (\d{2})-(\d{2})-(\d{4})', caption, re.I)
        if match:
            record['fecha_aprob'] = date(int(match[3]), int(match[2]), int(match[1])).isoformat()
            record['fase'] = 'aprobación definitiva'
            record['fecha_aprob_fuente'] = doc
        elif record['fase'] is None and re.search(r'INFORMACI[ÓO]N P[ÚU]BLICA', caption, re.I):
            record['fase'] = 'información pública (según documentación publicada)'
    if not groups:
        raise ValueError('No supported planning instruments found')
    for record in groups.values():
        record['url_documento'] = record['documentos'][0]['url']
    return list(groups.values())


class NoblejasAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = []
        captures = self.config.get('capture_dir')
        for source in SOURCES:
            response = requests.get(source, timeout=40, headers={
                'User-Agent': 'municipio-noblejas/1.0 (public planning inventory)'})
            response.raise_for_status()
            if response.url.rstrip('/') != source.rstrip('/'):
                raise ValueError('Unexpected source redirect')
            if captures:
                directory = Path(captures)
                directory.mkdir(parents=True, exist_ok=True)
                (directory / (urlparse(source).path.strip('/') + '.html')).write_text(response.text, encoding='utf-8')
            rows.extend(parse_inventory(response.text, source))
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES),
                'coverage': 'current NNSS, published modifications and UA-66 reparcelacion inventory; partial',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
