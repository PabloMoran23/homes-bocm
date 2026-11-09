"""Public municipal PGM document tree; one instrument, many source documents."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://olivafrontera.com/plan-general-municipal/'
LIMITATIONS = [
    'Only the public municipal PGM document tree; not a complete planning or works register.',
    'The source labels this version initially approved; no claim of current legal validity or final approval.',
    'No publication date, coordinates or granted licences inferred.',
    'PDF links are inventoried; document contents are not parsed and all downloads are not validated.',
    'Legacy documentacion-concejales buttons are excluded in favour of the public PGM navigation tree.',
]


def canonical(url):
    parts = urlsplit(url)
    if parts.hostname not in {'olivafrontera.com', 'www.olivafrontera.com'}:
        raise ValueError(f'Unexpected source host: {url}')
    return urlunsplit(('https', 'olivafrontera.com', parts.path, parts.query, ''))


def parse_page(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    content = soup.select_one('#content .post-content')
    if main is None or content is None:
        raise ValueError(f'Missing municipal document content: {url}')
    # A new pagination mechanism must be reviewed, never silently dropped.
    if main.select('.pagination, .page-links, a[rel~=next], a.next, .nav-links'):
        raise ValueError('Paginated document tree needs review')
    pages = set()
    for a in main.select('a[href]'):
        href = urljoin(url, a['href'])
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', 'más', 'anterior'}:
            raise ValueError('Paginated document tree needs review')
        p = urlsplit(href)
        if p.hostname in {'olivafrontera.com', 'www.olivafrontera.com'} and p.path.startswith('/plan-general-municipal/'):
            if p.query or '/page/' in p.path:
                raise ValueError('Unexpected pagination/query in document tree')
            pages.add(canonical(href))
    documents = []
    for a in content.select('a[href]'):
        href = urljoin(url, a['href'])
        p = urlsplit(href)
        if p.path.lower().endswith('.pdf'):
            target = canonical(href)
            if not p.path.startswith('/wp-content/uploads/'):
                raise ValueError('Unexpected document location')
            documents.append({'titulo': a.get_text(' ', strip=True) or unquote(p.path.rsplit('/', 1)[-1]),
                              'url': target, 'source_page': url})
        elif p.path.startswith('/documentacion-concejales/') and p.hostname in {'olivafrontera.com', 'www.olivafrontera.com'}:
            continue  # Old buttons; the sidebar exposes the public equivalent tree.
        elif canonical(href) not in pages:
            raise ValueError(f'Unreviewed content link: {href}')
    return sorted(pages), documents, main.get_text(' ', strip=True)


class OlivaDeLaFronteraAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(url, timeout=45)
        response.raise_for_status()
        if canonical(response.url) != url:
            raise ValueError(f'Unexpected source redirect: {response.url}')
        response.encoding = 'utf-8'
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            folder = Path(capture_dir)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / ('page-' + hashlib.sha256(url.encode()).hexdigest()[:12] + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(output)

    def backfill_proyectos(self, out_jsonl):
        pending, visited, documents = [SOURCE], set(), {}
        agreement_date = None
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'
            while pending:
                url = pending.pop(0)
                if url in visited:
                    continue
                if len(visited) >= 200:
                    raise ValueError('Document tree expanded beyond reviewed scope; no partial output written')
                pages, docs, text = parse_page(self._fetch(session, url), url)
                visited.add(url)
                pending.extend(p for p in pages if p not in visited and p not in pending)
                if url == SOURCE:
                    match = re.search(r'versi[oó]n aprobada inicialmente por el pleno en sesi[oó]n ordinaria celebrada el d[ií]a (\d{1,2})-(\d{1,2})-(\d{2}|\d{4})\b', text, re.I)
                    if not match:
                        raise ValueError('PGM version/approval label changed; review before extraction')
                    day, month, year = map(int, match.groups())
                    agreement_date = date(year + 2000 if year < 100 else year, month, day).isoformat()
                for doc in docs:
                    entry = documents.setdefault(doc['url'], {'titulo': doc['titulo'], 'url': doc['url'], 'source_pages': []})
                    if url not in entry['source_pages']:
                        entry['source_pages'].append(url)
        if not documents:
            raise ValueError('No PGM documents discovered')
        row = {
            'id': 'oliva-de-la-frontera-pgm-version-' + agreement_date,
            'municipio': 'Oliva de la Frontera', 'codigo_ine': '06093', 'provincia': 'Badajoz',
            'titulo': 'Plan General Municipal de Oliva de la Frontera — versión aprobada inicialmente',
            'tipo': 'planeamiento_urbanistico', 'fase': 'aprobacion_inicial',
            'fecha_acuerdo': agreement_date, 'fecha_acuerdo_source_url': SOURCE,
            'url': SOURCE, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_pgm', 'documentos': sorted(documents.values(), key=lambda d: d['url']),
            'source_urls': sorted(visited), 'limitations': LIMITATIONS,
            'publication_ready': False, 'geometry_status': 'unavailable',
        }
        self._write(out_jsonl, [row])
        return {'count': 1, 'written': 1, 'documents': len(documents), 'source_urls': sorted(visited),
                'limitations': LIMITATIONS, 'coverage': 'public_pgm_version_document_tree'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
