"""Municipal PXOM document inventory: one instrument, multiple source documents."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://concello.ordes.gal'
INVENTORY = BASE + '/p/pxom'
LIMITATIONS = [
    'Partial coverage: municipal current PXOM and its linked processing documents only; '
    'not a complete inventory of development plans, modifications, agreements or public works.',
    'No granted-licence register extracted; application forms and news excluded.',
    'Linked PDFs, registry/ SIOTUGA entries and municipal Google Drive folders are retained '
    'as references; their contents are not recursively extracted.',
    'No verified instrument geometry; coordinates remain null.',
    'fecha_publicacion is the DOG approval-notice publication date, not the municipal '
    'webpage date or the BOP ordinance publication date.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).replace('\u200b', '').split())


def _numeric_date(text):
    matches = re.findall(r'\b(\d{2})/(\d{2})/(\d{4})\b', text)
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous explicit date: ' + text)
    return datetime.strptime('/'.join(matches[0]), '%d/%m/%Y').date().isoformat()


def _no_pagination(soup):
    # These are static document inventories. New pagination needs explicit review.
    if soup.select('.pagination, .pager, a[rel~=next], link[rel~=next]'):
        raise ValueError('Pagination appeared; refusing a partial PXOM inventory')
    for a in soup.select('a[href]'):
        if _text(a).casefold() in {'seguinte', 'siguiente', 'next', '»', '›'}:
            if a['href'] not in {'', '#'}:
                raise ValueError('Pagination appeared; refusing a partial PXOM inventory')


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    _no_pagination(soup)
    content = soup.select_one('.content-wrapper')
    if content is None or content.select_one('h1') is None:
        raise ValueError('Municipal document page markup changed')
    return content


def discover_pages(html):
    """Discover the current plan and processing page from the planning menu."""
    soup = BeautifulSoup(html, 'html.parser')
    _no_pagination(soup)
    menus = [a.parent for a in soup.select('a.trigger')
             if _text(a) == 'PLANEAMENTO URBANISTICO']
    current, history = set(), set()
    for menu in menus:
        for a in menu.select('a[href]'):
            url = urljoin(INVENTORY, a['href'])
            if urlparse(url).hostname != urlparse(BASE).hostname:
                raise ValueError('Planning menu points outside municipal portal')
            title = _text(a)
            if re.match(r'^PXOM AD \(en vigor ', title):
                current.add(url)
            elif title == 'DOC. TRAMITACIÓN PXOM':
                history.add(url)
    if len(current) != 1 or len(history) != 1:
        raise ValueError('Expected one current PXOM and one processing inventory')
    return next(iter(current)), next(iter(history))


def parse_plan(html, url):
    content = _content(html)
    heading = _text(content.select_one('h1'))
    if not re.match(r'^PXOM AD \(en vigor ', heading):
        raise ValueError('Source no longer identifies the current PXOM')
    docs = {}
    for a in content.select('ol a[href]'):
        title = _text(a)
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        if parsed.scheme not in {'https', 'http'} or not parsed.hostname:
            raise ValueError('Invalid document URL')
        if not title:
            raise ValueError('Unlabelled PXOM document')
        # Registry links say only VER ENLACE: keep their containing section label.
        if title == 'VER ENLACE':
            section = a.find_parent('ul').find_parent('li')
            title = _text(section.find('p'))
        docs.setdefault(target, {'titulo': title, 'url': target,
                                 'source_url': url, 'origen': 'inventario_pxom_vigente'})
    documents = list(docs.values())
    approval = [d for d in documents if d['titulo'].startswith('ORDE APROBACIÓN DEFINITIVA')]
    dog = [d for d in documents if '/dog/' in urlparse(d['url']).path
           and urlparse(d['url']).hostname == 'www.xunta.gal'
           and 'CONCELLO DE ORDES' in d['titulo']]
    if len(approval) != 1 or len(dog) != 1 or len(documents) < 7:
        raise ValueError('Incomplete or ambiguous current PXOM document inventory')
    return {
        'id': 'ordes-proy-pxom', 'municipio': 'Ordes', 'codigo_ine': '15059',
        'provincia': 'A Coruña', 'titulo': 'Plan xeral de ordenación municipal de Ordes (PXOM)',
        'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación definitiva',
        'fecha': None, 'fecha_aprob': _numeric_date(approval[0]['titulo']),
        'fecha_acuerdo': _numeric_date(approval[0]['titulo']),
        'fecha_publicacion': _numeric_date(dog[0]['titulo']),
        'fecha_entrada_vigor': _numeric_date(heading),
        'url': url, 'url_documento': approval[0]['url'],
        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
        'descripcion': heading,
        'documentos': documents,
        'provenance': {
            'fecha_aprob': {'source_url': url, 'texto': approval[0]['titulo'],
                            'document_url': approval[0]['url']},
            'fecha_publicacion': {'source_url': url, 'texto': dog[0]['titulo'],
                                 'document_url': dog[0]['url'], 'boletin': 'DOG'},
            'fecha_entrada_vigor': {'source_url': url, 'texto': heading},
        },
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'cobertura': 'parcial: PXOM vigente y documentos de tramitación enlazados',
    }


def parse_history(html, url):
    content = _content(html)
    if _text(content.select_one('h1')) != 'DOC. TRAMITACIÓN PXOM':
        raise ValueError('Processing inventory heading changed')
    if 'PLAN XERAL DE ORDEACIÓN MUNICIPAL DE ORDES' not in _text(content):
        raise ValueError('Processing page does not identify the Ordes PXOM')
    docs = {}
    for a in content.select('ol a[href]'):
        title = _text(a)
        if not re.match(r'^APROBACIÓN (INICIAL|PROVISIONAL)', title):
            raise ValueError('Unknown processing document; review grouping before extraction')
        target = urljoin(url, a['href'])
        if urlparse(target).hostname != 'drive.google.com':
            raise ValueError('Processing document host changed; review source')
        docs.setdefault(target, {'titulo': title, 'url': target,
                                 'source_url': url, 'origen': 'tramitacion_pxom',
                                 'fecha_acuerdo': _numeric_date(title),
                                 'formato': 'carpeta_documental_enlazada'})
    if not docs:
        raise ValueError('Empty PXOM processing inventory')
    return list(docs.values())


class OrdesAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(url, timeout=35)
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(BASE).hostname:
            raise ValueError('Unexpected redirect outside municipal portal')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected municipal HTML inventory')
        response.encoding = 'utf-8'
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (urlparse(url).path.rsplit('/', 1)[-1] + '.html')).write_text(
                response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                       encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-ordes/1.0 (public planning inventory)'
            current, history = discover_pages(self._fetch(session, INVENTORY))
            row = parse_plan(self._fetch(session, current), current)
            row['documentos'].extend(parse_history(self._fetch(session, history), history))
        row['source_urls'] = [INVENTORY, current, history]
        self._write(out_jsonl, [row])
        return {'status': 'ok', 'rows': 1, 'source_urls': row['source_urls'],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # A complete refresh of this explicitly scoped, unpaginated inventory.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
