"""Montserrat (Valencia): complete snapshot of its GVA planning directory.

One record per registered instrument, not one per PDF. Dates inside the PDF
documents are not parsed; directory timestamps are never agreement dates.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/'
          '4%20VALENCIA/46172%20MONTSERRAT/')
MUNICIPAL_SOURCE = 'https://montserrat.es/ajuntament/'
LIMITATIONS = [
    'Partial municipal coverage: only instruments in the GVA municipal directory; '
    'not a complete works, licence or historical planning register.',
    'PDF contents are linked, not parsed: agreement, approval and publication '
    'dates and current legal effectiveness remain unverified.',
    'No verified vector geometry or coordinates; publication_ready is false.',
]


def parse_directory(html: str, url: str) -> list[dict]:
    """Parse Apache's full index; reject changed markup and pagination."""
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1#indextitle')
    expected = unquote(urlsplit(url).path).rstrip('/')
    if not heading or heading.get_text(' ', strip=True) != 'Index of ' + expected:
        raise ValueError('Missing or mismatched GVA directory heading')
    if not soup.select_one('table#indexlist'):
        raise ValueError('Missing GVA directory table')
    if soup.select('[rel~=next], .pagination, .nav-links'):
        raise ValueError('Unexpected pagination: inventory cannot be truncated')
    entries = {}
    for a in soup.select('td.indexcolname a[href]'):
        href = a['href']
        if href == '../':
            continue
        target = urljoin(url, href)
        parsed = urlsplit(target)
        # Keep original percent escapes (GVA uses Latin-1 filenames). Never
        # unquote/re-encode document URLs, which would break accented names.
        relative = unquote(parsed.path)[len(expected) + 1:]
        if (parsed.netloc != urlsplit(SOURCE).netloc or parsed.query or parsed.fragment
                or not unquote(parsed.path).startswith(expected + '/')
                or any(part in ('.', '..') for part in relative.split('/'))):
            raise ValueError('Out-of-directory entry: ' + target)
        title = a.get_text(' ', strip=True).rstrip('/')
        if not title:
            raise ValueError('Untitled inventory entry')
        entries[target] = {'titulo': title, 'url': target,
                           'directory': parsed.path.endswith('/')}
    if not entries:
        raise ValueError('Empty directory; refusing an incomplete snapshot')
    return list(entries.values())


def collect_projects(fetch) -> tuple[list[dict], list[str]]:
    """Traverse every category, dossier and nested document folder.

    The guard raises instead of emitting a partial result. The current source
    exposes P. GENERAL; unknown categories require explicit parser review.
    """
    visited = []

    def directory(url):
        if url in visited or len(visited) >= 250:
            raise ValueError('Directory cycle or safety limit; snapshot aborted')
        visited.append(url)
        return parse_directory(fetch(url), url)

    rows = []
    for category in directory(SOURCE):
        if not category['directory'] or not re.fullmatch(r'\d+ P\. GENERAL', category['titulo']):
            raise ValueError('Unsupported planning category: ' + category['titulo'])
        for instrument in directory(category['url']):
            match = re.fullmatch(r'(46172-\d+) PG (\d{4}-\d+)', instrument['titulo'])
            if not instrument['directory'] or not match:
                raise ValueError('Unrecognized instrument identity: ' + instrument['titulo'])
            pending = [instrument['url']]
            documents = {}
            while pending:
                page = pending.pop(0)
                for entry in directory(page):
                    if entry['directory']:
                        pending.append(entry['url'])
                    else:
                        if not urlsplit(entry['url']).path.lower().endswith('.pdf'):
                            raise ValueError('Unexpected document format: ' + entry['url'])
                        documents[entry['url']] = {
                            'titulo': entry['titulo'], 'url': entry['url'],
                            'inventory_url': page, 'publisher': 'Generalitat Valenciana',
                        }
            if not documents:
                raise ValueError('Instrument has no documents')
            rows.append({
                'id': 'montserrat-plan-' + hashlib.sha256(instrument['url'].encode()).hexdigest()[:16],
                'municipio': 'Montserrat', 'codigo_ine': '46172', 'provincia': 'Valencia',
                'titulo': 'Plan General de Montserrat — ' + instrument['titulo'],
                'tipo': 'Plan General', 'expediente': match[2],
                'registro_planeamiento_id': match[1],
                'source': 'generalitat-valenciana', 'origen': 'registro_planeamiento',
                'url': instrument['url'], 'inventory_url': SOURCE,
                'municipal_source_url': MUNICIPAL_SOURCE,
                'documentos': sorted(documents.values(), key=lambda doc: doc['url']),
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None,
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'geometry_status': 'unavailable',
                'coverage': 'GVA published planning document inventory',
                'limitations': LIMITATIONS,
            })
    if not rows:
        raise ValueError('No real planning instruments found')
    return sorted(rows, key=lambda row: row['id']), visited


class MontserratAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='montserrat', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)
        if slug != 'montserrat' or str(self.config.get('ine_code', '46172')) != '46172':
            raise ValueError('Adapter restricted to Montserrat, Valencia, INE 46172')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        captures = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-montserrat/1.0'

            def fetch(url):
                with session.get(url, timeout=(10, 30), stream=True) as response:
                    response.raise_for_status()
                    if response.url != url:
                        raise ValueError('Unexpected directory redirect')
                    body = bytearray()
                    for chunk in response.iter_content(65536):
                        body.extend(chunk)
                        if len(body) > 4_000_000:
                            raise ValueError('Oversized inventory; snapshot aborted')
                    # The live GVA directory declares no charset and serves
                    # ISO-8859-1 names, including INSCRIPCIÓN and SITUACIÓN.
                    html = body.decode('iso-8859-1')
                    if captures:
                        path = Path(captures)
                        path.mkdir(parents=True, exist_ok=True)
                        key = hashlib.sha256(url.encode()).hexdigest()[:16]
                        (path / (key + '.html')).write_bytes(body)
                        (path / (key + '.url')).write_text(url + '\n', encoding='utf-8')
                    return html

            rows, source_urls = collect_projects(fetch)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        # Write only after traversal succeeds; failures preserve the last snapshot.
        temporary = output.with_suffix('.jsonl.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(output)
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': source_urls, 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'count': 0,
                'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
