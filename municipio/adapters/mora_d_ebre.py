"""Municipal NNSS modification inventory, one record per planning instrument."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://www.moradebre.cat/serveis/urbanisme-i-patrimoni/'
          'modificacio-normes-subsidiaries/')


def _norm(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                   if not unicodedata.combining(c))


class MoraDEbreAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE = SOURCE

    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.moradebre.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('.post-content')
        heading = soup.select_one('h1')
        if (not content or not heading or
                'modificacio normes subsidiaries' not in _norm(heading.get_text(' ', strip=True))):
            raise ValueError('Missing municipal NNSS modification inventory')
        # This reviewed inventory is a single page. Fail visibly if pagination
        # appears, instead of treating the first page as a complete snapshot.
        if soup.select('.pagination, .page-numbers, a[rel~=next], .nav-next'):
            raise ValueError('Inventory has pagination; crawler requires review')
        rows = {}
        panels = content.select('.fusion-panel')
        if not panels:
            raise ValueError('Inventory contains no instrument panels')
        for panel in panels:
            title_node = panel.select_one('.fusion-toggle-heading')
            body = panel.select_one('.panel-body')
            if not title_node or not body:
                raise ValueError('Incomplete instrument panel')
            heading_text = title_node.get_text(' ', strip=True)
            normalized = _norm(heading_text)
            if not ('modificacio' in normalized and
                    ('normes subsidiaries' in normalized or 'nnss' in normalized)):
                raise ValueError('Unrecognized inventory panel; review classification')
            title = heading_text.split('(')[0].strip()
            title = re.sub(r'^EDICTE\s+aprovació\s+(?:inicial|definitiva)\s+', '', title, flags=re.I)
            title = title[0].upper() + title[1:]
            key = re.sub(r'[^a-z0-9]+', '-', _norm(title)).strip('-')
            agreement = None
            match = re.search(r'aprovada al ple de data (\d{2}/\d{2}/\d{4})', normalized)
            if match:
                agreement = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
            # The index does not label the 2026 approval as initial/definitive.
            # Keep its phase unknown; the linked certificate provides more detail.
            phase = ('aprobación inicial' if 'aprovacio inicial' in normalized else
                     'aprobación definitiva' if 'aprovacio definitiva' in normalized else None)
            documents = {}
            for a in body.select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                parsed = urlparse(url)
                if (parsed.scheme not in {'http', 'https'} or
                        parsed.hostname not in {'www.moradebre.cat', 'eseu.moradebre.cat'} or
                        not parsed.path.lower().endswith('.pdf')):
                    raise ValueError('Unrecognized document link in instrument panel')
                documents[url] = {
                    'titulo': a.get_text(' ', strip=True) or
                              (a.img.get('alt', '') if a.img else '') or title,
                    'url': url, 'source_url': SOURCE,
                }
            if not documents:
                raise ValueError('Instrument lacks source documents')
            row = {
                'id': 'mora-d-ebre-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': "Móra d'Ebre", 'provincia': 'Tarragona', 'codigo_ine': '43093',
                'titulo': title, 'tipo': 'modificacion_planeamiento', 'fase': phase,
                'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': agreement, 'fecha_aprob': agreement,
                'referencia_temporal_fuente': heading_text,
                'url': SOURCE, 'source': 'ayuntamiento',
                'origen': 'inventario_municipal_modificaciones_nnss',
                'documentos': list(documents.values()),
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False,
                'geometry_status': 'No verified instrument geometry in inventory',
            }
            if key in rows:
                previous = rows[key]
                for field in ('fase', 'fecha_acuerdo', 'fecha_aprob'):
                    if previous[field] != row[field]:
                        raise ValueError('Conflicting instrument entries; review lifecycle grouping')
                merged = {d['url']: d for d in previous['documentos'] + row['documentos']}
                previous['documentos'] = list(merged.values())
            else:
                rows[key] = row
        return list(rows.values())

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        # A browser User-Agent is needed by the public site's HTTP filter.
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; MunicipalInventory/1.0)',
        })
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE.rstrip('/'):
            raise ValueError('Unexpected inventory redirect')
        response.encoding = 'utf-8'
        rows = self.parse_projects(response.text)
        if self.config.get('evidence_dir'):
            captures = Path(self.config['evidence_dir'])
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'modificacions.html').write_bytes(response.content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'Complete single-page NNSS modification inventory; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete current snapshot, including removals; no date-based cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0,
                'reason': 'No verified public register of granted building licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
