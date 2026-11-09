"""Cazorla's municipal IDAE project inventory (partial municipal coverage)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


SOURCE = 'https://cazorla.es/proyectos-que-favorecen-una-economia-baja-en-carbono-idae/'
HEADERS = ('DENOMINACIÓN PROYECTO', 'Nº EXP. IDAE', 'INVERSIÓN TOTAL',
           'FINANCIACIÓN FONDOS FEDER', 'APORTACIÓN MUNICIPAL')


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.page')
    if article is None:
        raise ValueError('Municipal inventory article missing')
    # This is a single-page table, not the paginated municipal news feed.
    if soup.select('a[rel~=next], .pagination a, .page-numbers, .page-links a'):
        raise ValueError('Pagination detected; review crawler before extracting')
    for a in article.select('a[href]'):
        if re.search(r'siguiente|entradas más antiguas|next', text(a), re.I):
            raise ValueError('Pagination detected in inventory')
    tables = []
    for table in article.select('table'):
        first = table.find('tr')
        cells = first.find_all(['td', 'th'], recursive=False) if first else []
        if len(cells) == 5 and all(h in text(c).upper() for h, c in zip(HEADERS, cells)):
            tables.append(table)
    if len(tables) != 1:
        raise ValueError('Expected one identifiable IDAE inventory table')
    records = {}
    for tr in tables[0].find_all('tr')[1:]:
        cells = tr.find_all(['td', 'th'], recursive=False)
        if len(cells) != 5:
            raise ValueError('Malformed IDAE project row')
        title, expediente, total, feder, municipal = map(text, cells)
        if not title or not re.fullmatch(r'\d+', expediente):
            raise ValueError('Missing project title or IDAE expediente')
        if not all(re.fullmatch(r'[\d.]+,\d{2}\s*€', v) for v in (total, feder, municipal)):
            raise ValueError('Unrecognised source investment amounts')
        documents = [{'titulo': 'Inventario municipal de proyectos IDAE', 'url': url,
                      'formato': 'text/html', 'localizador': 'Nº EXP. IDAE: ' + expediente}]
        for a in tr.select('a[href]'):
            target = urljoin(url, a['href'])
            if urlparse(target).scheme in {'https', 'http'}:
                doc = {'titulo': text(a) or title, 'url': target}
                if doc not in documents:
                    documents.append(doc)
        row = {'id': 'cazorla-idae-' + expediente, 'municipio': 'Cazorla',
               'codigo_ine': '23028', 'provincia': 'Jaén', 'titulo': title,
               'expediente_idae': expediente, 'tipo': 'proyecto_eficiencia_energetica',
               'url': url, 'inventory_url': url, 'source': 'ayuntamiento',
               'origen': 'inventario_municipal_idae', 'documentos': documents,
               'inversion_total_texto': total, 'financiacion_feder_texto': feder,
               'aportacion_municipal_texto': municipal,
               'publication_ready': False, 'geometry_status': 'unavailable'}
        if expediente in records:
            previous = records[expediente]
            if {k: v for k, v in previous.items() if k != 'documentos'} != {
                    k: v for k, v in row.items() if k != 'documentos'}:
                raise ValueError('Conflicting rows for IDAE expediente ' + expediente)
            for doc in documents:
                if doc not in previous['documentos']:
                    previous['documentos'].append(doc)
        else:
            records[expediente] = row
    if not records:
        raise ValueError('Empty IDAE inventory')
    return list(records.values())


class CazorlaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'municipal-inventory/1.0 (public project research)'})
        response.raise_for_status()
        if (urlparse(response.url).hostname != 'cazorla.es'
                or urlparse(response.url).path.rstrip('/') != urlparse(SOURCE).path.rstrip('/')):
            raise ValueError('Unexpected inventory redirect')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected HTML inventory')
        rows = parse_inventory(response.content, response.url)
        if self.config.get('evidence_dir'):
            evidence = Path(self.config['evidence_dir'])
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / 'idae-live.html').write_bytes(response.content)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [response.url],
                'coverage': 'municipal_idae_project_table', 'publication_ready': False}

    @staticmethod
    def _write(path: Path, rows: list[dict]):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
