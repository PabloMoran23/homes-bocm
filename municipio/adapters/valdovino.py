"""Snapshot of the municipal rural-settlement planning document inventory."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.concellodevaldovino.com/urbanismo/planeamento-xeral/delimitacion/'


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find('h1')
    if not heading or heading.get_text(' ', strip=True) != 'Delimitación de novos núcleos rurais':
        raise ValueError('Missing municipal rural-settlement inventory heading')
    records = {}
    for heading in soup.select('.wpb_text_column h4'):
        title = heading.get_text(' ', strip=True).rstrip(':')
        match = re.fullmatch(r'Modificación puntual núm\. (\d+) das NNSSPP para delimitación de solo de núcleo rural', title)
        if not match:
            continue
        block = heading.parent
        # Pagination of the separate latest-news widget is outside this inventory.
        for a in block.select('a[href]'):
            if 'next' in a.get('rel', []) or a.get_text(' ', strip=True).lower() in {'seguinte', 'siguiente', 'next', 'seguinte páxina'}:
                raise ValueError('Planning inventory pagination requires crawler review')
        documents = {}
        for a in block.select('a[href]'):
            url = urljoin(source_url, a['href'])
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname != 'www.concellodevaldovino.com' or not parsed.path.startswith('/arquivo/sites/default/files/') or not parsed.path.lower().endswith(('.pdf', '.zip')):
                raise ValueError('Unexpected planning attachment; review inventory')
            documents.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url, 'source_url': source_url})
        if not documents:
            raise ValueError('Named planning instrument has no source documents')
        key = 'valdovino-nnss-mp-' + match[1]
        if key in records:
            raise ValueError('Ambiguous duplicate planning instrument')
        records[key] = {
            'id': key, 'municipio': 'Valdoviño', 'codigo_ine': '15087', 'provincia': 'A Coruña',
            'titulo': title, 'tipo': 'modificacion_planeamiento', 'fase': None,
            'url': source_url, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
            'documentos': list(documents.values()),
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'date_status': 'Dates are in linked bulletins; PDF contents are not parsed',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'coverage': 'Municipal rural-settlement delimitation document page only',
        }
    if not records:
        raise ValueError('No supported named planning instruments found')
    return list(records.values())


class ValdovinoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> dict:
        target = Path(out_jsonl)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(target)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'publication_ready': False}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={'User-Agent': 'municipio-valdovino/1.0'})
        response.raise_for_status()
        if response.url != SOURCE:
            raise ValueError('Unexpected inventory redirect')
        # Optional local capture of exactly the response used by the adapter.
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'live-delimitacion.html').write_bytes(response.content)
        return self._write(out_jsonl, parse_inventory(response.content, response.url))

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        result = self._write(out_jsonl, [])
        return {**result, 'status': 'disabled', 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
