"""Oñati's public planning document inventory (not a licence register)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.xn--oati-gqa.eus'
SOURCE = BASE + '/eu/udala/sailak/hirigintza-eta-lurralde-antolamendua/hiri-antolamendua'
LIMITATIONS = [
    'Partial municipal planning document inventory, not all municipal works or historical proceedings.',
    'Documents and area sheets are grouped by instrument, not counted as separate projects.',
    'No verified agreement/approval/publication dates extracted; procurement dates are excluded.',
    'No granted licences extracted. No verified vector geometry or coordinates.',
    'Linked document contents and legal currency are not comprehensively audited.',
]


def canonical(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or '').encode('idna').decode('ascii')
    if host not in {'www.xn--oati-gqa.eus', 'xn--oati-gqa.eus'} or parts.scheme not in {'http', 'https'}:
        raise ValueError(f'Unexpected municipal URL: {url}')
    return urlunsplit(('https', 'www.xn--oati-gqa.eus', parts.path.rstrip('/'), parts.query, ''))


def page(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content')
    body = soup.select_one('#parent-fieldname-text')
    if content is None or body is None:
        raise ValueError('Missing municipal content markup')
    # These reviewed inventories are unpaginated. Fail closed if this changes.
    if soup.select('.pagination, .batching, .listingBar, a[rel~=next]'):
        raise ValueError('Pagination detected: extend traversal before extracting')
    for a in content.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'next', 'siguiente', 'hurrengoa', 'hurrengo', '»'}:
            raise ValueError('Pagination detected: extend traversal before extracting')
    return soup, body


def parse_inventory(html: str):
    soup, body = page(html)
    heading = next((s.get_text(' ', strip=True) for s in body.select('strong')
                    if 'OÑATIKO HIRI ANTOLAKETAKO ARAUAK' in s.get_text().upper()), None)
    if not heading:
        raise ValueError('Missing consolidated planning rules heading')
    sections, instruments = {}, {}
    for a in body.select('a[href]'):
        raw = urljoin(SOURCE, a['href'])
        if '/hiri-antolamendua/' in raw:
            sections[canonical(raw)] = a.get_text(' ', strip=True)
        elif '/udala/planak/hapo-' in raw:
            instruments[canonical(raw)] = 'hapo'
    for a in soup.select('#content .secondarynav a[href]'):
        if a.get_text(' ', strip=True).casefold() != 'arau aldaketa':
            raise ValueError('Unreviewed instrument in secondary inventory')
        instruments[canonical(urljoin(SOURCE, a['href']))] = 'modificacion'
    if not sections:
        raise ValueError('Missing planning document sections')
    return heading, sections, instruments


def parse_documents(html: str, url: str):
    soup, body = page(html)
    title = soup.select_one('#content h1')
    if not title:
        raise ValueError('Missing instrument title')
    docs = {}
    for a in body.select('a[href]'):
        raw = urljoin(url, a['href'])
        participation = urlsplit(raw).path.rstrip('/').endswith('/tramiteak/herritarrek-parte-hartzeko-programa')
        if not participation and not urlsplit(raw).path.lower().endswith(('.pdf', '.jpg', '.png', '.zip')):
            continue
        target = canonical(raw)
        # Filenames disambiguate generic "pdf, size" link labels in the old rules.
        docs.setdefault(target, {
            'titulo': a.get_text(' ', strip=True) or urlsplit(target).path.rsplit('/', 1)[-1],
            'archivo': urlsplit(target).path.rsplit('/', 1)[-1],
            'url': target, 'source_url': url,
            'seccion': title.get_text(' ', strip=True),
        })
    if not docs or not any(urlsplit(u).path.lower().endswith('.pdf') for u in docs):
        raise ValueError(f'No planning PDFs found at {url}')
    description = soup.select_one('#content .documentDescription')
    return title.get_text(' ', strip=True), description.get_text(' ', strip=True) if description else '', list(docs.values())


class OnatiAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        url = canonical(url)
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-onati-inventory/1.0'})
        response.raise_for_status()
        if canonical(response.url) != url:
            raise ValueError(f'Unexpected source redirect: {response.url}')
        capture_dir = self.config.get('evidence_dir')
        if capture_dir:
            dest = Path(capture_dir)
            dest.mkdir(parents=True, exist_ok=True)
            (dest / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _record(url, title, kind, docs, description=''):
        return {
            'id': 'onati-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'municipio': 'Oñati', 'codigo_ine': '20059', 'provincia': 'Gipuzkoa',
            'titulo': title, 'tipo': kind, 'url': url, 'inventory_url': SOURCE,
            'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
            'descripcion': description, 'documentos': docs,
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }

    @staticmethod
    def _write(out_jsonl, rows):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(output)

    def backfill_proyectos(self, out_jsonl):
        title, sections, instruments = parse_inventory(self._fetch(SOURCE))
        sources = [SOURCE]
        docs = {}
        for url in sections:
            _, _, documents = parse_documents(self._fetch(url), url)
            sources.append(url)
            for doc in documents:
                docs.setdefault(doc['url'], doc)
        rows = [self._record(SOURCE, title, 'normas_subsidiarias', list(docs.values()))]
        for url, kind in instruments.items():
            name, description, documents = parse_documents(self._fetch(url), url)
            sources.append(url)
            rows.append(self._record(url, name, kind, documents, description))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'live_records': len(rows), 'source_urls': sources,
                'limitations': LIMITATIONS, 'documents': sum(len(r['documentos']) for r in rows)}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh of the reviewed inventory; no date-based filtering.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
