"""Abarán's published PGMO document inventory; no inferred approval or geometry."""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://abaran.es/plan-general-municipal-de-ordenacion-de-abaran/'
TITLE = 'Plan General Municipal de Ordenación de Abarán'
SECTIONS = {
    'Catálogo, Memoria y Normas urbanísticas': 'general',
    'Modificaciones del Plan General': 'modificaciones',
    'Planos PGMOU Abarán': 'general',
}


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    """Group all inventory attachments by instrument, deduplicating download buttons.

    Fail closed if the reviewed, single-page inventory becomes paginated or its
    section/document layout changes. Upload-path years are not event dates.
    """
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if ('next' in a.get('rel', []) or
                label in {'siguiente', 'siguiente página', 'next', '»', '›'} or
                a.find_parent(class_=re.compile(r'pagination|page-numbers|nav-links'))):
            if a['href'] not in {'', '#'}:
                raise ValueError('Inventory pagination detected; traversal requires review')
    blocks = [b for b in soup.select('.elementor-text-editor, .entry-content')
              if any(h.get_text(' ', strip=True) in SECTIONS for h in b.select('h2'))]
    # The innermost matching container avoids collecting sidebar/navigation links.
    blocks = [b for b in blocks if not any(c in blocks for c in b.find_all(['div', 'article']))]
    if len(blocks) != 1:
        raise ValueError('Expected one municipal planning inventory container')
    rows: dict[str, dict] = {}
    seen_sections = set()
    section = None
    for node in blocks[0].find_all(['h2', 'a']):
        if node.name == 'h2':
            heading = node.get_text(' ', strip=True)
            if heading not in SECTIONS:
                raise ValueError(f'Unreviewed inventory section: {heading}')
            section = SECTIONS[heading]
            seen_sections.add(heading)
            continue
        if not node.get('href'):
            continue
        label = node.get_text(' ', strip=True)
        target = urlsplit(urljoin(url, node['href']))
        if (target.scheme != 'https' or target.hostname != 'abaran.es' or
                not target.path.startswith('/wp-content/uploads/') or
                not target.path.lower().endswith(('.pdf', '.zip'))):
            raise ValueError(f'Unreviewed inventory document: {label}')
        document_url = urlunsplit((target.scheme, target.netloc, target.path, target.query, ''))
        if section == 'modificaciones':
            match = re.search(r'(?:Modificación número|Modif\. núm\.)\s*(\d+)\b', label, re.I)
            if not match:
                raise ValueError(f'Cannot associate modification attachment: {label}')
            number = str(int(match.group(1)))
            key = 'pgmo-modificacion-' + number
            title = f'Modificación número {number} del {TITLE}'
        elif section == 'general':
            key, title = 'pgmo', TITLE
        else:
            raise ValueError('Document without inventory section')
        row = rows.setdefault(key, {
            'id': 'abaran-' + key, 'municipio': 'Abarán', 'codigo_ine': '30002',
            'provincia': 'Murcia', 'titulo': title, 'tipo': 'planeamiento_urbanistico',
            'url': url, 'inventory_url': url,
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'documentos': [], 'geometry_status': 'unavailable',
            'publication_ready': False,
        })
        if not any(d['url'] == document_url for d in row['documentos']):
            row['documentos'].append({'titulo': label, 'url': document_url, 'source_url': url})
    if seen_sections != set(SECTIONS) or 'pgmo' not in rows or len(rows) < 2:
        raise ValueError('Incomplete planning inventory; review source')
    return list(rows.values())


class AbaranAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'municipio-abaran/1.0 (public planning inventory)'})
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE.rstrip('/'):
            raise ValueError('Unexpected planning inventory redirect')
        response.encoding = 'utf-8'
        rows = parse_inventory(response.text, SOURCE)
        # Optional local capture, never an alternative to fetching the live source.
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'plan-general.html.gz').write_bytes(gzip.compress(response.content, mtime=0))
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [SOURCE],
                'coverage': 'published_pgmo_document_inventory', 'publication_ready': False}

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # This source is a snapshot, not a dated incremental feed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**self._write(out_jsonl, []), 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
