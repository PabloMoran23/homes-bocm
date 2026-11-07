"""Municipal planning document inventories, grouped by instrument (not by PDF)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.alaracha.gal'
SOURCE = BASE + '/gl/pagina/177/urbanismo/'
LIMITATIONS = [
    'Partial coverage: municipal PXOM and educational facilities special-plan document inventories only; no comprehensive registry of modifications, works or licences.',
    'HTML inventories have no explicit publication/agreement/approval dates. Dates and phase remain unknown; PDF contents are not parsed.',
    'Documents are source links, not individual projects. Availability of every linked PDF is not verified.',
    'Source anomalies retained: Estrutura Xeral 5 and 6 share a URL; rural inventory repeats NR-O-19 and NR-O/P-60 and does not link NR-O-20.',
    'No verified vector geometry or coordinates; PDF plans are not converted into geometry.',
]


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def official_url(base, href):
    url = urljoin(base, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'www.alaracha.gal' or parsed.query or parsed.fragment:
        raise ValueError(f'Unexpected inventory URL: {url}')
    return url


def check_pagination(soup):
    # These are unpaginated document inventories. Refuse changed pagination
    # rather than accepting the first page as a complete snapshot.
    for a in soup.select('a[href]'):
        if (a.get('rel') and any(r in {'next', 'prev'} for r in a['rel'])) or norm(a.get_text(' ', strip=True)) in {'seguinte', 'siguiente', 'next', 'anterior', 'ultima', 'última'}:
            if a['href'] not in {'', '#'}:
                raise ValueError('Pagination detected; inventory traversal requires review')
    if soup.select('.pagination, .paginacion, .pager, [data-next-page]'):
        raise ValueError('Pagination detected; inventory traversal requires review')


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    headings = soup.select('h3.kopa-title')
    if len(headings) != 1:
        raise ValueError('Missing or ambiguous municipal content heading')
    block = headings[0].parent
    if 'row' not in block.get('class', []):
        raise ValueError('Municipal content structure changed')
    return headings[0].get_text(' ', strip=True), block


def discover_instruments(html):
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    expected = {'plan xeral': 'pxom', 'plan especial equipamentos educativos': 'equipamentos-educativos'}
    found = {}
    for a in soup.select('a[href]'):
        key = expected.get(norm(a.get_text(' ', strip=True)))
        if key:
            url = official_url(SOURCE, a['href'])
            if not re.fullmatch(r'/gl/pagina/\d+/[a-z-]+/', urlparse(url).path):
                raise ValueError('Unexpected instrument page')
            if key in found and found[key] != url:
                raise ValueError('Conflicting instrument links')
            found[key] = url
    if set(found) != set(expected.values()):
        raise ValueError('Municipal planning navigation missing expected inventories')
    return found


class ALarachaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=35, headers={'User-Agent': 'municipio-a-laracha/1.0'})
        response.raise_for_status()
        if response.url != url or 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Unexpected source redirect or content type')
        if len(response.content) > 5_000_000:
            raise ValueError('Inventory response exceeds reviewed size')
        response.encoding = 'utf-8'
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    def extract(self, fetch):
        instruments = discover_instruments(fetch(SOURCE))
        rows = []
        for key, root in instruments.items():
            pending, seen, docs, pages = [root], set(), {}, []
            title = None
            while pending:
                url = pending.pop(0)
                if url in seen:
                    continue
                if len(seen) >= 100:
                    raise ValueError('Inventory exceeds reviewed traversal size; no partial output written')
                seen.add(url)
                heading, block = content(fetch(url))
                if url == root:
                    required = ({'planos pdf - estrutura xeral', 'planos pdf - nucleos rurais',
                                 'planos pdf - nucleos urbanos', 'normativa'} if key == 'pxom'
                                else {'anexos', 'informacion', 'ordenacion', 'publicacions oficiais'})
                    labels = {norm(a.get_text(' ', strip=True)) for a in block.select('a[href]')}
                    if not required <= labels:
                        raise ValueError('Instrument inventory lost expected sections')
                title = title or heading
                pages.append({'url': url, 'titulo': heading})
                links = block.select('a[href]')
                if not links:
                    raise ValueError(f'Empty document inventory: {url}')
                for a in links:
                    target = official_url(url, a['href'])
                    path = urlparse(target).path
                    label = a.get_text(' ', strip=True)
                    if path.startswith('/panel/subido/documentos/') and path.lower().endswith('.pdf'):
                        doc = docs.setdefault(target, {'url': target, 'titulo': label, 'referencias': []})
                        ref = {'titulo': label, 'pagina_origen': url, 'seccion': heading}
                        if ref not in doc['referencias']:
                            doc['referencias'].append(ref)
                    elif re.fullmatch(r'/gl/pagina/\d+/[a-z-]+/', path):
                        pending.append(target)
                    else:
                        raise ValueError(f'Unrecognized content link: {target}')
            if not docs:
                raise ValueError('Instrument has no source documents')
            if key == 'pxom' and not any('normativa pxom' in norm(d['titulo']) for d in docs.values()):
                raise ValueError('PXOM normative document inventory missing')
            if key == 'equipamentos-educativos' and not any('aprobacion inicial' in norm(d['titulo']) for d in docs.values()):
                raise ValueError('Special plan official publication missing')
            rows.append({
                'id': 'a-laracha-proy-' + key,
                'municipio': 'A Laracha', 'provincia': 'A Coruña', 'codigo_ine': '15041',
                'titulo': title + ' — A Laracha', 'tipo': 'planeamiento_urbanistico',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'fase': None, 'url': root, 'source': 'ayuntamiento',
                'origen': 'inventario_documental_planeamiento',
                'paginas_fuente': [{'url': SOURCE, 'titulo': 'Urbanismo'}] + pages,
                'documentos': list(docs.values()), 'cobertura': 'parcial',
                'limitaciones': LIMITATIONS,
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            })
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        return self._write(out_jsonl, self.extract(self._fetch))

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
