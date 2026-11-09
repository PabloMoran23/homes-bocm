"""Public technical-project folders in Llançà's current transparency inventory."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'llanca.eadministracio.cat'
SOURCE = f'https://{HOST}/transparency/330458c5-008e-4021-b597-b61b6f6d3bf6/'
LIMITATIONS = [
    'Partial municipal coverage: current WEB - Projectes Tècnics inventory only; legacy works and planning inventories excluded.',
    'Empty project folders are reported separately, not emitted as documented projects.',
    'Document titles and descriptions are inventory metadata; linked document contents and geometry are not parsed.',
    'Publication and agreement dates are unknown; years and dates embedded in document labels are not approval dates.',
    'No verified granted-licence register or project coordinates; licences and scheduling disabled.',
]


def _official(url: str, prefix: str) -> str:
    p = urlparse(url)
    if p.scheme != 'https' or p.netloc != HOST or not p.path.startswith(prefix):
        raise ValueError(f'Unexpected municipal source URL: {url}')
    return url


def parse_inventory(html: str) -> dict:
    """Parse one complete folder; reject changed markup or pagination."""
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.TransparencyListPanel')
    if table is None:
        raise ValueError('Missing public transparency inventory table')
    # The reviewed source has no pagination. Fail closed if controls appear.
    if soup.select('.pagination, .navigator, .paging, [rel="next"], [rel="prev"]'):
        raise ValueError('Pagination detected; crawler must be extended before extraction')
    for a in soup.select('a[href], a[onclick]'):
        label = ' '.join([a.get_text(' ', strip=True), a.get('title', ''), a.get('aria-label', '')]).lower()
        if re.search(r'\b(next|previous|següent|següents|siguiente|anterior|última|last)\b', label):
            raise ValueError('Pagination detected; refusing partial output')
    folders, documents, external = [], [], []
    for cell in table.select('td.class_name'):
        a = cell.select_one('a.gIconLink.exp')
        if a is not None:
            badge = a.select_one('.linkExtraInfo')
            if badge is None or not re.fullmatch(r'\s*\(\s*\d+\s*\)\s*', badge.text):
                raise ValueError('Missing folder document count')
            count = int(re.search(r'\d+', badge.text)[0])
            badge.extract()
            title = a.get_text(' ', strip=True)
            callback = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
            if not callback or not title:
                raise ValueError('Unresolvable public folder')
            folders.append({'titulo': title, 'count': count, 'callback': callback[1]})
            continue
        a = cell.select_one('a[href*="/preview-document/"]')
        if a is not None:
            documents.append({'titulo': a.get_text(' ', strip=True),
                              'descripcion': a.get('title') or None,
                              'url': _official(a['href'], '/preview-document/')})
            continue
        a = cell.select_one('a.extUrl[href]')
        if a is not None:
            external.append({'titulo': a.get_text(' ', strip=True), 'url': a['href']})
            continue
        if cell.get_text(' ', strip=True):
            raise ValueError('Unsupported inventory entry; refusing incomplete extraction')
    if len({d['url'] for d in documents}) != len(documents):
        raise ValueError('Duplicate document identifiers in folder')
    return {'folders': folders, 'documentos': documents, 'external': external}


def project_record(title: str, url: str, year: str, documents: list[dict]) -> dict:
    match = re.match(r'Exp(?:edient|\.)\s*(\d+/\d{2,4})\s*[-–]?\s*(.+)', title, re.I)
    if not match or not documents:
        raise ValueError('Project requires an actual dossier and linked documentation')
    if (not re.search(r'\b(projecte|memòria|memoria)\b', match[2], re.I)
            or re.search(r'\b(sol·licitud|formulari|licitació|contractació)\b', match[2], re.I)):
        raise ValueError('Unsupported project title; review municipal inventory coverage')
    return {
        'id': 'llanca-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Llançà', 'codigo_ine': '17092', 'provincia': 'Girona',
        'titulo': match[2], 'expediente': match[1], 'titulo_origen': title,
        'tipo': 'proyecto_obra_publica', 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'source': 'ayuntamiento', 'origen': 'inventario_proyectos_tecnicos',
        'url': url, 'source_inventory': SOURCE, 'inventory_year': year,
        'documentos': documents, 'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False,
    }


class LlancaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or f'https://{HOST}')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        captures = self.config.get('capture_dir')
        source_urls, visited, empty, rows = [], set(), [], {}
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-llanca/1.0'

            def get(url, ajax=False):
                _official(url, '/' if ajax else '/transparency/')
                response = session.get(url, timeout=30, headers={'Wicket-Ajax': 'true'} if ajax else {}, stream=True)
                response.raise_for_status()
                _official(response.url, '/' if ajax else '/transparency/')
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 4_000_000:
                        raise ValueError('Municipal response exceeds reviewed size limit')
                    chunks.append(chunk)
                payload = b''.join(chunks)
                response.close()
                if not ajax:
                    source_urls.append(url)
                    if captures:
                        target = Path(captures)
                        target.mkdir(parents=True, exist_ok=True)
                        (target / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(payload)
                return response, payload.decode(response.encoding or 'utf-8')

            def open_folder(parent, entry):
                # Wicket returns an Ajax-Location header pointing at a stable,
                # anonymous folder URL. Callback tokens are session-local only.
                response, _ = get(urljoin(parent, entry['callback']), ajax=True)
                location = response.headers.get('Ajax-Location')
                if not location:
                    raise ValueError('Public folder callback did not return Ajax-Location')
                return _official(urljoin(parent, location), '/transparency/')

            def visit(url):
                if url in visited:
                    raise ValueError('Duplicate/cyclic inventory folder')
                visited.add(url)
                if len(visited) > 500:
                    raise ValueError('Inventory exceeds reviewed traversal limit')
                _, html = get(url)
                return parse_inventory(html)

            root = visit(SOURCE)
            if not root['folders'] or root['documentos']:
                raise ValueError('Expected current technical-project year folders')
            for year in root['folders']:
                if not re.fullmatch(r'20\d{2}', year['titulo']):
                    raise ValueError('Unexpected technical-project year category')
                year_url = open_folder(SOURCE, year)
                inventory = visit(year_url)
                if inventory['documentos'] or inventory['external']:
                    raise ValueError('Unexpected year-level documents or external folders')
                if sum(e['count'] for e in inventory['folders']) != year['count']:
                    raise ValueError('Year document count mismatch; possible pagination')
                for entry in inventory['folders']:
                    url = open_folder(year_url, entry)
                    detail = visit(url)
                    if detail['folders'] or detail['external']:
                        raise ValueError('Nested/external project documents need further traversal')
                    docs = detail['documentos']
                    if len(docs) != entry['count']:
                        raise ValueError('Project document count mismatch; possible pagination')
                    if not docs:
                        empty.append({'titulo': entry['titulo'], 'url': url})
                        continue
                    row = project_record(entry['titulo'], url, year['titulo'], docs)
                    if row['expediente'] in rows:
                        raise ValueError('Repeated dossier across year folders; grouping requires review')
                    rows[row['expediente']] = row
        if not rows:
            raise ValueError('No documented municipal projects found')
        self._write(out_jsonl, list(rows.values()))
        return {'status': 'ok', 'rows': len(rows), 'source_urls': source_urls,
                'empty_folders': empty, 'limitations': LIMITATIONS,
                'external_inventory_links': root['external']}

    @staticmethod
    def _write(path: Path, rows: list[dict]):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
