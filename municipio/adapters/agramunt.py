"""Agramunt's public planning inventory, one record per instrument, not per PDF."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.agramunt.cat/ajuntament/reglaments-i-normatives/urbanisme'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
DATE = r"(\d{1,2})\s+d[e’']\s*(\w+)\s+de\s+(\d{4})"


def text(node):
    return node.get_text(' ', strip=True) if node else ''


def official_url(href, base):
    url = urldefrag(urljoin(base, href))[0]
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'www.agramunt.cat' or not (parsed.path == urlparse(SOURCE).path or parsed.path.startswith(urlparse(SOURCE).path + '/')):
        raise ValueError(f'Unexpected inventory URL: {url}')
    return url


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.select_one('article#content')
    if root is None or root.select_one('#content-core') is None or root.select_one('h1') is None:
        raise ValueError('Missing public planning content; possible error/login page')
    return root


def next_page(root, base):
    links = set()
    for a in root.select('a[href]'):
        rel = a.get('rel', [])
        if ('next' in rel or a.find_parent(class_='next') or
                text(a).lower() in {'següent', 'següents', 'siguiente', 'next', '»', '›'}):
            links.add(official_url(a['href'], base))
    if len(links) > 1:
        raise ValueError('Conflicting pagination links')
    # Never accept an unrecognised pager as an unpaginated complete snapshot.
    if root.select_one('.listingBar, .pagination') and not links:
        pager = root.select_one('.listingBar, .pagination')
        for a in pager.select('a[href]'):
            if a.find_parent(class_='previous'):
                continue
            target = urlparse(urljoin(base, a['href']))
            offset = parse_qs(target.query).get('b_start:int', parse_qs(target.query).get('b_start'))
            current = parse_qs(urlparse(base).query)
            current_offset = int(current.get('b_start:int', current.get('b_start', ['0']))[0])
            if not offset or int(offset[0]) > current_offset:
                raise ValueError('Pagination present without recognised next link')
    return next(iter(links), None)


def parse_inventory(html, url=SOURCE):
    root = content(html)
    if text(root.select_one('h1')) != 'Informació Urbanística':
        raise ValueError('Unexpected municipal inventory heading')
    rows = []
    for tile in root.select('#content-core article.tileItem'):
        a = tile.select_one('.tileHeadline a[href]')
        description = text(tile.select_one('.description'))
        if not a:
            raise ValueError('Inventory item lacks detail link')
        title = text(a)
        if not re.match(r'^(POUM|Modificació|TUC|Pla Especial|PLA\s+DE MILLORA|MODIFICACIÓ)', title):
            raise ValueError(f'Unreviewed inventory entry: {title}')
        if not description:
            raise ValueError('Planning entry lacks substantive description')
        rows.append({'titulo': title, 'descripcion': description,
                     'url': official_url(a['href'], url)})
    if not rows:
        raise ValueError('Empty planning inventory')
    return rows, next_page(root, url)


def parse_documents(html, url):
    root = content(html)
    core = root.select_one('#content-core')
    docs = {}
    for a in core.select('a[href]'):
        href = a['href']
        if href.startswith('#'):
            continue
        if re.search(r'\.pdf(?:/|$)', href, re.I):
            link = official_url(href, url)
            docs.setdefault(link, {'titulo': text(a), 'url': link, 'source_url': url})
        elif 'contenttype-folder' in a.get('class', []) or a.find_parent(title='Folder'):
            raise ValueError('New nested document folder needs crawler review')
    return list(docs.values()), next_page(root, url)


def semantics(description):
    """Read dated agreement clauses only, never dates of cited legislation."""
    events = []
    patterns = [
        ('aprobación definitiva', r'Aprovació definitiva[^.]*?en data\s+'),
        ('acuerdo de publicación a efectos de ejecutividad', r'acordada la seva publicació[^.]*?data\s+'),
        ('aprobación inicial', r'(?=[^.]*aprovació inicial)Acord de l’Ajuntament Ple, de data\s+'),
        ('aprobación provisional', r"Acord d'aprovació provisional[^.]*?data\s+"),
        ('aprobación definitiva', r'Aprovada definitivament[^.]*?data\s+'),
        ('aprobación del texto refundido', r"Acord d'aprovació del Text refós[^.]*?data\s+"),
        ('aprobación CTU', r'Aprovat per la Comissió Territorial[^.]*?data\s+'),
        ('aprobación provisional', r'Aprovat provisionalment[^.]*?data\s+'),
    ]
    for phase, prefix in patterns:
        for match in re.finditer(prefix + DATE, description, re.I):
            day, month, year = match.groups()
            if month.lower() not in MONTHS:
                raise ValueError('Unknown Catalan agreement month')
            events.append({'fase': phase, 'fecha_acuerdo': date(int(year), MONTHS[month.lower()], int(day)).isoformat(),
                           'texto_fuente': match[0]})
    publication = re.search(r'Publicat al DOGC[^.]*?data\s+' + DATE, description, re.I)
    publication_date = None
    if publication:
        d, m, y = publication.groups()
        publication_date = date(int(y), MONTHS[m.lower()], int(d)).isoformat()
    events.sort(key=lambda e: e['fecha_acuerdo'])
    # The POUM executive-publication agreement is not a new approval date.
    approvals = [e for e in events if not e['fase'].startswith('acuerdo de publicación')]
    latest = approvals[-1] if approvals else {}
    return {'fase': latest.get('fase'), 'fecha_acuerdo': latest.get('fecha_acuerdo'),
            'fecha_aprob': latest.get('fecha_acuerdo'), 'fecha_publicacion': publication_date,
            'acuerdos': events}


class AgramuntAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='agramunt', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.agramunt.cat')

    def _fetch(self, url):
        response = requests.get(url, timeout=35, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-agramunt/1.0')})
        with response:
            response.raise_for_status()
            if urldefrag(response.url)[0] != url:
                raise ValueError('Unexpected source redirect')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected municipal HTML inventory')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Municipal page exceeds reviewed size limit')
            html = bytes(data).decode('utf-8')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            target = Path(capture_dir)
            target.mkdir(parents=True, exist_ok=True)
            (target / (hashlib.sha256(url.encode()).hexdigest() + '.html')).write_text(html, encoding='utf-8')
        return html

    def _pages(self, first, parser):
        seen = set()
        url = first
        while url:
            if url in seen or len(seen) >= 100:
                raise ValueError('Pagination loop or limit reached; no partial output written')
            seen.add(url)
            items, following = parser(self._fetch(url), url)
            yield url, items
            url = following

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        instruments = {}
        sources = []
        for url, rows in self._pages(SOURCE, parse_inventory):
            sources.append(url)
            for row in rows:
                previous = instruments.setdefault(row['url'], row)
                if previous != row:
                    raise ValueError('Conflicting duplicate instrument')
        output = []
        for url, row in instruments.items():
            documents = {}
            for page, docs in self._pages(url, parse_documents):
                sources.append(page)
                for doc in docs:
                    documents.setdefault(doc['url'], doc)
            if not documents:
                raise ValueError(f'Instrument lacks source documents: {url}')
            # Only the human-readable certificate label supplies this event;
            # document filenames and page-modification dates are not agreement dates.
            dates = semantics(row['descripcion'])
            if not dates['acuerdos']:
                for doc in documents.values():
                    match = re.fullmatch(r'Aprovació inicial Ajuntament Ple (\d{2})\.(\d{2})\.(\d{4})', doc['titulo'])
                    if match:
                        d, m, y = map(int, match.groups())
                        value = date(y, m, d).isoformat()
                        dates.update(fase='aprobación inicial', fecha_acuerdo=value, fecha_aprob=value)
                        dates['acuerdos'].append({'fase': 'aprobación inicial', 'fecha_acuerdo': value,
                                                  'texto_fuente': doc['titulo'], 'source_url': doc['source_url']})
            expediente = re.search(r'(?:Expedient|Exp\.|EXP\.)\s*(?:núm\.?\s*)?(\d+/\d{4})', row['titulo'] + ' ' + row['descripcion'], re.I)
            row.update(dates)
            row.update(id='agramunt-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                       municipio='Agramunt', provincia='Lleida', codigo_ine='25003',
                       tipo='planeamiento_urbanistico', expediente=expediente[1] if expediente else None,
                       fecha=None, source='ayuntamiento', origen='inventario_municipal_urbanismo',
                       source_url=SOURCE, documentos=list(documents.values()),
                       url_documento=next(iter(documents)), lat=None, lon=None, geometry=None,
                       publication_ready=False, coverage='Inventario municipal de urbanismo; cobertura histórica parcial')
            output.append(row)
        self._write(out_jsonl, output)
        return {'status': 'ok', 'rows': len(output), 'source_urls': sources, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full current inventory snapshot; never skip records by a crawl timestamp.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
