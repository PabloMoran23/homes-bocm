"""Municipal planning document inventory; dates and geometry are not inferred."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://www.markina-xemein.eus'
AREA = ROOT + '/es-ES/Servicios/Serviciosmunicipales/Urbanismo/'
SOURCE = AREA + 'Paginas/default.aspx'


def canonical(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, quote(unquote(p.path), safe='/'), p.query, ''))


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#main-content')
    if main is None:
        raise ValueError('Missing municipal content container')
    return main


def label(a):
    return a.get_text(' ', strip=True) or ' '.join(i.get('alt', '') for i in a.select('img'))


def parse_inventory(html):
    """Only named instrument bundles; forms, subsidies and catalogues excluded."""
    main = content(html)
    if main.select('.pagination, a[rel="next"]'):
        raise ValueError('Instrument landing inventory now paginated; review crawler')
    found = {}
    for a in main.select('a[href]'):
        title = label(a)
        if title.startswith('PGOU -'):
            kind = 'pgou'
        elif title.startswith('Modificación puntual del PGOU'):
            kind = 'modificacion'
        elif re.match(r'Área RX.*40 Arretxinaga', title):
            kind = 'arretxinaga'
        else:
            continue
        url = canonical(urljoin(SOURCE, a['href']))
        if not url.startswith(AREA + 'Paginas/'):
            raise ValueError('Instrument link left the municipal urbanism inventory')
        if kind in found and found[kind]['url'] != url:
            raise ValueError('Ambiguous instrument inventory')
        found[kind] = {'titulo': title, 'url': url}
    if not found:
        raise ValueError('No supported planning instruments in current inventory')
    return found


def parse_document_page(html, url):
    """Return PDFs, pager links and per-webpart advertised result counts."""
    main = content(html)
    docs = {}
    for a in main.select('a[href]'):
        target = canonical(urljoin(url, a['href']))
        if urlsplit(target).path.lower().endswith('.pdf'):
            if not target.startswith(AREA):
                raise ValueError('Unexpected document origin')
            docs[target] = {'titulo': label(a), 'url': target, 'source_page': url}
    pages = set()
    for a in main.select('.pagination a[href], a[rel="next"]'):
        target = canonical(urljoin(url, a['href']))
        if (urlsplit(target).path != urlsplit(url).path
                or urlsplit(target).netloc != urlsplit(url).netloc
                or not re.fullmatch(r'page=\d+', urlsplit(target).query)):
            raise ValueError('Unsupported pagination link')
        pages.add(target)
    counts = []
    for block in main.select('.ms-WPBody'):
        matches = set(re.findall(r'Resultados\s+(\d+)\s*-\s*(\d+)\s+de\s+(\d+)', block.get_text(' ', strip=True)))
        if len(matches) > 1:
            raise ValueError('Ambiguous pagination count')
        if matches:
            start, end, total = map(int, next(iter(matches)))
            urls = {canonical(urljoin(url, a['href'])) for a in block.select('a[href]')
                    if urlsplit(a['href']).path.lower().endswith('.pdf')}
            if not (1 <= start <= end <= total) or len(urls) != end - start + 1:
                raise ValueError('Pagination range does not match document links')
            # Separate webparts by their source document directory.
            directories = {u.rsplit('/', 1)[0] for u in urls}
            if len(directories) != 1:
                raise ValueError('Unsupported mixed-directory paginated webpart')
            counts.append((next(iter(directories)), start, end, total, urls))
    if 'Resultados' in main.get_text() and not counts:
        raise ValueError('Unrecognized result count markup')
    return list(docs.values()), sorted(pages), counts


def collect_documents(fetch, url):
    """Walk discovered pagers; verify all advertised documents and positions."""
    base = url.split('?')[0]
    queue, visited, docs, groups = [base], set(), {}, {}
    while queue:
        page = queue.pop(0)
        if parse_qs(urlsplit(page).query).get('page') == ['1']:
            page = base
        if page in visited:
            continue
        if len(visited) >= 100:
            raise ValueError('Pagination safety limit reached; no partial output written')
        visited.add(page)
        items, links, counts = parse_document_page(fetch(page), page)
        for item in items:
            docs.setdefault(item['url'], item)
        queue.extend(links)
        for directory, start, end, total, urls in counts:
            group = groups.setdefault(directory, {'total': total, 'positions': set(), 'urls': set()})
            if group['total'] != total:
                raise ValueError('Inventory changed during pagination')
            group['positions'].update(range(start, end + 1))
            group['urls'].update(urls)
    for group in groups.values():
        if len(group['positions']) != group['total'] or len(group['urls']) != group['total']:
            raise ValueError('Incomplete paginated document inventory')
    return list(docs.values())


def record(key, title, url, docs, **extra):
    if not docs:
        raise ValueError('Instrument has no source documents')
    return {
        'id': 'markina-xemein-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
        'municipio': 'Markina-Xemein', 'codigo_ine': '48060', 'provincia': 'Bizkaia',
        'titulo': title, 'tipo': 'instrumento_urbanistico', 'url': url,
        'inventory_url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_urbanismo',
        'documentos': docs, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'fase': None, 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False, **extra,
    }


def extract_projects(fetch):
    rows = []
    for kind, entry in parse_inventory(fetch(SOURCE)).items():
        url, title = entry['url'], entry['titulo']
        if kind == 'modificacion':
            main = content(fetch(url))
            if main.select('.pagination, a[rel="next"]'):
                raise ValueError('Approval section inventory now paginated; review crawler')
            docs, stages = {}, []
            for a in main.select('a[href]'):
                if not label(a).lower().startswith('aprobación '):
                    continue
                stage_url = canonical(urljoin(url, a['href']))
                if not stage_url.startswith(AREA + 'Paginas/'):
                    raise ValueError('Unexpected approval section origin')
                items = collect_documents(fetch, stage_url)
                stages.append({'titulo': label(a), 'url': stage_url, 'documentos': len(items)})
                for item in items:
                    item['seccion_documental'] = label(a)
                    docs.setdefault(item['url'], item)
            rows.append(record(url, title, url, list(docs.values()), secciones_documentales=stages))
        elif kind == 'arretxinaga':
            docs = collect_documents(fetch, url)
            # This area contains four different instruments, not seven projects.
            rules = [
                ('estudio-detalle', 'Estudio de detalle — Arretxinaga RX–V-a.40',
                 lambda t: t.startswith(('estudio detalle', 'planos'))),
                ('pau', 'Programa de Actuación Urbanizadora — Arretxinaga RX–V-a.40',
                 lambda t: t.startswith('programa de actuación')),
                ('reparcelacion', 'Proyecto de reparcelación — Arretxinaga RX–V-a.40',
                 lambda t: t.startswith('proyecto de reparcelación')),
                ('urbanizacion', 'Proyecto de Urbanización — Arretxinaga RX–V-a.40',
                 lambda t: t.startswith('proyecto de urbanización')),
            ]
            related = [d for d in docs if d['titulo'].lower().startswith('convenio de concertación')]
            assigned = {d['url'] for d in related}
            for key, instrument, matches in rules:
                bundle = [d for d in docs if matches(d['titulo'].lower())]
                assigned.update(d['url'] for d in bundle)
                rows.append(record(url + '#' + key, instrument, url, bundle,
                                   documentos_contexto=related, ambito=title))
            if assigned != {d['url'] for d in docs}:
                raise ValueError('Unclassified Arretxinaga documents require review')
        else:
            rows.append(record(url, title, url, collect_documents(fetch, url)))
    return rows


class MarkinaXemeinAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-markina-xemein/1.0'}, stream=True)
        with response:
            response.raise_for_status()
            if not canonical(response.url).startswith(AREA):
                raise ValueError('Unexpected municipal source redirect')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 4_000_000:
                    raise ValueError('Source response too large')
            html = body.decode('utf-8-sig')
        self.source_urls.append(url)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (directory / name).write_bytes(body)
            self.captures[url] = name
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls, self.captures = [], {}
        # Cache only within this snapshot, never reuse stale content on updates.
        cache = {}
        def fetch(url):
            if url not in cache:
                cache[url] = self._fetch(url)
            return cache[url]
        rows = extract_projects(fetch)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'captures': self.captures, 'coverage': 'municipal_planning_document_inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
