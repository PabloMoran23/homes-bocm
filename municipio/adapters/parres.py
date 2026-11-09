"""Parres municipal planning document inventory; one row per named instrument."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.ayto-parres.es/normativa-urbanistica'
LIMITATIONS = [
    'Partial coverage: municipal planning inventory only, not the regional register, works or licence history.',
    'Inventory presence does not establish approval, current legal force or execution; dates and phase remain unknown.',
    'PDF links and source labels retained; PDF contents are not parsed for dates or geometry.',
    'Standalone environmental assessment, IPCA heritage notices and emergency flood-response plan excluded.',
    'Duplicate document URLs retained once with all nonempty source labels; source labelling errors are not corrected.',
]
EXCLUDED = {
    'Evaluación ambiental estratégica', 'b. IPCA',
    'PLAN DE ACTUACIÓN MUNICIPAL FRENTE A INUNDACIONES DEL CONCEJO DE PARRES',
}


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def parse_inventory(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, 'html.parser')
    candidates = [n for n in soup.select('.journal-content-article .detalle')
                  if any(_text(h) == 'PLANEAMIENTO DE PARRES' for h in n.select('h3'))]
    if len(candidates) != 1:
        raise ValueError('Missing or ambiguous Parres planning inventory')
    content = candidates[0]
    if (soup.select('a[rel~=next]') or content.select('.pagination, .lfr-pagination, .search-container-pagination')):
        raise ValueError('Paginated inventory requires review; refusing an incomplete snapshot')
    groups = []
    current = None
    in_inventory = False
    for node in content.find_all(['h3', 'h4', 'a']):
        if node.name == 'h3':
            in_inventory = _text(node) == 'PLANEAMIENTO DE PARRES'
            current = None
            continue
        if not in_inventory:
            continue
        if node.name == 'h4':
            title = _text(node)
            current = None
            if title in EXCLUDED:
                continue
            match = re.fullmatch(r'(\d+|a)\.\s+(.+)', title)
            if not match:
                raise ValueError(f'Unrecognised inventory section: {title}')
            name = match[2]
            if name.startswith('NSP '):
                kind = 'normas subsidiarias'
            elif name.startswith('Plan Parcial'):
                kind = 'plan parcial'
            elif name.startswith('PERI '):
                kind = 'plan especial de reforma interior'
            elif name.startswith('Estudio Detalle'):
                kind = 'estudio de detalle'
            elif name.startswith('Estudio Implantación'):
                kind = 'estudio de implantación'
            elif name == 'CAU - Catalogo urbanístico':
                kind = 'catálogo urbanístico'
            else:
                raise ValueError(f'Unrecognised instrument type: {title}')
            current = {'title': name, 'section': title, 'kind': kind, 'documents': {}}
            groups.append(current)
        elif current is not None:
            href = node.get('href', '')
            label = _text(node)
            if not href:
                continue
            target = urljoin(SOURCE, href)
            parsed = urlsplit(target)
            if parsed.scheme != 'https' or parsed.netloc != 'www.ayto-parres.es' or not re.match(r'^/documents/188680/\d+/.+\.pdf/', parsed.path, re.I):
                raise ValueError(f'Unexpected instrument document URL: {target}')
            doc = current['documents'].setdefault(target, {'url': target, 'titulos_fuente': []})
            if label and label not in doc['titulos_fuente']:
                doc['titulos_fuente'].append(label)
    if not groups:
        raise ValueError('No planning instruments found')
    rows = []
    ids = set()
    for group in groups:
        documents = list(group['documents'].values())
        folders = {urlsplit(d['url']).path.split('/')[3] for d in documents}
        if len(folders) != 1:
            raise ValueError('Missing documents or ambiguous instrument folder')
        key = 'parres-plan-' + next(iter(folders))
        if key in ids:
            raise ValueError('One document folder assigned to multiple instruments')
        ids.add(key)
        rows.append({
            'id': key, 'municipio': 'Parres', 'codigo_ine': '33045', 'provincia': 'Asturias',
            'titulo': group['title'], 'tipo': group['kind'], 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'inventory_url': SOURCE, 'url_documento': documents[0]['url'],
            'documentos': documents, 'seccion_fuente': group['section'],
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'unavailable', 'coverage': 'partial_planning_document_inventory',
        })
    return rows


class ParresAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='parres', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.ayto-parres.es')

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-parres/1.0'),
        })
        response.raise_for_status()
        if urlsplit(response.url)._replace(query='', fragment='') != urlsplit(SOURCE):
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'normativa-urbanistica.html').write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # The unpaginated inventory is refreshed as a complete scoped snapshot.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
