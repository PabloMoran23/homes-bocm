"""Canyelles: current official transparency project-document inventory snapshot."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/canyelles/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme')
PLANNING = SOURCE + '/planejament-urbanistic'
LIMITATIONS = [
    'Partial current transparency inventory, not a historical municipal register.',
    'Only project, planning-amendment and reparcelation pages with source documents; '
    'forms, procurement, parcel sales, boundary demarcation and heritage declarations excluded.',
    'Base POUM structured table is not present in fetched HTML; not extracted from search snippets.',
    'Document contents and dates within PDFs are not parsed; links and their page provenance retained.',
    'Page update dates are not publication or approval dates; most agreement dates remain unknown.',
    'No verified geometry; no coordinates or municipal centroid substituted.',
    'No verified public granted-licence inventory; licences disabled.',
]


def _page(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None:
        raise ValueError('Official source lacks main content (possible login/error page)')
    for a in main.select('a[href]'):
        text = a.get_text(' ', strip=True).casefold()
        if (a.get('rel') and 'next' in a['rel']) or text in {
            'següent', 'següents', 'siguiente', 'next', '›', '»'
        } or a.find_parent(class_=re.compile(r'pagination|pager|lfr-pagination')):
            if a['href'] not in {'', '#'}:
                raise ValueError('Pagination detected; extend crawler before emitting a partial snapshot')
    return main


def _date(value, fmt):
    return datetime.strptime(value, fmt).date().isoformat()


def parse_inventory(html):
    """Discover all supported children, without a fixed record cap or slice."""
    main = _page(html)
    found = {}
    for a in main.select('a[href]'):
        url = urljoin(SOURCE, a['href']).rstrip('/')
        title = a.get_text(' ', strip=True)
        if not url.startswith(SOURCE + '/') or urlsplit(url).query:
            continue
        if not re.match(r'^(projecte\b|projectes urbanístics$|memòria modificat|'
                        r'modificació puntual|reparcel·lació)', title, re.I):
            continue
        found.setdefault(url, title)
    if not found:
        raise ValueError('No supported project inventory entries')
    return [(url, title) for url, title in found.items()]


def parse_detail(html, url):
    main = _page(html)
    blocks = [b for b in main.select('.journal-content-article')
              if any('/documents/28721/' in a['href'] for a in b.select('a[href]'))]
    if not blocks:
        raise ValueError(f'Project page has no municipal source documents: {url}')
    docs = {}
    texts = []
    for b in blocks:
        # Ignore script data and generic transparency metadata.
        for el in b.select('script, style, .indicador-dades'):
            el.decompose()
        texts.append(b.get_text(' ', strip=True))
        for a in b.select('a[href]'):
            docurl = urljoin(url, a['href'].strip())
            parts = urlsplit(docurl)
            if parts.hostname not in {'seu-e.cat', 'www.seu-e.cat'} or not parts.path.startswith('/documents/28721/'):
                continue
            # UUID identifies the same attachment even when linked from two versions.
            key = parts.path.rstrip('/').rsplit('/', 1)[-1]
            if not re.fullmatch(r'[0-9a-f-]{36}', key):
                raise ValueError('Unexpected municipal document identifier')
            docs[key] = {'titulo': a.get_text(' ', strip=True).removeprefix('Descarrega '),
                         'url': docurl, 'source_urls': [url]}
    if not docs:
        raise ValueError('No supported municipal document links')
    text = '\n'.join(texts)
    updates = sorted(set(_date(d, '%d/%m/%Y') for d in
                         re.findall(r'Actualització:\s*(\d{2}/\d{2}/\d{4})', text)))
    return list(docs.values()), text, updates


class CanyellesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://seu-e.cat/ca/web/canyelles')
        self.source_urls = []

    def _fetch(self, url):
        with requests.get(url, timeout=40, stream=True, headers={
            'User-Agent': 'municipio-canyelles/1.0'
        }) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname not in {'seu-e.cat', 'www.seu-e.cat'}:
                raise ValueError('Unexpected source redirect')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 5_000_000:
                    raise ValueError('HTML exceeds response limit; refusing truncated content')
        self.source_urls.append(url)
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / (url.rsplit('/', 1)[-1] + '.html')).write_bytes(data)
        return data.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        inventory = parse_inventory(self._fetch(SOURCE))
        rows = []
        for url, title in inventory:
            docs, text, updates = parse_detail(self._fetch(url), url)
            # This generic category currently contains exactly one named instrument.
            if title.casefold() == 'projectes urbanístics':
                names = re.findall(r'(Projecte executiu[^:]+):', text)
                if len(names) != 1:
                    raise ValueError('Generic project page changed; review instrument grouping')
                title = names[0]
            planning = bool(re.match(r'modificació|reparcel', title, re.I))
            row = {
                'id': 'canyelles-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                'municipio': 'Canyelles', 'codigo_ine': '08043', 'provincia': 'Barcelona',
                'titulo': title, 'tipo': 'planeamiento_urbanistico' if planning else 'proyecto_obra',
                'fase': None, 'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_transparencia_urbanismo',
                'source_urls': [url], 'documentos': docs,
                'source_updates': [{'url': url, 'fechas_actualizacion': updates}],
                'descripcion': text, 'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False,
            }
            if re.match(r'Modificació puntual núm\. 2 del POUM$', title, re.I):
                extra, narrative, updated = parse_detail(self._fetch(PLANNING), PLANNING)
                match = re.search(r'MODIFICACIÓ PUNTUAL NÚM\. 2 POUM- Verificació del Ple.*?'
                                  r'data (\d{2}\.\d{2}\.\d{4})', narrative)
                if not match:
                    raise ValueError('MP2 verification narrative changed; review grouping/date semantics')
                row['fase'] = 'verificació municipal'
                row['fecha_acuerdo'] = _date(match[1], '%d.%m.%Y')
                row['source_urls'].append(PLANNING)
                row['source_updates'].append({'url': PLANNING, 'fechas_actualizacion': updated})
                row['descripcion'] += '\n' + narrative
                by_id = {d['url'].rsplit('/', 1)[-1]: d for d in docs}
                for d in extra:
                    key = d['url'].rsplit('/', 1)[-1]
                    if key in by_id:
                        by_id[key]['source_urls'].append(PLANNING)
                    else:
                        by_id[key] = d
                row['documentos'] = list(by_id.values())
            rows.append(row)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full current snapshot; never use page-update timestamps as a cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': LIMITATIONS[-1]}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
