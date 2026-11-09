"""Alaró's public planning inventory: instruments, not application forms."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://ajalaro.net/ca/normes-subsidiaries-de-planejament'
LIMITATIONS = [
    'Partial coverage: municipal planning inventory only; no works or granted-licence register.',
    'Generic Estudis de detall folder excluded: no individually named instruments in the index.',
    'Google Drive folders are retained as municipal references, not enumerated or authenticated.',
    'PDF contents and viewer geometry are not parsed; no coordinates inferred.',
    'Dates on download cards are upload metadata, not instrument publication or approval dates.',
]


def clean(text):
    return ' '.join(text.split())


def parse_date(value):
    d, m, y = map(int, value.split('.'))
    return date(y, m, d).isoformat()


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    # These inventories are unpaginated today. Fail explicitly if that changes.
    if soup.select('.pager, .pagination, a[rel~=next], link[rel~=next]'):
        raise ValueError('Unexpected pagination: inventory cannot be treated as complete')
    body = soup.select_one('#block-consell-main-content article')
    if body is None:
        raise ValueError('Missing municipal article (possibly login or changed markup)')
    return body


def links(node, source):
    result = []
    for a in node.select('a[href]'):
        target = urljoin(source, a['href'].strip())
        # The municipal www host currently resolves document paths to its home page.
        if urlparse(target).hostname == 'www.ajalaro.net':
            target = target.replace('://www.ajalaro.net/', '://ajalaro.net/', 1)
        if urlparse(target).scheme not in ('https', 'http'):
            raise ValueError('Unexpected document URL')
        item = {'titulo': clean(a.get_text(' ', strip=True)), 'url': target, 'source_url': source}
        if target not in [x['url'] for x in result]:
            result.append(item)
    return result


def parse_inventory(html, source=SOURCE):
    body = content(html).select_one('.prose')
    if body is None:
        raise ValueError('Missing planning inventory')
    rows, phase, current = [], None, None
    for block in body.find_all(['p', 'ul'], recursive=False):
        text = clean(block.get_text(' ', strip=True))
        if text == 'Planejament definitivament aprovat:':
            phase, current = 'aprobación definitiva', None
            continue
        if text == 'Planejament en revisió/tramitació:':
            phase, current = 'en revisión/tramitación', None
            continue
        if block.name == 'p':
            if current:
                current['documentos'].extend(links(block, source))
            continue
        if not phase:
            raise ValueError('Instrument without explicit inventory section')
        for li in block.find_all('li', recursive=False):
            text = clean(li.get_text(' ', strip=True))
            if text == 'Estudis de detall':
                current = None
                continue
            if not re.match(r'^(Normes Subsidiàries|Correcció d’error material|Modificació puntual|MP )', text):
                raise ValueError(f'Unrecognized inventory item: {text}')
            match = re.search(r'\(A\.D\.\s*(\d{2}\.\d{2}\.\d{4})\)', text)
            approval = parse_date(match[1]) if match else None
            title = re.sub(r'\s*\(A\.D\..*?\)\s*:?', '', text).rstrip(':').strip()
            key = 'alaro-plan-' + hashlib.sha256(title.encode()).hexdigest()[:16]
            current = {
                'id': key, 'municipio': 'Alaró', 'codigo_ine': '07001', 'provincia': 'Illes Balears',
                'titulo': title, 'tipo': 'instrumento de planeamiento', 'fase': phase,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': approval, 'fecha_aprob_source_url': source if approval else None,
                'url': source, 'inventory_url': source, 'descripcion': text,
                'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
                'documentos': links(li, source), 'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'geometry_status': 'unavailable',
            }
            rows.append(current)
    if not rows or {r['fase'] for r in rows} != {'aprobación definitiva', 'en revisión/tramitación'}:
        raise ValueError('Missing planning sections or instruments')
    # Repeat entries must not silently become separate instruments.
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate planning identity in inventory')
    if any(not r['documentos'] for r in rows):
        raise ValueError('Instrument without supporting document reference')
    return rows


def parse_documents(html, source):
    body = content(html)
    documents = []
    for a in body.select('section.multimedia--documents a[download][href]'):
        card = a.parent
        heading = card.find('h3')
        if heading is None:
            raise ValueError('Document without title')
        documents.append({'titulo': clean(heading.get_text(' ', strip=True)),
                          'url': urljoin(source, a['href']), 'source_url': source})
    if not documents:
        raise ValueError(f'Empty municipal document inventory: {source}')
    return documents


class AlaroAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='alaro', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://ajalaro.net')

    def _fetch(self, url):
        with requests.get(url, timeout=40, stream=True, headers={
            'User-Agent': 'municipio-alaro/1.0 (public planning inventory)'
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname not in ('ajalaro.net', 'www.ajalaro.net'):
                raise ValueError('Unexpected municipal source redirect')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Municipal HTML exceeds response size limit')
            html = bytes(data).decode('utf-8')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(html, encoding='utf-8')
        return html

    def backfill_proyectos(self, out_jsonl: Path):
        rows = parse_inventory(self._fetch(SOURCE))
        source_urls, cache = [SOURCE], {}
        for row in rows:
            for doc in list(row['documentos']):
                parsed = urlparse(doc['url'])
                if parsed.hostname in ('ajalaro.net', 'www.ajalaro.net') and parsed.path.startswith('/ca/arxius-i-documents/'):
                    if doc['url'] not in cache:
                        cache[doc['url']] = parse_documents(self._fetch(doc['url']), doc['url'])
                        source_urls.append(doc['url'])
                    row['documentos'].extend(cache[doc['url']])
                elif parsed.hostname == 'ajalaro.net' and parsed.path == '/ca/cataleg-delements-i-espais-protegits':
                    detail_url = doc['url']
                    detail = content(self._fetch(detail_url)).select_one('.prose')
                    if detail is None:
                        raise ValueError('Missing catalogue description')
                    text = clean(detail.get_text(' ', strip=True))
                    match = re.search(r'Aprovació inicial (\d{2}\.\d{2}\.\d{4})', text)
                    if not match:
                        raise ValueError('Catalogue no longer exposes initial approval')
                    row.update(fase='aprobación inicial', fecha_aprob=parse_date(match[1]),
                               fecha_aprob_source_url=detail_url, fase_source_url=detail_url)
                    row['documentos'].extend(links(detail, detail_url))
                    source_urls.append(detail_url)
            # Only explicit BOIB document labels establish publication, never card/upload dates.
            publications = []
            for doc in row['documentos']:
                label = doc['titulo'] + ' ' + unquote(doc['url'].rsplit('/', 1)[-1])
                match = re.search(r'BOIB.*?\bde\s+(\d{2}\.\d{2}\.\d{4})', label)
                if match:
                    publications.append((parse_date(match[1]), doc['url']))
            if len({p[0] for p in publications}) == 1:
                row['fecha_publicacion'], row['fecha_publicacion_source_url'] = publications[0]
            row['documentos'] = list({doc['url']: doc for doc in row['documentos']}.values())
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'live_records': len(rows), 'source_urls': source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full replacement snapshot; no timestamp-based omission of older instruments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        Path(out_jsonl).parent.mkdir(parents=True, exist_ok=True)
        Path(out_jsonl).write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
