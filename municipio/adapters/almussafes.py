"""Complete snapshot of the municipality's finite current-planning table."""
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

SOURCE = 'https://almussafes.net/departamentos/urbanismo/serveis-urbanisme/'


def _key(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


class AlmussafesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://almussafes.net')

    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('main article .entry-content')
        if content is None:
            raise ValueError('Missing municipal planning content')
        # This source is a finite table, not the separately paginated news archive.
        # Fail if a future version introduces paging rather than lose records.
        for a in content.select('a[href]'):
            if (a.get('rel') and 'next' in a['rel']) or re.search(
                r'(?:/page/|[?&](?:page|paged|offset)=)', a['href']
            ) or _key(a.get_text(' ', strip=True)) in {
                'next', 'seguent', 'siguiente', 'mostrar mes', 'load more'
            }:
                raise ValueError('Planning inventory pagination requires review')
        headings = [h for h in content.find_all(['h2', 'h3', 'h4'])
                    if _key(h.get_text(' ', strip=True)) == 'plantejament vigent']
        if len(headings) != 1:
            raise ValueError('Missing or ambiguous current-planning heading')
        figure = headings[0].find_next_sibling()
        table = figure.find('table') if figure else None
        if table is None:
            raise ValueError('Missing current-planning table')
        rows, current, titles = [], None, set()
        header_seen = False
        for tr in table.select('tr'):
            cells = tr.find_all(['td', 'th'], recursive=False)
            if len(cells) != 2:
                raise ValueError('Unexpected planning table columns')
            label = cells[0].get_text(' ', strip=True)
            if not tr.get_text(strip=True) and not tr.select('a[href]'):
                continue
            if _key(label) == 'descripcio' and _key(cells[1].get_text(' ', strip=True)) == 'document':
                if header_seen or rows:
                    raise ValueError('Unexpected repeated table header')
                header_seen = True
                continue
            if not header_seen:
                raise ValueError('Missing planning table header')
            match = re.fullmatch(r'(\d+)\s*[–—-]\s*(PLA\s+.+)', label, re.I)
            if match:
                title = match[2]
                key = _key(title)
                if int(match[1]) != len(rows) + 1 or key in titles or cells[1].get_text(strip=True) or tr.select('a[href]'):
                    raise ValueError('Ambiguous planning instrument grouping')
                titles.add(key)
                current = {
                    'id': 'almussafes-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                    'municipio': 'Almussafes', 'provincia': 'Valencia', 'codigo_ine': '46035',
                    'titulo': title, 'tipo': 'planeamiento_urbanistico',
                    'fase': 'vigente según inventario municipal',
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'planeamiento_vigente',
                    'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                    'publication_ready': False,
                    'geometry_status': 'No verified instrument geometry extracted',
                }
                rows.append(current)
                continue
            links = cells[1].select('a[href]')
            if current is None or not label or not links:
                raise ValueError('Unrecognised planning table row')
            for a in links:
                url = urljoin(SOURCE, a['href'])
                parsed = urlparse(url)
                if parsed.scheme != 'https' or not (
                    (parsed.hostname == 'almussafes.net' and parsed.path.startswith('/wp-content/uploads/') and parsed.path.lower().endswith('.pdf'))
                    or (parsed.hostname == 'drive.google.com' and re.fullmatch(r'/file/d/[\w-]+/view', parsed.path))
                ):
                    raise ValueError('Unexpected planning document link')
                doc = {'titulo': label, 'url': url, 'url_procedencia': SOURCE}
                if doc not in current['documentos']:
                    current['documentos'].append(doc)
        if not rows or any(not row['documentos'] for row in rows):
            raise ValueError('Planning inventory is empty or contains undocumented instruments')
        return rows

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-almussafes/1.0')
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'almussafes.net':
                raise ValueError('Unexpected municipal source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Municipal source exceeds response size limit')
                chunks.append(chunk)
            payload = b''.join(chunks)
        rows = self.parse_projects(payload.decode('utf-8'))
        if self.config.get('capture_dir'):
            capture_dir = Path(self.config['capture_dir'])
            capture_dir.mkdir(parents=True, exist_ok=True)
            (capture_dir / 'planeamiento-vigente.html').write_bytes(payload)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'Complete current-planning table only; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full replacement snapshot: never infer additions from publication dates.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No granted-licence register verified'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
