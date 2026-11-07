"""Snapshot of the municipal transparency planning-document inventory (IND-53)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://transparencia.castillejadelacuesta.es/es/transparencia/'
          'indicadores-de-transparencia/indicador/'
          'Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00036')
DOC_PREFIX = '/export/sites/castillejadelacuesta/es/transparencia/.galleries/IND-53-/PLANES-PARCIALES/'
LIMITATIONS = [
    'Partial municipal coverage: only IND-53 planning galleries with linked PDFs; '
    'not a complete historical register, PGOM inventory or physical works inventory.',
    'Empty galleries and external PGOM landing link excluded. Inventory labels do not '
    'establish current legal validity, approval, execution or a granted licence.',
    'PDF contents are not parsed; agreement, approval and publication dates remain unknown. '
    'No verified coordinates or geometry; publication_ready=false.',
]


def _text(tag):
    return ' '.join(tag.get_text(' ', strip=True).split())


def page_url(href):
    """Accept only this inventory's independent gallery pagination parameters."""
    target = urlsplit(urljoin(SOURCE, href))
    origin = urlsplit(SOURCE)
    if (target.scheme, target.netloc, target.path) != (origin.scheme, origin.netloc, origin.path):
        raise ValueError('Unexpected pagination destination')
    params = parse_qsl(target.query, keep_blank_values=True)
    if not params:  # Disabled first/previous controls use fragment-only links.
        return SOURCE
    if len(params) != 1 or not re.fullmatch(r'pagegalleryfiles-\d+-\d+', params[0][0]):
        raise ValueError('Unrecognised gallery pagination')
    if not params[0][1].isdigit() or int(params[0][1]) < 1:
        raise ValueError('Invalid gallery page number')
    return urlunsplit((target.scheme, target.netloc, target.path, urlencode(params), ''))


def parse_inventory(html, source_url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.sg-indicador-trans')
    heading = article.select_one('h2.title') if article else None
    if not heading or 'Modificaciones aprobadas del PGOU' not in _text(heading):
        raise ValueError('Expected municipal planning inventory is missing')
    groups, pages = {}, set()
    for block in article.select('.contentblock'):
        parent = block.find('h3', recursive=False)
        if not parent:
            continue
        context = _text(parent)
        for gallery in block.select('section.gallery'):
            title_tag = gallery.select_one('h4.gallery-title')
            if not title_tag:
                raise ValueError('Gallery without an instrument heading')
            title = _text(title_tag)
            if not re.search(r'PLAN|PROYECTO|ESTUDIO DE DETALLE|PGMO', context + ' ' + title, re.I):
                continue
            key = context + ' / ' + title
            docs = {}
            for a in gallery.select('a[href]'):
                target = urlsplit(urljoin(SOURCE, a['href']))
                if target.path.lower().endswith('.pdf'):
                    if target.netloc != urlsplit(SOURCE).netloc or not target.path.startswith(DOC_PREFIX):
                        raise ValueError('Document outside the verified planning inventory')
                    url = urlunsplit((target.scheme, target.netloc, target.path, target.query, ''))
                    docs[url] = {'titulo': _text(a), 'url': url, 'source_urls': [source_url]}
            pagination = gallery.select('.pagination a[href]')
            advertised = set()
            if pagination:
                last = gallery.select_one('.pagination a.lastpagelink[href]')
                if not last:
                    raise ValueError('Pagination has no declared last page')
                last_url = page_url(last['href'])
                bounds = parse_qsl(urlsplit(last_url).query)
                if not bounds and last['href'].startswith('#'):
                    active = gallery.select_one('.pagination .active a[href]')
                    if active:
                        bounds = parse_qsl(urlsplit(page_url(active['href'])).query)
                if not bounds or int(bounds[0][1]) > 100:
                    raise ValueError('Invalid pagination bounds')
                parameter, final_page = bounds[0]
                # OpenCMS emits phantom next/previous links when a shared
                # parameter exceeds a shorter gallery's last page. Enumerate
                # exactly 1..last, including pages hidden by sliding controls.
                for n in range(1, int(final_page) + 1):
                    advertised.add((parameter, str(n)))
                    pages.add(SOURCE + '?' + urlencode({parameter: n}))
            # Some parameter names repeat in different galleries. Validate only
            # galleries advertising the requested page, preserving heading context.
            requested = set(parse_qsl(urlsplit(source_url).query))
            if requested & advertised:
                active = gallery.select_one('.pagination .active a[href]')
                if not active or set(parse_qsl(urlsplit(page_url(active['href'])).query)) != requested:
                    raise ValueError('Server did not honour gallery pagination')
            groups[key] = {'context': context, 'title': title, 'documents': docs,
                           'requested_page': bool(requested & advertised) and any(
                               int(v) > 1 for _, v in requested)}
    if not groups or not any(g['documents'] for g in groups.values()):
        raise ValueError('No usable planning documents found')
    return groups, pages


def collect_inventory(fetch):
    """Follow every advertised page; fail rather than return a truncated snapshot."""
    pending, visited, merged, first_signatures = {SOURCE}, set(), {}, {}
    while pending:
        url = min(pending)
        pending.remove(url)
        if url in visited:
            continue
        if len(visited) >= 100:
            raise ValueError('Unexpected pagination size; refusing partial extraction')
        groups, pages = parse_inventory(fetch(url), url)
        visited.add(url)
        if url == SOURCE:
            expected = set(groups)
        elif set(groups) != expected:
            raise ValueError('Instrument headings changed between inventory pages')
        for key, group in groups.items():
            documents = group['documents']
            signature = frozenset(documents)
            if url == SOURCE:
                first_signatures[key] = signature
            elif group['requested_page'] and (not signature or signature == first_signatures[key]):
                raise ValueError('Gallery page is empty or repeats page one')
            target = merged.setdefault(key, {**group, 'documents': {}})
            for doc_url, doc in documents.items():
                if doc_url in target['documents']:
                    sources = target['documents'][doc_url]['source_urls']
                    if url not in sources:
                        sources.append(url)
                else:
                    target['documents'][doc_url] = doc
        pending.update(pages - visited)
    rows, duplicate_sets = [], {}
    for key, group in sorted(merged.items()):
        docs = group['documents']
        if not docs:  # Heading-only or explicitly empty urbanisation galleries.
            continue
        fingerprint = tuple(sorted(docs))
        if fingerprint in duplicate_sets:
            existing = duplicate_sets[fingerprint]
            existing['inventory_headings'].append(key)
            for doc in existing['documentos']:
                doc['source_urls'] = sorted(set(doc['source_urls']) | set(docs[doc['url']]['source_urls']))
            continue
        row = {
            'id': 'castilleja-de-la-cuesta-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Castilleja de la Cuesta', 'codigo_ine': '41029', 'provincia': 'Sevilla',
            'titulo': key, 'tipo': 'instrumento o proyecto de planeamiento y gestión urbanística',
            'url': SOURCE, 'inventory_url': SOURCE, 'inventory_headings': [key],
            'documentos': [docs[u] for u in sorted(docs)],
            'source': 'ayuntamiento', 'source_entity_type': 'documento',
            'origen': 'inventario_planeamiento_IND_53',
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'coverage': 'current_document_inventory',
        }
        duplicate_sets[fingerprint] = row
        rows.append(row)
    if not rows:
        raise ValueError('Empty planning snapshot')
    return rows, sorted(visited)


class CastillejaDeLaCuestaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        with requests.get(url, timeout=45, stream=True, headers={
            'User-Agent': 'municipio-castilleja-de-la-cuesta/1.0'
        }) as response:
            response.raise_for_status()
            if page_url(response.url) != url:
                raise ValueError('Unexpected inventory redirect')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 5_000_000:
                    raise ValueError('Inventory exceeds response limit')
            html = content.decode('utf-8')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            name = 'inventory-' + hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (path / name).write_text(html, encoding='utf-8')
        return html

    def backfill_proyectos(self, out_jsonl: Path):
        rows, sources = collect_inventory(self._fetch)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': sources,
                'documents': sum(len(r['documentos']) for r in rows),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
