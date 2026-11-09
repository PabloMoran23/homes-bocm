"""Municipal planning inventory from the official JCyL archive linked by the town."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://servicios.jcyl.es/PlanPublica/'
SOURCE = ROOT + 'searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=168'
LIMITATIONS = [
    'Partial municipal coverage: current JCyL planning archive (historical toggle off), not all public works.',
    'Municipal website returned HTTP 403 to direct requests; its Normativa Urbanística page links this archive.',
    'No granted licence register extracted; forms, conventions and court judgments excluded.',
    'Agreement and publication dates are archive metadata; no approval phase inferred.',
    'Files are grouped under their archive instrument ID; PDF contents and legal validity are not independently interpreted.',
    'No verified geometry or coordinates; publication_ready=false.',
]


def clean_url(value, base=ROOT):
    url = urljoin(base, re.sub(r';jsessionid=[^?/#]+', '', value))
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'servicios.jcyl.es' or not parsed.path.startswith('/PlanPublica/'):
        raise ValueError('Unexpected archive URL')
    return url


def _date(value):
    value = value.strip()
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat() if value else None


def _pager(soup):
    """Read actual JavaScript pagination targets, rather than guessing page limits."""
    urls = set()
    for a in soup.select('a[onclick]'):
        if a.find_parent('th') is not None:
            continue  # Column sorting targets are not pagination.
        match = re.search(r"unescape\('([^']+)'\)", a['onclick'])
        if match:
            target = unquote(match[1])
            if 'pager.offset=' in target:
                urls.add(clean_url(target))
    return sorted(urls)


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    summary = re.search(r'Mostrando resultados\s+(\d+)-(\d+)\s+de\s+(\d+)', text)
    if not summary:
        raise ValueError('Missing archive pagination count')
    start, end, total = map(int, summary.groups())
    tables = [t for t in soup.select('table') if [h.get_text(' ', strip=True) for h in t.select('th')][:5]
              == ['Libro', 'Instrumento', 'Fecha de publicación', 'Fecha de acuerdo', 'Título']]
    if len(tables) != 1:
        raise ValueError('Unexpected planning table')
    rows = []
    for tr in tables[0].select('tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells:
            continue
        if len(cells) != 6:
            raise ValueError('Unexpected planning row')
        values = [c.get_text(' ', strip=True) for c in cells]
        ids = set(re.findall(r'cDocId=(\d+)', str(cells[5])))
        ids.update(re.findall(r"doGoBoletin\('(\d+)'", str(cells[2])))
        if len(ids) != 1 or not values[4]:
            raise ValueError('Missing or ambiguous instrument ID')
        doc_id = next(iter(ids))
        rows.append({'archive_id': doc_id, 'libro': values[0], 'instrumento': values[1],
                     'titulo': values[4], 'fecha_publicacion': _date(values[2]),
                     'fecha_acuerdo': _date(values[3]),
                     'url_boletin': ROOT + 'openBoletinDoc.do?cDocId=' + doc_id if 'doGoBoletin' in str(cells[2]) else None,
                     'has_files': 'ldoc_files.do' in str(cells[5])})
    if len(rows) != end - start + 1 or not (1 <= start <= end <= total):
        raise ValueError('Incomplete archive page')
    return rows, (start, end, total), _pager(soup)


def parse_files(html):
    soup = BeautifulSoup(html, 'html.parser')
    if 'Listado de ficheros' not in soup.get_text(' ', strip=True):
        raise ValueError('Unexpected file inventory')
    files = {}
    for a in soup.select('a[href]'):
        if 'openFichero.do?' not in a['href']:
            continue
        url = clean_url(a['href'])
        cells = a.find_parent('tr').find_all('td', recursive=False)
        files[url] = {'nombre': cells[0].get_text(' ', strip=True), 'url': url}
    if not files:
        raise ValueError('Expected archive attachments missing')
    # Fail closed if this endpoint introduces pagination rather than dropping files.
    if _pager(soup) or re.search(r'Mostrando resultados', soup.get_text(' ', strip=True)):
        raise ValueError('File inventory pagination requires review')
    return list(files.values())


class LasNavasDelMarquesAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        url = clean_url(url)
        response = session.get(url, timeout=45)
        response.raise_for_status()
        clean_url(response.url)
        # Keep captures optional and local; never depend on them for extraction.
        self.source_urls.append(url)
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f'source-{len(self.source_urls):03d}.html').write_bytes(response.content)
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = []
        session = requests.Session()
        session.headers['User-Agent'] = 'municipio-las-navas-del-marques/1.0'
        try:
            html = self._fetch(session, SOURCE)
            soup = BeautifulSoup(html, 'html.parser')
            if 'Código INE: 05168' not in soup.get_text(' ', strip=True) or 'NAVAS DEL MARQUÉS (LAS)' not in soup.get_text(' ', strip=True):
                raise ValueError('Wrong archive municipality')
            pending, visited, inventory, positions = [SOURCE], set(), {}, set()
            total_expected = None
            while pending:
                url = pending.pop(0)
                offset = int(parse_qs(urlparse(url).query).get('pager.offset', ['0'])[0])
                if offset in visited:
                    continue
                visited.add(offset)
                page = html if url == SOURCE else self._fetch(session, url)
                rows, (start, end, total), links = parse_inventory(page)
                if total_expected is not None and total != total_expected:
                    raise ValueError('Archive changed during pagination')
                total_expected = total
                for position, row in enumerate(rows, start):
                    doc_id = row['archive_id']
                    if doc_id in inventory and inventory[doc_id] != row:
                        raise ValueError('Conflicting archive instrument')
                    inventory[doc_id] = row
                    positions.add(position)
                for link in links:
                    query = parse_qs(urlparse(link).query)
                    if query.get('municipio') != ['168'] or query.get('provincia') != ['05'] or query.get('bInfoPublica') != ['N']:
                        raise ValueError('Wrong pagination scope')
                    next_offset = int(query['pager.offset'][0])
                    if next_offset not in visited and link not in pending:
                        pending.append(link)
                if len(visited) > 100:
                    raise ValueError('Unexpected archive pagination loop')
            if positions != set(range(1, total_expected + 1)) or len(inventory) != total_expected:
                raise ValueError('Incomplete archive inventory')
            records = []
            for row in inventory.values():
                if row['libro'] not in {'PU', 'GU'} or row['titulo'].startswith('SENTENCIA'):
                    continue
                doc_id = row['archive_id']
                files_url = ROOT + 'ldoc_files.do?cDocId=' + doc_id
                files = parse_files(self._fetch(session, files_url)) if row['has_files'] else []
                records.append({
                    'id': 'las-navas-del-marques-plan-' + doc_id,
                    'municipio': 'Las Navas del Marqués', 'codigo_ine': '05168', 'provincia': 'Ávila',
                    'titulo': row['titulo'], 'tipo': row['instrumento'], 'libro': row['libro'],
                    'archive_id': doc_id, 'fecha_publicacion': row['fecha_publicacion'],
                    'fecha_acuerdo': row['fecha_acuerdo'],
                    'url': files_url if row['has_files'] else (row['url_boletin'] or SOURCE),
                    'url_boletin': row['url_boletin'],
                    'inventory_url': SOURCE, 'documentos': files,
                    'source': 'jcyl', 'origen': 'archivo_planeamiento_municipal',
                    'lat': None, 'lon': None, 'geometry': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                })
            if not records:
                raise ValueError('No usable planning instruments')
            output = Path(out_jsonl)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
            return {'count': len(records), 'live_records': len(records), 'inventory_rows': total_expected,
                    'excluded_rows': total_expected - len(records), 'source_urls': self.source_urls,
                    'limitations': LIMITATIONS, 'publication_ready': False}
        finally:
            session.close()

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
