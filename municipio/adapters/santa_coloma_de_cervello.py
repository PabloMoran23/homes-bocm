"""Municipal transparency inventories: complete snapshots, grouped instruments."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://seu-e.cat/ca/web/santacolomadecervello/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/'
INVENTORIES = (
    'planejament-urbanistic-en-tramitacio-217',
    'projectes-de-reparcel-lacions-218',
    'projectes-d-obres-219',
)
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
LIMITATIONS = [
    'Partial municipal coverage: only the three published transparency inventories; no exhaustive historic register or RPUC crawl.',
    'Inventory labels describe published stages, not verification that these remain the latest legal stages. No inference of construction or completion.',
    'Document URLs and contextual labels retained; PDF contents and external validation links are not downloaded by the adapter.',
    'Dates are contextual events, not a single approval date; undated and month-only labels remain undated. Page-update dates are not project publication dates.',
    'No verified geometry or coordinates; publication_ready=false. Granted licences are disabled.',
]


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def dates(value):
    """Full explicit dates only: never derive dates from filenames or crawl time."""
    pattern = r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b|\b(\d{1,2})\s+d[e’']?\s*(gener|febrer|març|abril|maig|juny|juliol|agost|setembre|octubre|novembre|desembre)\s+(?:de\s+)?(\d{4})\b"
    found = []
    for m in re.finditer(pattern, value.lower()):
        try:
            d = date(int(m[3]), int(m[2]), int(m[1])) if m[1] else date(int(m[6]), MONTHS[m[5]], int(m[4]))
            if d.isoformat() not in found:
                found.append(d.isoformat())
        except ValueError:
            continue
    return found


class SantaColomaDeCervelloAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.santacolomadecervello.cat')

    @staticmethod
    def parse_inventory(html, source_url):
        soup = BeautifulSoup(html, 'html.parser')
        # The reviewed inventories are static rich text, not a first search page.
        for a in soup.select('a[href]'):
            if ('next' in a.get('rel', []) or text(a).lower() in {'següent', 'siguiente', 'next', 'següents'}
                    or a.find_parent(class_=re.compile(r'pagination|paginacio|pager'))):
                if a['href'] not in {'', '#'}:
                    raise ValueError('Pagination detected; extend traversal before extracting')
        articles = [a for a in soup.select('.journal-content-article') if a.select('a[href*="/documents/"]')]
        if len(articles) != 1:
            raise ValueError('Expected one documented municipal inventory')
        article = articles[0]
        rows = []
        current = None
        for p in article.select('p'):
            heading = next((h for h in p.select('u, strong') if len(text(h)) > 25 and text(h)[0].isalpha()), None)
            if heading:
                title = text(heading)
                if not re.match(r'^(PLA |AVANÇ |TEXT REFÓS |MODIFICACIÓ |APROVACIÓ |PROJECTE |INSTAL·LACIÓ |AMPLIACIÓ |MILLORA )', title):
                    raise ValueError('Unreviewed inventory heading: ' + title)
                current = {
                    'titulo': title, 'documentos': [], 'eventos': [],
                    'contextos': [], 'source_urls': [source_url],
                }
                rows.append(current)
            if not text(p):
                continue
            if current is None:
                raise ValueError('Content before first instrument heading')
            context = text(p)
            current['contextos'].append(context)
            for a in p.select('a[href]'):
                url = urljoin(source_url, a['href'])
                if urlparse(url).scheme != 'https':
                    raise ValueError('Unexpected document URL scheme')
                doc = {'titulo': text(a), 'url': url, 'contexto': context, 'source_url': source_url}
                if not any(d['url'] == url for d in current['documentos']):
                    current['documentos'].append(doc)
            for day in dates(context):
                lower = context.lower()
                kind = ('publicacion' if 'bopb' in lower else 'acuerdo' if any(w in lower for w in ('acord', 'junta', 'ple ', 'decret')) else 'fecha_documento')
                current['eventos'].append({'fecha': day, 'tipo': kind, 'contexto': context, 'source_url': source_url})
        if not rows or any(not r['documentos'] for r in rows):
            raise ValueError('Missing instruments or supporting document links')
        # Fail if markup changes leave document links outside the parsed blocks.
        if {urljoin(source_url, a['href']) for a in article.select('a[href]')} != {d['url'] for r in rows for d in r['documentos']}:
            raise ValueError('Ungrouped inventory document links')
        return rows

    @staticmethod
    def consolidate(rows):
        grouped = {}
        for row in rows:
            # Both pages explicitly describe PAU-1 Font Vella reparcel·lació;
            # their attached documents also share the official folder 18483973.
            key = ('font-vella-pau1-reparcellacio' if any('/28421/18483973/' in d['url'] for d in row['documentos'])
                   else row['titulo'].casefold())
            if key in grouped:
                existing = grouped[key]
                for field in ('documentos', 'eventos', 'contextos', 'source_urls', 'titulos_fuente'):
                    for item in (row.get(field, [row['titulo']]) if field == 'titulos_fuente' else row[field]):
                        if item not in existing[field]:
                            existing[field].append(item)
                continue
            title = row['titulo']
            grouped[key] = {
                **row, 'titulos_fuente': [title],
                'id': 'santa-coloma-de-cervello-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Santa Coloma de Cervelló', 'codigo_ine': '08244', 'provincia': 'Barcelona',
                'tipo': 'reparcelacion' if 'REPARCEL' in title else 'obra_publica' if '/projectes-d-obres-' in row['source_urls'][0] or "URBANITZACIÓ DE TORRE" in title else 'planeamiento_urbanistico',
                'fase': None, 'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': row['source_urls'][0], 'source': 'ayuntamiento', 'origen': 'inventarios_transparencia_municipal',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'cobertura': 'parcial; inventarios municipales publicados',
            }
        return list(grouped.values())

    def backfill_proyectos(self, out_jsonl: Path):
        rows = []
        sources = []
        for inventory in INVENTORIES:
            url = BASE + inventory
            response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-santa-coloma-de-cervello/1.0'}, stream=True)
            with response:
                response.raise_for_status()
                chunks = bytearray()
                for chunk in response.iter_content(65536):
                    chunks.extend(chunk)
                    if len(chunks) > 4_000_000:
                        raise ValueError('Inventory exceeds reviewed response limit')
                html = chunks.decode('utf-8')
            rows.extend(self.parse_inventory(html, url))
            sources.append(url)
            if self.config.get('capture_dir'):
                capture = Path(self.config['capture_dir'])
                capture.mkdir(parents=True, exist_ok=True)
                (capture / (inventory + '.html')).write_text(html, encoding='utf-8')
        records = self.consolidate(rows)
        self._write(out_jsonl, records)
        return {'status': 'ok', 'rows': len(records), 'source_urls': sources, 'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
