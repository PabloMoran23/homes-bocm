"""Celrà's municipal current-planning inventory, one row per instrument."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from typing import Any

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.celra.cat/wp/ajuntament/documentacio/normativa-municipal/planejament-urbanistic/'
DATE_LABEL = re.compile(r'\s*[-–]\s*data d[’\']aprovació\s*', re.I)


def _normal(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if not unicodedata.combining(c))


def _approval(raw: str) -> str | None:
    if not re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}', raw):
        return None
    try:
        day, month, year = map(int, raw.split('/'))
        return date(year, month, day).isoformat()
    except ValueError:
        return None


class CelraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug: str, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.celra.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        h1 = soup.find('h1')
        if not h1 or h1.get_text(' ', strip=True) != 'Planejament urbanístic vigent':
            raise ValueError('Celrà planning inventory heading missing')
        # This inventory is a single page. Fail visibly if pagination is introduced.
        if soup.select('.pagination a[href], .page-links a[href], a.page-numbers[href], a.next[href]'):
            raise ValueError('Paginated inventory requires crawler review')
        for a in soup.select('a[href]'):
            label = _normal(a.get_text(' ', strip=True))
            if 'next' in a.get('rel', []) or label in {'seguent', 'seguents', 'siguiente', 'next'}:
                if a['href'] not in {'', '#'}:
                    raise ValueError('Paginated inventory requires crawler review')
        blocks = []
        for heading in soup.select('.panel-heading h5'):
            text = heading.get_text(' ', strip=True)
            if DATE_LABEL.search(text):
                blocks.append((text, heading.find_parent(class_='panel')))
            elif _normal(text).startswith(('revisio del pla', 'modificacio puntual', 'pla especial')):
                raise ValueError('Planning panel lost its approval label')
        # The two partial plans are list items, not accordion panels.
        for bold in soup.select('li > b, li > strong'):
            if _normal(bold.get_text(' ', strip=True)).startswith('pla parcial '):
                li = bold.parent
                text = ' '.join(str(node) if isinstance(node, str) else node.get_text(' ', strip=True)
                                for node in li.contents if getattr(node, 'name', None) not in {'ol', 'ul'})
                blocks.append((' '.join(text.split()), li))
        rows = {}
        for heading, block in blocks:
            parts = DATE_LABEL.split(heading, maxsplit=1)
            if len(parts) != 2:
                raise ValueError('Missing approval label for planning instrument')
            title, raw_date = parts
            normalized = _normal(title)
            if not normalized.startswith(('revisio del pla general', 'modificacio puntual ',
                                          'pla especial ', 'pla parcial ')):
                raise ValueError('Unreviewed planning instrument type: ' + title)
            docs = {}
            for a in block.select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                path = urlsplit(url)
                if path.scheme in {'http', 'https'} and path.path.lower().endswith('.pdf'):
                    docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                                          'source_url': SOURCE})
            if not docs:
                raise ValueError('Planning instrument has no source documents: ' + title)
            approval = _approval(raw_date)
            narrative = [p.get_text(' ', strip=True) for p in block.select('p')
                         if 'aprovació' in p.get_text().casefold()]
            definitive = any('aprovació definitiva' in p.casefold() for p in narrative)
            identity = hashlib.sha256(normalized.encode()).hexdigest()[:16]
            row = {
                'id': 'celra-proy-' + identity, 'municipio': 'Celrà', 'provincia': 'Girona',
                'codigo_ine': '17049', 'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'fase': 'aprobación definitiva' if definitive else 'aprobado (sin precisar fase)',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': approval, 'fecha_aprob_original': raw_date,
                'url': SOURCE, 'url_documento': next(iter(docs)), 'documentos': list(docs.values()),
                'source': 'ayuntamiento', 'origen': 'planejament_urbanistic_vigent',
                'source_heading': heading, 'approval_evidence': narrative,
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'coverage': 'Municipal current-planning inventory only; not a complete RPUC history',
            }
            if approval is None:
                row['date_warning'] = 'Invalid source approval date retained verbatim; not corrected'
            if identity in rows:
                raise ValueError('Duplicate planning instrument identity: ' + title)
            rows[identity] = row
        if not rows:
            raise ValueError('No documented planning instruments found')
        return list(rows.values())

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temp = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=40, stream=True,
                          headers={'User-Agent': self.config.get('user_agent', 'municipio-celra/1.0')}) as response:
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 4_000_000:
                    raise ValueError('Celrà planning response exceeds 4 MB')
            html = content.decode('utf-8')
        rows = self.parse_projects(html)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'planejament.html').write_bytes(content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'publication_ready': False, 'pagination': 'single complete inventory page'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Full snapshot refresh; no date-based cutoff or invented incremental cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
