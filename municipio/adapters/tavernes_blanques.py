"""Tavernes Blanques planning instruments in the official Generalitat register."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/'
          '4%20VALENCIA/46237%20TAVERNES%20BLANQUES/')
LIMITATIONS = [
    'Inventario documental del registro autonómico; no historial municipal completo.',
    'Se excluye la carpeta EXPEDIENTES ANULADOS y sus descendientes.',
    'No cubre el nuevo PGE/POP en tramitación anunciado en 2026 fuera de este inventario.',
    'No se acredita vigencia jurídica, ejecución física ni concesión de licencias.',
    'Sin fechas extraídas de los PDF ni coordenadas; años y códigos del nombre no son fechas.',
]


def decode_html(content: bytes) -> str:
    # The server declares UTF-8 but directory filenames contain Latin-1 bytes.
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        return content.decode('latin-1')


def parse_directory(html: str, url: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1#indextitle')
    table = soup.select_one('table#indexlist')
    if not heading or not heading.get_text(strip=True).startswith('Index of /') or not table:
        raise ValueError(f'Unexpected register directory: {url}')
    for a in soup.select('a[href]'):
        if ('next' in a.get('rel', []) or
                a.get_text(' ', strip=True).casefold() in {'next', 'siguiente', '»', '›'}):
            raise ValueError(f'Pagination requires review: {url}')
    entries = {}
    for a in table.select('td.indexcolname a[href]'):
        href = a['href']
        target = urljoin(url, href)
        parsed = urlparse(target)
        if parsed.query or parsed.fragment:
            raise ValueError(f'Unexpected listing query: {target}')
        # Parent links, external hosts and sibling municipalities never enter scope.
        if not target.startswith(url) or target == url:
            continue
        relative = target[len(url):]
        if '/' in relative.rstrip('/') or unquote(relative).startswith('.'):
            raise ValueError(f'Non-child register entry: {target}')
        name = a.get_text(' ', strip=True).rstrip('/')
        entries[target] = {'titulo': name, 'url': target, 'directory': parsed.path.endswith('/')}
    if not entries:
        raise ValueError(f'Empty register directory: {url}')
    return list(entries.values())


class TavernesBlanquesAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(url, timeout=(10, 45))
        response.raise_for_status()
        if response.url.lower() != url.lower():
            raise ValueError(f'Unexpected register redirect: {url} -> {response.url}')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            folder = Path(capture_dir)
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest() + '.html'
            (folder / name).write_bytes(response.content)
        return decode_html(response.content)

    def extract(self, fetch):
        """Walk the whole municipality subtree, grouping all files per instrument."""
        pending = [(SOURCE, None)]
        seen = set()
        rows = {}
        excluded = []
        while pending:
            url, owner = pending.pop(0)
            if url in seen:
                raise ValueError(f'Repeated directory/cycle: {url}')
            seen.add(url)
            for entry in parse_directory(fetch(url), url):
                target, title = entry['url'], entry['titulo']
                if entry['directory']:
                    if 'ANULAD' in title.upper() or 'SIN EFECTO' in title.upper():
                        excluded.append(target)
                        continue
                    match = re.match(r'^(46237-\d{4})\b', title)
                    child_owner = owner
                    if match:
                        if owner:
                            raise ValueError('Nested instrument requires grouping review')
                        child_owner = match.group(1)
                        if child_owner in rows:
                            raise ValueError(f'Duplicate register identity: {child_owner}')
                        rows[child_owner] = {
                            'id': 'tavernes-blanques-plan-' + child_owner,
                            'expediente': child_owner, 'titulo': title,
                            'municipio': 'Tavernes Blanques', 'codigo_ine': '46237',
                            'provincia': 'Valencia', 'tipo': 'planeamiento',
                            'url': target, 'inventory_url': SOURCE,
                            'source': 'registro_planeamiento_gva',
                            'organismo_fuente': 'Generalitat Valenciana',
                            'origen': 'inventario_documental_planeamiento',
                            'publication_ready': False, 'geometry_status': 'unavailable',
                            'documentos': [],
                        }
                    pending.append((target, child_owner))
                elif owner and re.search(r'\.(pdf|jpe?g|png|tiff?)$', target, re.I):
                    rows[owner]['documentos'].append({
                        'titulo': title, 'url': target, 'inventory_url': url,
                        'seccion': unquote(url[len(rows[owner]['url']):], encoding='latin-1').strip('/'),
                    })
        if not rows or any(not r['documentos'] for r in rows.values()):
            raise ValueError('Register has no instruments or an instrument lacks documents')
        for row in rows.values():
            row['documentos'].sort(key=lambda d: d['url'])
        return sorted(rows.values(), key=lambda r: r['id']), {
            'source_urls': sorted(seen), 'excluded_urls': excluded,
            'limitations': LIMITATIONS, 'coverage': 'regional_register_document_inventory',
        }

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-inventory/1.0'
            rows, report = self.extract(lambda url: self._fetch(session, url))
        self._write(out_jsonl, rows)
        return {**report, 'count': len(rows), 'written': len(rows),
                'documents': sum(len(r['documentos']) for r in rows)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full snapshot: removals and newly annulled instruments must be reflected.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
