"""Anonymous municipal derived-planning inventory; documents grouped by folder.

This is a complete refresh of the derived-planning branch, not a licence register
or a statement that every instrument in the directory remains legally in force.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit, urlencode

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

LANDING = 'https://www.ametllamar.cat/ajuntament/per-temes/urbanisme/'
ROOT = 'https://ametllamar.cat/ajuntament/backoffice/seccions/urbanisme/'
BRANCH = '03. Planejament derivat'
LIMITATIONS = [
    'Only the municipal derived-planning directory is covered; POUM, POUM amendments, '
    'consolidated urban area, acoustic map, public works and other inventories are outside this snapshot.',
    'Folder bundles retain versions and amendments; listing presence does not establish legal validity or approval.',
    'PDF/DOC contents are linked, not parsed. Publication/agreement/approval dates and geometry are unknown. '
    'File modification timestamps are document metadata only.',
    'No granted-licence register is extracted. No coordinates or municipal centroid are substituted.',
]


def directory_url(directory: str) -> str:
    return ROOT + '?' + urlencode({'dir': directory})


def parse_listing(html: str, directory: str) -> tuple[list[str], list[dict]]:
    """Read only actual listing rows, rejecting pagination and escaping paths."""
    soup = BeautifulSoup(html, 'html.parser')
    listing = soup.select_one('#directory-listing')
    if listing is None:
        raise ValueError('Missing municipal directory listing')
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        href = a['href']
        if (set(a.get('rel', [])) & {'next', 'prev'} or
                label in {'next', 'siguiente', 'següent', 'anterior', '›', '»'} or
                any(k in parse_qs(urlsplit(href).query) for k in ('page', 'offset', 'start'))):
            raise ValueError('Pagination detected; refusing a partial directory snapshot')
    folders, documents = set(), {}
    for row in listing.select('li[data-name][data-href]'):
        name, href = row['data-name'], row['data-href']
        if name == '..':
            continue
        parts = urlsplit(urljoin(ROOT, href))
        if parts.hostname != 'ametllamar.cat' or not parts.path.startswith(urlsplit(ROOT).path):
            raise ValueError('Directory entry leaves official municipal source')
        query = parse_qs(parts.query)
        if 'dir' in query:
            child = query['dir'][0]
            if '..' in PurePosixPath(child).parts or (directory and not child.startswith(directory + '/')):
                raise ValueError('Unexpected directory traversal')
            folders.add(child)
            continue
        path = unquote(parts.path)
        relative = path[len(urlsplit(ROOT).path):]
        if '..' in PurePosixPath(relative).parts or (directory and not relative.startswith(directory + '/')):
            raise ValueError('Document leaves selected directory')
        if PurePosixPath(relative).suffix.lower() not in {'.pdf', '.doc', '.docx'}:
            continue  # e.g. Thumbs.db is not a planning document
        stamp = row.select_one('.file-modified')
        url = ROOT + quote(relative, safe='/')
        documents[url] = {
            'titulo': name, 'url': url,
            'source_url': directory_url(directory),
            'source_path': relative,
            'fecha_modificacion_archivo': stamp.get_text(strip=True) if stamp else None,
        }
    return sorted(folders), list(documents.values())


def collect_projects(fetch) -> tuple[list[dict], list[str]]:
    """Dependency-injected fetch enables offline tests of complete traversal."""
    landing = BeautifulSoup(fetch(LANDING), 'html.parser')
    if not any(urljoin(LANDING, frame.get('src', '')).rstrip('/') == ROOT.rstrip('/')
               for frame in landing.select('iframe[src]')):
        raise ValueError('Municipal page no longer endorses the expected inventory')
    root_folders, _ = parse_listing(fetch(ROOT), '')
    if BRANCH not in root_folders:
        raise ValueError('Derived-planning branch missing')
    source_urls = [LANDING, ROOT, directory_url(BRANCH)]
    instruments, loose = parse_listing(fetch(directory_url(BRANCH)), BRANCH)
    if loose or not instruments:
        raise ValueError('Derived-planning structure changed; review loose documents or empty inventory')
    visited, rows = set(), []
    for instrument in instruments:
        pending, docs = [instrument], {}
        while pending:
            directory = pending.pop()
            if directory in visited:
                continue
            if len(visited) >= 200:
                raise ValueError('Directory safety limit exceeded; no partial output written')
            visited.add(directory)
            url = directory_url(directory)
            source_urls.append(url)
            children, files = parse_listing(fetch(url), directory)
            pending.extend(children)
            docs.update((d['url'], d) for d in files)
        if not docs:
            raise ValueError('Planning folder lacks usable documents: ' + instrument)
        title = instrument.rsplit('/', 1)[-1]
        rows.append({
            'id': 'l-ametlla-de-mar-proy-' + hashlib.sha256(instrument.encode()).hexdigest()[:16],
            'municipio': "L'Ametlla de Mar", 'codigo_ine': '43013', 'provincia': 'Tarragona',
            'titulo': title, 'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': directory_url(instrument), 'source': 'ayuntamiento',
            'origen': 'directorio_municipal_planejament_derivat',
            'documentos': sorted(docs.values(), key=lambda d: d['url']),
            'source_path': instrument, 'source_inventory_url': directory_url(BRANCH),
            'source_landing_url': LANDING,
            'coverage': 'Municipal folder bundle including associated versions and amendments; legal status unverified',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        })
    return rows, source_urls


class LAmetllaDeMarAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.ametllamar.cat')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        captures = self.config.get('capture_dir')
        session = requests.Session()
        session.headers['User-Agent'] = 'municipio-l-ametlla-de-mar/1.0 (public planning inventory)'

        def fetch(url):
            with session.get(url, timeout=(10, 40), stream=True) as response:
                response.raise_for_status()
                final = urlsplit(response.url)
                if final.scheme != 'https' or final.hostname not in {'ametllamar.cat', 'www.ametllamar.cat'}:
                    raise ValueError('Unexpected source redirect')
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 4_000_000:
                        raise ValueError('Directory exceeds response limit; refusing truncation')
                    chunks.append(chunk)
                raw = b''.join(chunks)
                if captures:
                    target = Path(captures)
                    target.mkdir(parents=True, exist_ok=True)
                    key = hashlib.sha256(url.encode()).hexdigest()[:16]
                    (target / (key + '.html')).write_bytes(raw)
                    (target / (key + '.url.txt')).write_text(url, encoding='utf-8')
                return raw.decode('utf-8')

        try:
            rows, urls = collect_projects(fetch)
        finally:
            session.close()
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
