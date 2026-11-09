"""Municipal Urbanismo document inventory; one record per instrument/project."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.lesalqueries.es/es/administracion/urbanismo'
LIMITATIONS = [
    'Partial municipal coverage: only the public Urbanismo document inventory, not the electronic transparency portal or a complete historic register.',
    'Document listing does not establish current legal validity, approval, execution or licence grant. No dates or geometry inferred.',
    'Attachments are municipal links hosted on Google Drive; their full contents and continued public availability are not guaranteed.',
    'Convenio Camí la Ratlla and the environmental licence heading are excluded: no verified physical project or licence grant extracted from them.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


class LesAlqueriesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='les-alqueries', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('main .cuerpo-taxo')
        if content is None:
            raise ValueError('Missing municipal Urbanismo inventory container')
        # This inventory is a single page. Fail explicitly if it gains paging.
        if soup.select('.pager, .pagination, a[rel~=next]') or any(
            _text(a).lower() in {'siguiente', 'següent', 'next', 'mostrar más', 'mostrar més'}
            and a.get('href', '') not in {'', '#'} for a in soup.select('a[href]')
        ):
            raise ValueError('Inventory pagination detected; crawler must be extended')
        rows = []
        seen = set()
        for heading in content.find_all('h3', recursive=False):
            title = re.sub(r'^\d+\.\s*', '', _text(heading))
            lower = title.lower()
            if lower.startswith('san ramón') and 'rehabilitación de edificio' in lower:
                kind = 'proyecto_rehabilitacion'
            elif re.match(r'^pgou\b', lower):
                kind = 'plan_general'
            elif lower.startswith('proyecto de reparcelación'):
                kind = 'proyecto_reparcelacion'
            elif re.match(r'^pai\b', lower):
                kind = 'programa_actuacion_integrada'
            else:
                continue
            documents = {}
            for node in heading.next_siblings:
                if getattr(node, 'name', None) == 'h3':
                    break
                if not getattr(node, 'find_all', None):
                    continue
                for a in node.find_all('a', href=True):
                    href = urljoin(SOURCE, a['href'])
                    parsed = urlparse(href)
                    if parsed.hostname == 'drive.google.com' and re.fullmatch(r'/file/d/[\w-]+/view', parsed.path):
                        canonical = parsed._replace(query='', fragment='').geturl()
                        documents.setdefault(canonical, {'titulo': _text(a), 'url': href,
                            'provenance_url': SOURCE, 'hosting': 'Google Drive linked by municipality'})
            if not documents:
                raise ValueError(f'Project has no supported document links: {title}')
            key = title.casefold()
            if key in seen:
                raise ValueError(f'Duplicate instrument heading: {title}')
            seen.add(key)
            rows.append({
                'id': 'les-alqueries-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'les Alqueries / Alquerías del Niño Perdido',
                'codigo_ine': '12901', 'provincia': 'Castellón',
                'titulo': title, 'tipo': kind, 'fase': None,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
                'documentos': list(documents.values()),
                'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                'publication_ready': False, 'coverage': 'partial',
                'limitations': LIMITATIONS,
            })
        if not rows:
            raise ValueError('No supported projects in municipal inventory')
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        response = requests.get(SOURCE, timeout=40, headers={'User-Agent': 'municipio-les-alqueries/1.0'})
        response.raise_for_status()
        rows = self.parse_projects(response.text)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            target = Path(capture_dir)
            target.mkdir(parents=True, exist_ok=True)
            (target / 'urbanismo-live.html').write_text(response.text, encoding='utf-8')
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temp = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete refresh of this single-page inventory; no date-based cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
