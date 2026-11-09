"""Snapshot of Porreres' official Expedients tree, grouped by planning instrument."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, parse_qs

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://porreres.cat'
SOURCE = BASE + '/ca/arxius-i-documents/expedients'
PREFIX = '/ca/arxius-i-documents/'
LIMITATIONS = [
    'Partial coverage: municipal Expedients document tree only; no comprehensive works or licence register.',
    'Road catalogue excluded; forms, procurement and news are outside this inventory.',
    'Documents and historical versions grouped by instrument, not separate projects.',
    'Document display dates are file dates, not verified publication or agreement dates.',
    'Approval status, agreement dates and legal currency are not inferred from document titles.',
    'Attachments retained as links; PDF/ZIP contents and geometries are not parsed.',
    'No verified coordinates; publication_ready is false.',
]


def _official(url: str, prefix: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'porreres.cat' or not parts.path.startswith(prefix):
        raise ValueError(f'Unexpected inventory URL: {url}')
    return url.split('#')[0]


def parse_page(html: str, url: str) -> dict:
    """Extract scoped folder links, pagination and attachment metadata, never navigation."""
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main .layout-content')
    if main is None or main.select_one('h1') is None:
        raise ValueError(f'Missing municipal content: {url}')
    folder = main.select_one('.taxonomy-term-files')
    article = main.select_one('article.node-file-or-document')
    if folder is None and article is None:
        raise ValueError(f'Unknown document layout: {url}')
    children = []
    if folder:
        for a in folder.select('a[href]'):
            h = a.select_one('h3')
            if h:
                children.append((_official(urljoin(url, a['href']), PREFIX), h.get_text(' ', strip=True)))
    pages = []
    for a in main.select('nav.pager a[href], nav[aria-label="Paginació"] a[href], a[rel~="next"]'):
        target = _official(urljoin(url, a['href']), PREFIX)
        if urlsplit(target).path != urlsplit(url).path or set(parse_qs(urlsplit(target).query)) - {'page'}:
            raise ValueError('Unexpected pagination URL')
        pages.append(target)
    # A pager with changed markup must fail instead of silently stopping at page one.
    for nav in main.select('nav'):
        if ('pager' in ' '.join(nav.get('class', [])) or 'pagin' in nav.get('aria-label', '').lower()) and nav.select('a[href]'):
            if not pages:
                raise ValueError('Unrecognised pagination')
    documents = []
    if article:
        for a in article.select('.multimedia--documents a[href]'):
            block = a.parent
            h = block.select_one('h3')
            if h is None:
                raise ValueError('Attachment missing title')
            text = block.get_text(' ', strip=True)
            match = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', text)
            documents.append({
                'titulo': h.get_text(' ', strip=True),
                'url': _official(urljoin(url, a['href']), '/sites/cilma_porreres/files/'),
                'fecha_archivo': datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None,
                'metadata_original': text, 'pagina_origen': url,
            })
        if not documents:
            raise ValueError(f'Document page has no attachments: {url}')
    description = article.select_one('.prose') if article else None
    return {'titulo': main.select_one('h1').get_text(' ', strip=True),
            'descripcion': description.get_text(' ', strip=True) if description else None,
            'children': children, 'pages': pages, 'documentos': documents}


def instrument_key(url: str) -> str | None:
    """Reviewed top-level identities; newly added branches require a scope review."""
    name = urlsplit(url).path.removeprefix(PREFIX).removeprefix('expedients/')
    if name == 'cataleg-de-camins':
        return None
    if name in {'adaptacio-nnss-al-ptm',
                'annex-laprovacio-amb-exposicio-publica-de-lesmena-de-deficiencies-18122017',
                'annex-laprovacio-amb-exposicio-publica-de-lesmena-de-deficiencies',
                'text-refos-modificacio-nnss-i-adaptacio-al-ptm-2021'}:
        return 'adaptacio-nnss-ptm'
    if name == 'cataleg-delements-i-espais-protegits':
        return 'cataleg-elements-espais-protegits'
    if name == 'modificacio-de-les-nnss-la-redelimitacio-de-la-unitat-dactuacio-4':
        return 'nnss-redelimitacio-ua4'
    if name == 'supressio-de-les-ua1-ua2-i-ua3-nnss':
        return 'nnss-supressio-ua1-ua2-ua3'
    match = re.match(r'modificacio-puntual-num-([4-7])(?:-de-les)?-nnss(?:-|$)', name)
    if match:
        return 'nnss-mp-' + match[1]
    raise ValueError(f'Unreviewed top-level instrument: {url}')


class PorreresAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, session, url):
        _official(url, PREFIX)
        response = session.get(url, timeout=40)
        response.raise_for_status()
        _official(response.url, PREFIX)
        if urlsplit(response.url).path != urlsplit(url).path or urlsplit(response.url).query != urlsplit(url).query:
            raise ValueError('Inventory redirected; review source before extraction')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected HTML inventory')
        if self.config.get('evidence_dir'):
            target = Path(self.config['evidence_dir'])
            target.mkdir(parents=True, exist_ok=True)
            (target / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
        return parse_page(response.text, url)

    def collect(self, fetch):
        queue = [(SOURCE, None)]
        visited, groups, owners = set(), {}, {}
        while queue:
            url, key = queue.pop(0)
            if url in owners and owners[url] != key:
                raise ValueError('Page assigned to conflicting instruments')
            owners[url] = key
            if url in visited:
                continue
            if len(visited) >= 200:
                raise ValueError('Inventory safety limit exceeded; no partial output written')
            page = fetch(url)
            visited.add(url)
            queue.extend((p, key) for p in page['pages'])
            for child, title in page['children']:
                child_key = instrument_key(child) if key is None else key
                if child_key is None:
                    continue
                if child_key not in groups:
                    groups[child_key] = {
                        'titulo': 'Adaptació de les NNSS al PTM (versions i annexos)' if child_key == 'adaptacio-nnss-ptm' else title,
                        'url': child, 'paginas_fuente': [], 'documentos': {}, 'descripciones_fuente': [],
                    }
                queue.append((child, child_key))
            if key is not None:
                group = groups[key]
                group['paginas_fuente'].append(url)
                if page['descripcion']:
                    group['descripciones_fuente'].append({'url': url, 'descripcion': page['descripcion']})
                for doc in page['documentos']:
                    entry = group['documentos'].setdefault(doc['url'], {
                        'titulo': doc['titulo'], 'url': doc['url'], 'apariciones': [],
                    })
                    entry['apariciones'].append({k: v for k, v in doc.items() if k != 'url'})
        if not groups:
            raise ValueError('No planning instruments found')
        rows = []
        for key, group in sorted(groups.items()):
            if not group['documentos']:
                raise ValueError(f'Instrument without documents: {key}')
            group['documentos'] = list(group['documentos'].values())
            descriptions = group['descripciones_fuente']
            references = set()
            for entry in descriptions:
                references.update(re.findall(r'\bExpedient\s+(\d+/\d{4})\b', entry['descripcion']))
            rows.append({
                'id': 'porreres-proy-' + key, 'municipio': 'Porreres', 'codigo_ine': '07043',
                'provincia': 'Illes Balears', 'tipo': 'planeamiento_urbanistico',
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_expedients',
                'url_inventario': SOURCE, 'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': None, 'fecha_aprob': None, 'fase': None,
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'limitaciones': LIMITATIONS, **group,
                'descripcion': '\n'.join(entry['descripcion'] for entry in descriptions) or None,
                'numero_expediente': next(iter(references)) if len(references) == 1 else None,
            })
        return rows, sorted(visited)

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-porreres/1.0'
            rows, sources = self.collect(lambda url: self._fetch(session, url))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
