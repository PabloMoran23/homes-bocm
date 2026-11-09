"""Grouped instruments from Doña Mencía's official general-planning inventory."""
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

SOURCE = 'https://donamencia.es/urbanismo-general/'


def _norm(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                   if not unicodedata.combining(c))


def _official(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname in {'donamencia.es', 'www.donamencia.es'}


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    # This is a single-page inventory. Refuse newly introduced pagination rather
    # than silently emitting just its first page (including WordPress page splits).
    if soup.select('a[rel~=next], .pagination a[href], .page-numbers[href], .page-links a[href]'):
        raise ValueError('Inventory pagination detected; crawler requires review')
    for a in soup.select('a[href]'):
        if _norm(a.get_text(' ', strip=True)) in {'siguiente', 'next', '»', '›'} and a['href'] not in {'', '#'}:
            raise ValueError('Inventory pagination detected')
    modules = soup.select('.entry-content .et_pb_tabs')
    if not modules:
        raise ValueError('Planning tab inventory missing')
    rows = []
    seen = set()
    for module in modules:
        labels = module.select('.et_pb_tabs_controls > li')
        panels = module.select('.et_pb_all_tabs > .et_pb_tab')
        if not labels or len(labels) != len(panels):
            raise ValueError('Planning tabs and labels do not match')
        for label, panel in zip(labels, panels):
            title = label.get_text(' ', strip=True)
            normalized = _norm(title)
            if not (normalized == 'pgou' or re.fullmatch(r'modificacion puntual\s+\d+\s+pgou', normalized)):
                raise ValueError(f'Unreviewed planning group: {title}')
            documents = {}
            for a in panel.select('a[href]'):
                url = urljoin(source_url, a['href'])
                name = a.get_text(' ', strip=True)
                if not name or not _official(url) or urlparse(url).path in {'', '/'} or a['href'].startswith('#'):
                    raise ValueError(f'Invalid planning document: {a}')
                documents.setdefault(url, {'titulo': name, 'url': url, 'source_url': source_url})
            if not documents:
                raise ValueError(f'Planning group has no documents: {title}')
            key = 'dona-mencia-plan-' + hashlib.sha256(normalized.encode()).hexdigest()[:16]
            if key in seen:
                raise ValueError(f'Duplicate planning group: {title}')
            seen.add(key)
            rows.append({
                'id': key, 'municipio': 'Doña Mencía', 'codigo_ine': '14022',
                'provincia': 'Córdoba', 'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'url': source_url, 'inventory_url': source_url, 'source': 'ayuntamiento',
                'origen': 'inventario_planeamiento_general',
                'documentos': list(documents.values()),
                'publication_ready': False, 'geometry_status': 'unavailable',
            })
    if not rows:
        raise ValueError('No documented planning instruments')
    return rows


class DonaMenciaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={'User-Agent': 'Mozilla/5.0 (compatible; MunicipalInventory/1.0)'})
        response.raise_for_status()
        if not _official(response.url) or urlparse(response.url).path != '/urbanismo-general/':
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'urbanismo-general.html').write_bytes(response.content)
        return {**self._write(out_jsonl, rows), 'source_urls': [response.url],
                'coverage': 'current_general_planning_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # A full refresh avoids losing revised documents under unchanged tabs.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**self._write(out_jsonl, []), 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
