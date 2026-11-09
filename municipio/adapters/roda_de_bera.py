"""Municipal works inventories, complete pagination and expediente-level documents."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://web.rodadebera.cat'
SOURCES = (
    BASE + '/territori/urbanisme/obra-publica',
    BASE + '/territori/urbanisme/gestio-urban/projectes-d-urbanitzacio',
)
EXP = re.compile(r'^(?:Exp(?:edient)?\.?\s*)?(\d+)\s*/\s*(\d{3,4})\b', re.I)
LIMITATIONS = [
    'Partial municipal coverage: Obra pública and Projectes d’urbanització only; not all planning or licences.',
    'Inventory years are expediente identifiers, not agreement, publication or approval dates. Dates left null.',
    'Documents are linked with their municipal article provenance; PDF contents and signatures are not parsed.',
    'No verified coordinates or geometry. No inferred execution or approval phase.',
    'Source title/URL discrepancies and malformed expediente years are retained without correction.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _canonical(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))


class RodaDeBeraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html: str, page_url: str, source_url: str):
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.select_one('main table.com-content-category__table')
        if table is None:
            raise ValueError(f'Missing municipal inventory table: {page_url}')
        entries = []
        for row in table.select('tbody tr'):
            anchor = row.select_one('.list-title a[href]')
            if anchor is None:
                raise ValueError(f'Unrecognised inventory row: {page_url}')
            title = _text(anchor)
            url = _canonical(urljoin(page_url, anchor['href']))
            if not EXP.match(title) or not url.startswith(source_url + '/'):
                raise ValueError(f'Unexpected inventory entry: {title!r}')
            entries.append({'titulo': title, 'url': url, 'inventario': source_url})
        if not entries:
            raise ValueError(f'Empty inventory: {page_url}')
        pages = set()
        for a in soup.select('main .pagination a[href], main a[rel="next"][href]'):
            href = a['href']
            if href.startswith('#'):
                continue
            url = _canonical(urljoin(page_url, href))
            parts = urlsplit(url)
            query = parse_qs(parts.query)
            if (parts.scheme != 'https' or parts.netloc != urlsplit(source_url).netloc
                    or parts.path != urlsplit(source_url).path
                    or set(query) - {'start'}
                    or ('start' in query and (len(query['start']) != 1 or not query['start'][0].isdigit()))):
                raise ValueError(f'Unexpected pagination URL: {url}')
            pages.add(url)
        return entries, sorted(pages)

    @staticmethod
    def parse_detail(html: str, entry: dict[str, str]) -> dict[str, Any]:
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.select_one('main .com-content-article h1')
        body = soup.select_one('main .com-content-article__body')
        if heading is None or body is None:
            raise ValueError(f'Missing works article: {entry["url"]}')
        title = _text(heading)
        match = EXP.match(title)
        listed = EXP.match(entry['titulo'])
        if not match or not listed or match.groups() != listed.groups():
            raise ValueError(f'Article/inventory expediente mismatch: {entry["url"]}')
        documents = {}
        for a in body.select('a[href]'):
            url = _canonical(urljoin(entry['url'], a['href']))
            parts = urlsplit(url)
            if parts.scheme not in {'https', 'http'}:
                continue
            if '/uploads/' in parts.path or re.search(r'\.(?:pdf|zip|rar|docx?|xlsx?)(?:$)', parts.path, re.I):
                documents.setdefault(url, {'titulo': _text(a) or a.get('title', ''),
                                          'url': url, 'pagina_origen': entry['url']})
        if not documents:
            raise ValueError(f'Works article has no source documents: {entry["url"]}')
        # A three-digit year is a real source typo, not a date to repair.
        expediente = str(int(match[1])) + '/' + match[2]
        return {
            'id': 'roda-de-bera-proy-' + expediente.replace('/', '-'),
            'municipio': 'Roda de Berà', 'codigo_ine': '43131', 'provincia': 'Tarragona',
            'expediente': expediente, 'expediente_original': match[0],
            'titulo': title, 'tipo': 'proyecto de urbanización' if entry['inventario'] == SOURCES[1] else 'obra pública',
            'fase': None, 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': entry['url'], 'source': 'ayuntamiento', 'origen': 'inventario_municipal_obras',
            'descripcion': _text(body), 'documentos': list(documents.values()),
            'fuentes': [{**entry, 'titulo_articulo': title}],
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'No verified project geometry from these inventories',
        }

    @staticmethod
    def group_projects(records):
        grouped = {}
        for record in records:
            key = record['expediente']
            if key not in grouped:
                grouped[key] = record
                continue
            target = grouped[key]
            target['fuentes'].extend(record['fuentes'])
            target['descripcion'] += '\n' + record['descripcion']
            known = {(d['url'], d['pagina_origen']) for d in target['documentos']}
            target['documentos'].extend(d for d in record['documentos'] if (d['url'], d['pagina_origen']) not in known)
        return list(grouped.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        fetched = []
        session = requests.Session()
        session.headers['User-Agent'] = 'municipio-roda-de-bera/1.0 (public municipal works research)'

        def fetch(url):
            with session.get(url, timeout=45, stream=True) as response:
                response.raise_for_status()
                if _canonical(response.url) != url:
                    raise ValueError(f'Unexpected source redirect: {url} -> {response.url}')
                raw = bytearray()
                for chunk in response.iter_content(65536):
                    raw.extend(chunk)
                    if len(raw) > 4_000_000:
                        raise ValueError(f'Source exceeds response bound: {url}')
                html = raw.decode('utf-8-sig')
            capture = None
            if captures:
                directory = Path(captures)
                directory.mkdir(parents=True, exist_ok=True)
                capture = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
                (directory / capture).write_bytes(raw)
            fetched.append({'url': url, 'capture': capture, 'sha256': hashlib.sha256(raw).hexdigest()})
            return html

        try:
            entries = {}
            page_counts = {}
            for source in SOURCES:
                pending, seen, signatures = [source], set(), set()
                while pending:
                    url = pending.pop(0)
                    if url in seen:
                        continue
                    if len(seen) >= 100:
                        raise ValueError('Pagination exceeds safety bound; no partial output written')
                    items, pages = self.parse_inventory(fetch(url), url, source)
                    signature = tuple(item['url'] for item in items)
                    if signature in signatures:
                        raise ValueError('Repeated inventory page: pagination may be ignored')
                    signatures.add(signature)
                    seen.add(url)
                    for item in items:
                        entries.setdefault(item['url'], item)
                    pending.extend(page for page in pages if page not in seen and page not in pending)
                page_counts[source] = len(seen)
            rows = self.group_projects([self.parse_detail(fetch(item['url']), item) for item in entries.values()])
            self._write(out_jsonl, rows)
            result = {'status': 'ok', 'rows': len(rows), 'live_records': len(rows),
                      'inventory_pages': page_counts, 'articles': len(entries),
                      'source_urls': list(SOURCES), 'fetched_sources': fetched,
                      'limitations': LIMITATIONS, 'publication_ready': False}
            if captures:
                (Path(captures) / 'extraction.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            return result
        finally:
            session.close()

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # These mutable inventories are refreshed as a complete snapshot.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
