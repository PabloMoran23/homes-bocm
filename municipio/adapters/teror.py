"""Teror's municipal planning document inventories; no inferred legal status."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://teror.es/urbanismo/'
INSTRUMENT_PATHS = {
    '/plan-general-de-ordenacion-supletorio-de-teror/': 'pgo',
    '/oficina-tecnica-pepri/': 'pepri',
}


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('article .entry-content')
    if content is None:
        raise ValueError('Missing municipal article content')
    # These inventories currently have no pagination. Fail rather than lose pages.
    if content.select('.page-links, .pagination, a[rel~=next]'):
        raise ValueError('Paginated inventory requires crawler review')
    for a in content.select('a[href]'):
        if re.fullmatch(r'(siguiente|next|[»›])', a.get_text(' ', strip=True), re.I):
            raise ValueError('Paginated inventory requires crawler review')
    return content


def _url(base, href):
    return quote(urljoin(base, href), safe=":/?=&%+#@")


def parse_index(html, url=SOURCE):
    found = {}
    for a in _content(html).select('a[href]'):
        target = _url(url, a['href'])
        parsed = urlparse(target)
        if parsed.hostname == 'teror.es' and parsed.path in INSTRUMENT_PATHS:
            found[parsed.path] = target
    if set(found) != set(INSTRUMENT_PATHS):
        raise ValueError('Reviewed PGO/PEPRI inventory links missing')
    return list(found.values())


def parse_instrument(html, url):
    path = urlparse(url).path
    if urlparse(url).hostname != 'teror.es' or path not in INSTRUMENT_PATHS:
        raise ValueError('Unsupported instrument URL')
    content = _content(html)
    heading = content.select_one('p strong')
    if heading is None:
        raise ValueError('Missing instrument title')
    lines = list(heading.stripped_strings)
    title = ' '.join(line for line in lines if line != 'Aprobación definitiva')
    expected = 'Plan General' if INSTRUMENT_PATHS[path] == 'pgo' else 'PLAN ESPECIAL'
    if expected.casefold() not in title.casefold() or 'teror' not in title.casefold():
        raise ValueError('Unexpected instrument title')
    docs, related = {}, {}
    for a in content.select('a[href]'):
        target = _url(url, a['href'])
        if urlparse(target).hostname != 'teror.es':
            raise ValueError('Unexpected external document; review provenance')
        item = {'titulo': a.get_text(' ', strip=True), 'url': target,
                'source_page': url, 'availability': 'not_checked'}
        if urlparse(target).path.lower().endswith('.pdf'):
            docs.setdefault(target, item)
        elif 'catalogación' in item['titulo'].casefold():
            related.setdefault(target, item)
        else:
            raise ValueError('Unreviewed non-document link in instrument inventory')
    if not docs:
        raise ValueError('Instrument has no PDF documents')
    row = {
        'id': 'teror-plan-' + hashlib.sha256(path.encode()).hexdigest()[:16],
        'municipio': 'Teror', 'codigo_ine': '35027', 'provincia': 'Las Palmas',
        'titulo': title, 'tipo': 'planeamiento_urbanistico',
        'url': url, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
        'origen': 'inventario_documental_planeamiento',
        'documentos': list(docs.values()), 'enlaces_relacionados': list(related.values()),
        'publication_ready': False, 'geometry_status': 'unavailable',
        'coverage': 'Documentos de dos instrumentos enlazados desde Urbanismo; vigencia no verificada',
    }
    if 'Aprobación definitiva' in lines:
        row['estado_documental_fuente'] = 'Aprobación definitiva'
    return row


class TerorAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, name):
        response = requests.get(url, timeout=45, headers={
            'User-Agent': 'municipio-teror-inventory/1.0'})
        response.raise_for_status()
        if response.url != url:
            raise ValueError('Unexpected source redirect: ' + response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            dest = Path(capture_dir)
            dest.mkdir(parents=True, exist_ok=True)
            (dest / (name + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        dest = Path(out_jsonl)
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_suffix(dest.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(dest)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        urls = parse_index(self._fetch(SOURCE, 'urbanismo'))
        rows = [parse_instrument(self._fetch(url, INSTRUMENT_PATHS[urlparse(url).path]), url)
                for url in urls]
        return {**self._write(out_jsonl, rows), 'source_urls': [SOURCE, *urls],
                'coverage': 'two_currently_linked_document_inventories', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot: this inventory provides no reliable incremental dates.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True,
                'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
