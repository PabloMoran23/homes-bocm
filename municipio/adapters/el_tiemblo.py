"""El Tiemblo: municipal-linked JCyL PLAU urban planning inventory (PU only)."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL = 'https://www.eltiemblo.es/urbanismo'
ROOT = 'https://servicios.jcyl.es/PlanPublica/'
SOURCE = ROOT + ('searchVPubDocMuniPlau.do?bInfoPublica=N&pager.sortname=fPublicacion'
                 '&pager.sortindex=-3&provincia=05&municipio=241')
LIMITATIONS = [
    'Only libro PU (urban planning); GU management projects and OT territorial planning excluded.',
    'Historical entries are not requested; this is not a full municipal works or licence register.',
    'Dates are archive publication/agreement fields, not independently verified approval dates.',
    'Some archive entries have no attached files or publication date; absent values remain null.',
    'Files are grouped under each archive instrument; amendments remain distinct instruments.',
    'No verified instrument geometry or coordinates; publication_ready=false.',
]


def canonical(url):
    parts = urlsplit(urljoin(ROOT, url))
    if parts.scheme != 'https' or parts.netloc != 'servicios.jcyl.es':
        raise ValueError('Unexpected archive source host')
    return urlunsplit((parts.scheme, parts.netloc,
                      re.sub(r';jsessionid=[^/?;]+', '', parts.path), parts.query, ''))


def archive_link(endpoint, key, value):
    return ROOT + endpoint + '?' + key + '=' + value


def date_value(text):
    return datetime.strptime(text, '%d/%m/%Y').date().isoformat() if text else None


def page_range(soup):
    match = re.search(r'Mostrando resultados\s+(\d+)-(\d+)\s+de\s+(\d+)',
                      soup.get_text(' ', strip=True))
    if not match:
        raise ValueError('Missing inventory pagination totals')
    return tuple(map(int, match.groups()))


def next_page(soup):
    links = [a for a in soup.select('a') if 'Siguiente' in a.get_text(' ', strip=True)]
    if not links:
        return None
    if len(links) != 1:
        raise ValueError('Ambiguous next page')
    match = re.search(r"unescape\('([^']+)'\)", links[0].get('onclick', ''))
    if not match:
        raise ValueError('Unrecognized next-page control')
    url = canonical(unquote(match[1]))
    query = parse_qs(urlsplit(url).query)
    if (urlsplit(url).path != '/PlanPublica/searchVPubDocMuniPlau.do'
            or query.get('municipio') != ['241'] or query.get('provincia') != ['05']
            or query.get('bInfoPublica') != ['N'] or query.get('bIncluirHist')):
        raise ValueError('Pagination escaped municipality or inventory scope')
    return url


class ElTiembloAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.eltiemblo.es')

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.select_one('table.cuadroAplicacion')
        if not table or [th.get_text(' ', strip=True) for th in table.select('th')][:5] != [
                'Libro', 'Instrumento', 'Fecha de publicación', 'Fecha de acuerdo', 'Título']:
            raise ValueError('Changed archive inventory table')
        rows = []
        for tr in table.select('tr'):
            cells = tr.find_all('td', recursive=False)
            if not cells:
                continue
            if len(cells) != 6:
                raise ValueError('Changed inventory row')
            values = [c.get_text(' ', strip=True) for c in cells]
            book, figure, publication, agreement, title, _ = values
            if not book or not figure or not title:
                raise ValueError('Incomplete instrument identity')
            # Count every inventory row before limiting extraction to urban planning.
            row = {'libro': book, 'tipo': figure, 'titulo': title,
                   'fecha_publicacion': date_value(publication),
                   'fecha_acuerdo': date_value(agreement)}
            ids = set(re.findall(r"(?:cDocId=|doGoBoletin\(')(\d+)", str(tr)))
            if len(ids) > 1:
                raise ValueError('Conflicting instrument identifiers')
            row['archivo_id'] = next(iter(ids), None)
            listing = cells[-1].select_one('a[href*="ldoc_files.do"]')
            row['url_ficheros'] = canonical(listing['href']) if listing else None
            rows.append(row)
        start, end, total = page_range(soup)
        if not 1 <= start <= end <= total or len(rows) != end - start + 1:
            raise ValueError('Inventory row count disagrees with pagination')
        following = next_page(soup)
        if (end < total) != bool(following):
            raise ValueError('Missing or spurious next page; refusing truncated inventory')
        return rows, (start, end, total), following

    @staticmethod
    def parse_files(html):
        soup = BeautifulSoup(html, 'html.parser')
        if 'Listado de ficheros' not in soup.get_text(' ', strip=True):
            raise ValueError('Missing official file list')
        # The reviewed file lists are unpaginated. Fail if that changes.
        if any('pager.offset' in a.get('onclick', '') or
               re.search(r'siguiente|next', a.get_text(' ', strip=True), re.I)
               for a in soup.select('a')):
            raise ValueError('File list became paginated; review required')
        docs = {}
        for tr in soup.select('table.cuadroAplicacion tr'):
            link = tr.select_one('a[href*="openFichero.do"]')
            if not link:
                continue
            url = canonical(link['href'])
            name = tr.find('td').get_text(' ', strip=True)
            if not name or not parse_qs(urlsplit(url).query).get('cFicheroId'):
                raise ValueError('Missing file identity')
            docs[url] = {'titulo': name, 'url': url, 'procedencia': 'JCyL PLAU'}
        if not docs:
            raise ValueError('Linked file list has no documents')
        return list(docs.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        source_urls = []
        capture = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-el-tiemblo/1.0 (public planning inventory)'

            def fetch(url):
                if source_urls:
                    time.sleep(.2)
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if len(response.content) > 8_000_000:
                    raise ValueError('Unexpectedly large archive response')
                # JCyL explicitly declares its legacy encoding in the response.
                html = response.text
                source_urls.append(url)
                if capture:
                    folder = Path(capture)
                    folder.mkdir(parents=True, exist_ok=True)
                    name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
                    (folder / name).write_text(html, encoding='utf-8')
                return html

            municipal = BeautifulSoup(fetch(MUNICIPAL), 'html.parser')
            if not any(a.get('href', '').startswith(ROOT + 'searchVPubDocMuniPlau.do')
                       and parse_qs(urlsplit(a['href']).query).get('municipio') == ['241']
                       and parse_qs(urlsplit(a['href']).query).get('provincia') == ['05']
                       for a in municipal.select('a[href]')):
                raise ValueError('Municipal planning archive link no longer verified')
            url, expected_start, total = SOURCE, 1, None
            entries, visited = [], set()
            while url:
                if url in visited:
                    raise ValueError('Pagination cycle')
                visited.add(url)
                html = fetch(url)
                if expected_start == 1 and not re.search(r'Código INE:\s*05241',
                        BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)):
                    raise ValueError('Wrong municipality in archive')
                rows, (start, end, observed_total), following = self.parse_inventory(html)
                if start != expected_start or (total is not None and total != observed_total):
                    raise ValueError('Noncontiguous or changing inventory pagination')
                total = observed_total
                entries.extend(rows)
                expected_start, url = end + 1, following
            if len(entries) != total:
                raise ValueError('Incomplete inventory')
            projects, identities = [], set()
            for entry in entries:
                if entry['libro'] != 'PU':
                    continue
                doc_id = entry['archivo_id']
                key = doc_id or hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()[:20]
                if key in identities:
                    raise ValueError('Duplicate instrument across inventory pages')
                identities.add(key)
                docs = self.parse_files(fetch(entry['url_ficheros'])) if entry['url_ficheros'] else []
                row = {**entry, 'id': 'el-tiemblo-plau-' + key,
                       'municipio': 'El Tiemblo', 'codigo_ine': '05241', 'provincia': 'Ávila',
                       'source': 'ayuntamiento', 'organismo_fuente': 'Junta de Castilla y León',
                       'origen': 'archivo_planeamiento_plau', 'url_inventario': SOURCE,
                       'url': entry['url_ficheros'] or SOURCE, 'fecha': None,
                       'documentos': docs, 'documentacion_disponible': bool(docs),
                       'geometry': None, 'lat': None, 'lon': None,
                       'geometry_status': 'unavailable', 'publication_ready': False}
                if doc_id and entry['fecha_publicacion']:
                    row['url_boletin'] = archive_link('openBoletinDoc.do', 'cDocId', doc_id)
                projects.append(row)
            if not projects:
                raise ValueError('No usable urban planning instruments')
        self._write(out_jsonl, projects)
        return {'status': 'ok', 'rows': len(projects), 'inventory_rows': total,
                'inventory_pages': len(visited), 'source_urls': source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        """Refresh the entire current inventory; no date cutoff or append duplicates."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
