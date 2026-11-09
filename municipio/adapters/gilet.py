"""Gilet planning inventory in the Generalitat's public document register."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote_to_bytes, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/'
          '4%20VALENCIA/46134%20GILET/')
LIMITATIONS = [
    'Partial municipal coverage: only the Generalitat public planning archive; '
    'not a licence register or a complete inventory of public works.',
    'Directory and document names are extracted; PDF contents, legal validity, '
    'approval and publication dates are not parsed or inferred from filenames.',
    'No verified coordinates or vector geometry; publication_ready is false.',
]


def decode_path(value: str) -> str:
    """The archive mixes UTF-8 and legacy percent-encoded Latin-1 names."""
    parts = []
    for part in value.split('/'):
        raw = unquote_to_bytes(part)
        try:
            parts.append(raw.decode('utf-8'))
        except UnicodeDecodeError:
            parts.append(raw.decode('latin-1'))
    return '/'.join(parts)


def parse_index(html: str, url: str) -> list[tuple[str, bool]]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1#indextitle')
    table = soup.select_one('table#indexlist')
    expected = 'Index of ' + decode_path(urlsplit(url).path).rstrip('/')
    if not heading or heading.get_text(' ', strip=True).rstrip('/') != expected or table is None:
        raise ValueError('Not the expected Gilet archive directory: ' + url)
    for a in soup.select('a[href]'):
        if ('next' in a.get('rel', []) or
                a.get_text(' ', strip=True).lower() in {'next', 'siguiente', 'següent'}):
            raise ValueError('Unexpected pagination; cannot claim a complete directory')
    links = {}
    for a in table.select('td.indexcolname a[href]'):
        href = a['href']
        if href in {'../', '..'}:
            continue
        target = urljoin(url, href)
        parsed = urlsplit(target)
        decoded = decode_path(parsed.path)
        if (not target.startswith(SOURCE) or parsed.query or parsed.fragment or
                any(p in {'.', '..'} for p in decoded.split('/'))):
            raise ValueError('Unexpected directory entry: ' + target)
        directory = parsed.path.endswith('/')
        if not directory and not parsed.path.lower().endswith('.pdf'):
            raise ValueError('Unsupported archive file; review before dropping it: ' + target)
        links[target] = directory
    return sorted(links.items())


class GiletAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.gilet.es')

    @staticmethod
    def collect(fetch):
        queue = [SOURCE]
        visited = set()
        groups = {}
        documents = set()
        while queue:
            url = queue.pop(0)
            if url in visited:
                continue
            if len(visited) >= 500:
                raise ValueError('Archive exceeds 500 directories; no partial output written')
            visited.add(url)
            relative = url[len(SOURCE):].strip('/').split('/')
            if len(relative) >= 2:
                name = decode_path(relative[1])
                match = re.fullmatch(r'(46134-\d{4}) (.+)', name)
                if not match:
                    raise ValueError('Unrecognized instrument directory: ' + url)
                key, title = match.groups()
                dossier = SOURCE + '/'.join(relative[:2]) + '/'
                if key in groups and groups[key]['url'] != dossier:
                    raise ValueError('Conflicting instrument identifier: ' + key)
                groups.setdefault(key, {
                    'id': 'gilet-proy-' + key, 'registro_id': key,
                    # Official archive grouping ID, not a municipal file number.
                    'expediente_grupo': key, 'referencia_tipo': 'identificador_registral',
                    'municipio': 'Gilet', 'codigo_ine': '46134', 'provincia': 'Valencia',
                    'titulo': title, 'tipo': 'planeamiento urbanístico',
                    'fase': None, 'fecha': None, 'fecha_publicacion': None,
                    'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': dossier, 'source': 'generalitat_valenciana',
                    'origen': 'registro_autonomico_planeamiento', 'source_inventory': SOURCE,
                    'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                    'publication_ready': False, 'limitaciones': LIMITATIONS,
                })
            for target, directory in parse_index(fetch(url), url):
                if directory:
                    queue.append(target)
                else:
                    if len(relative) < 2:
                        raise ValueError('Document outside an instrument: ' + target)
                    if target in documents:
                        continue
                    documents.add(target)
                    groups[key]['documentos'].append({
                        'titulo': decode_path(urlsplit(target).path.rsplit('/', 1)[-1]),
                        'url': target, 'url_indice': url,
                        'seccion': decode_path('/'.join(relative[2:])),
                    })
        if not groups or any(not row['documentos'] for row in groups.values()):
            raise ValueError('No instruments or an instrument lacks documents')
        rows = [groups[key] for key in sorted(groups)]
        for row in rows:
            row['documentos'].sort(key=lambda d: d['url'])
        return rows, sorted(visited)

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('evidence_dir')
        capture_dir = Path(captures) if captures else None
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-gilet/1.0 (public planning inventory)'

            def fetch(url):
                with session.get(url, timeout=30, stream=True) as response:
                    response.raise_for_status()
                    # requests uppercases percent escapes in its prepared URL.
                    if (response.history or
                            unquote_to_bytes(response.url) != unquote_to_bytes(url)):
                        raise ValueError('Unexpected archive redirect: ' + response.url)
                    content = bytearray()
                    for chunk in response.iter_content(65536):
                        content.extend(chunk)
                        if len(content) > 2_000_000:
                            raise ValueError('Directory response exceeds 2 MB')
                    if capture_dir:
                        import hashlib
                        name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
                        (capture_dir / name).write_bytes(content)
                    try:
                        return bytes(content).decode('utf-8')
                    except UnicodeDecodeError:
                        return bytes(content).decode('latin-1')

            rows, urls = self.collect(fetch)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temp = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': urls,
                'documents': sum(len(r['documentos']) for r in rows),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot of every descendant directory, with no date cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        Path(out_jsonl).parent.mkdir(parents=True, exist_ok=True)
        Path(out_jsonl).write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
