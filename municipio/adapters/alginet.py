"""Alginet's public WordPress planning inventories; no inferred legal status."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://web.alginet.es/'
SLUGS = ('pgou', 'pla-general')
LIMITATIONS = [
    'Partial coverage: PGOU and preliminary PGE inventories only; not the full municipal noticeboard or regional register.',
    'Historical documents currently served by the municipal CMS do not establish present legal validity or execution.',
    'No granted licences, geometry, inferred agreement dates or inferred approval dates.',
    'Document links retained; attachments are not all downloaded or individually verified.',
]


def inventory_url(slug, page=1):
    return BASE + '?' + urlencode({'rest_route': '/wp/v2/pages', 'slug': slug,
                                  'per_page': 100, 'page': page})


def documents(block, source_url):
    result = {}
    for a in block.select('a[href]'):
        url = urljoin(BASE, a['href'])
        parsed = urlparse(url)
        if parsed.hostname != 'web.alginet.es' or not re.search(r'\.(pdf|zip)$', parsed.path, re.I):
            continue
        title = a.get_text(' ', strip=True)
        doc = {'titulo': title, 'url': url, 'source_url': source_url}
        date = re.search(r'Pub\.\s*(\d{2}/\d{2}/\d{4})', title)
        if date:
            doc['fecha_publicacion'] = datetime.strptime(date[1], '%d/%m/%Y').date().isoformat()
        else:
            partial = re.search(r'Pub\.\s*(\d{2}/\d{4})', title)
            if partial:
                doc['fecha_publicacion_texto'] = partial[1]
        result.setdefault(url, doc)
    return list(result.values())


def parse_page(page, source_url):
    slug = page.get('slug')
    if slug not in SLUGS or page.get('status') != 'publish':
        raise ValueError('Unexpected planning page')
    html = page.get('content', {}).get('rendered', '')
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('.page-links, .pagination, a[rel="next"]') or '<!--nextpage-->' in html:
        raise ValueError('Planning content pagination requires review')
    rows = []

    def record(title, docs):
        if not docs:
            raise ValueError('Planning instrument has no source documents: ' + title)
        identity = str(page['id']) + ':' + min(d['url'] for d in docs)
        return {'id': 'alginet-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
                'municipio': 'Alginet', 'codigo_ine': '46031', 'provincia': 'Valencia',
                'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
                'url': BASE + '?page_id=' + str(page['id']),
                'inventory_url': source_url, 'documentos': docs,
                'publication_ready': False, 'geometry_status': 'unavailable',
                'coverage': 'partial_municipal_planning_inventory'}

    if slug == 'pla-general':
        heading = next((h for h in soup.select('h1,h2,h3,h4,h5')
                        if 'Versió preliminar' in h.get_text()), None)
        if heading is None:
            raise ValueError('Preliminary PGE heading missing')
        rows.append(record(heading.get_text(' ', strip=True), documents(soup, source_url)))
    else:
        primary = None
        for block in soup.select('.widget_sow-editor .siteorigin-widget-tinymce'):
            h = block.select_one('h5')
            if not h:
                continue
            title = h.get_text(' ', strip=True)
            if re.match(r"^(Pla General d'Urbanisme|Modificació)\b", title):
                row = record(title, documents(block, source_url))
                rows.append(row)
                if title.startswith('Pla General'):
                    primary = row
        if primary is None:
            raise ValueError('PGOU inventory missing primary instrument')
        # Maps and the catalogue are components of the PGOU, not separate projects.
        used = {d['url'] for r in rows for d in r['documentos']}
        primary['documentos'].extend(d for d in documents(soup, source_url) if d['url'] not in used)
    if not rows:
        raise ValueError('No supported planning instruments')
    return rows


class AlginetAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        rows, sources = [], []
        captures = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-alginet/1.0 (public planning inventory)'
            for slug in SLUGS:
                page_number, total = 1, None
                found = []
                while total is None or page_number <= total:
                    url = inventory_url(slug, page_number)
                    response = session.get(url, timeout=40)
                    response.raise_for_status()
                    if urlparse(response.url).hostname != 'web.alginet.es':
                        raise ValueError('Unexpected API redirect')
                    pages = int(response.headers['X-WP-TotalPages'])
                    if total is not None and total != pages:
                        raise ValueError('Inventory changed during pagination')
                    total = pages
                    payload = response.json()
                    if not isinstance(payload, list) or not payload:
                        raise ValueError('Missing planning inventory')
                    sources.append(response.url)
                    if captures:
                        directory = Path(captures)
                        directory.mkdir(parents=True, exist_ok=True)
                        (directory / f'{slug}-{page_number}.json').write_text(response.text, encoding='utf-8')
                    for page in payload:
                        found.append(page['id'])
                        rows.extend(parse_page(page, response.url))
                    page_number += 1
                if len(found) != 1:
                    raise ValueError('Expected one unique CMS page per planning inventory')
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate planning instrument identities')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'source_urls': sources, 'limitations': LIMITATIONS}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
