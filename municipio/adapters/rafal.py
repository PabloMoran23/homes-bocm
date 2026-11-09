"""Rafal's municipal PGOU document inventory, grouped by planning instrument."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://rafal.es/?page_id=451'
LIMITATIONS = [
    'Partial coverage: municipal PGOU inventory only, not all works or licences.',
    'Document labels are provenance, not verified current legal status.',
    'Linked document contents and dates are not extracted; some PDF requests return HTTP 403.',
    'No verified geometry; no coordinates inferred.',
    'The separate electronic-office inventory is not traversed or merged.',
]


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text).lower()
                   if unicodedata.category(c) != 'Mn')


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    if not any(h.get_text(' ', strip=True).upper() == 'PGOU'
               for h in soup.select('h1, h2')):
        raise ValueError('Missing PGOU heading')
    widgets = [w for w in soup.select('.elementor-widget-text-editor')
               if 'PLANOS DE INFORMACIÓN' in w.get_text(' ', strip=True)]
    if len(widgets) != 1:
        raise ValueError('Missing or ambiguous PGOU document inventory')
    content = widgets[0]
    # The selected source is a complete single-page inventory. Fail visibly if
    # pagination appears, rather than silently returning its first page.
    if soup.select('[rel="next"], .pagination, .page-links, .nav-links') or any(
        _norm(a.get_text(' ', strip=True)) in ('siguiente', 'mostrar mas', 'next')
        for a in content.select('a[href]')
    ):
        raise ValueError('Unexpected pagination: inventory requires investigation')
    groups = {'pgou': {'titulo': 'Plan General de Ordenación Urbana de Rafal (PGOU)',
                       'documentos': []}}
    current = 'pgou'
    for node in content.find_all(['strong', 'a']):
        text = ' '.join(node.get_text(' ', strip=True).split())
        if node.name == 'strong':
            match = re.match(r'^modificacion puntual n[º°o]?\s*(\d+)\b', _norm(text))
            if match:
                current = 'modificacion-' + str(int(match[1]))
                groups.setdefault(current, {'titulo': text.rstrip(':'), 'documentos': []})
            elif _norm(text).startswith('modificacion puntual'):
                raise ValueError('Unrecognized modification heading')
            continue
        target = urljoin(url, node.get('href', ''))
        parsed = urlparse(target)
        municipal_pdf = (parsed.hostname in ('rafal.es', 'www.rafal.es')
                         and parsed.path.startswith('/wp-content/uploads/')
                         and parsed.path.lower().endswith('.pdf'))
        official_dossier = (parsed.hostname == 'www.modernizaalicante.es'
                            and parsed.path == '/dossierh.14')
        if not (municipal_pdf or official_dossier) or not text:
            raise ValueError(f'Unrecognized inventory document: {text!r}')
        doc = {'titulo': text, 'url': target, 'inventory_url': url}
        if doc not in groups[current]['documentos']:
            groups[current]['documentos'].append(doc)
    if not groups['pgou']['documentos'] or len(groups) < 2:
        raise ValueError('Incomplete PGOU inventory')
    rows = []
    for key, group in groups.items():
        if not group['documentos']:
            raise ValueError(f'Instrument without documents: {key}')
        warnings = [d['titulo'] for d in group['documentos']
                    if 'anulacion' in _norm(d['titulo'])]
        rows.append({
            'id': 'rafal-plan-' + key, 'municipio': 'Rafal',
            'codigo_ine': '03109', 'provincia': 'Alicante',
            'titulo': group['titulo'], 'tipo': 'instrumento de planeamiento urbanístico',
            'url': url, 'inventory_url': url, 'documentos': group['documentos'],
            'source': 'ayuntamiento', 'origen': 'inventario_municipal_pgou',
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'advertencias_documentales': warnings,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    return rows


class RafalAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in ('rafal.es', 'www.rafal.es'):
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        capture = self.config.get('capture_dir')
        if capture:
            folder = Path(capture)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'pgou.html').write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                  for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [response.url],
                'coverage': 'single_page_pgou_inventory', 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Refresh the complete inventory; stable IDs do not depend on link order.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
