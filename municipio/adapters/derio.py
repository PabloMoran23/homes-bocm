"""Derio's municipal planning library and the linked PGOU document inventory."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.derio.eus/es/territorio/'
LIMITATIONS = [
    'Cobertura parcial: biblioteca municipal de Normas Subsidiarias y nuevo PGOU; '
    'no incluye el registro foral de planeamiento de desarrollo ni obras o licencias.',
    'Las fases describen lo publicado en estas páginas, que pueden estar desactualizadas; '
    'no acreditan la situación administrativa completa a fecha de extracción.',
    'Fechas de publicación y acuerdo no verificadas; las rutas de carga no son fechas de aprobación.',
    'Se retienen todos los enlaces documentales publicados sin comprobar cada PDF; '
    'no se extraen geometrías de los planos.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href]'):
        if a['href'] in ('', '#'):
            continue
        if ('next' in a.get('rel', []) or
                a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'hurrengoa', '»', '›'}):
            raise ValueError('Pagination detected; review source before accepting a partial inventory')
    if soup.select('.pager, .pagination, .nav-links, [data-server-side="true"]'):
        raise ValueError('Unreviewed pagination markup')
    return soup


def _documents(scope, base, host):
    documents = {}
    for a in scope.select('a[href]'):
        url = urljoin(base, a['href']).split('#')[0]
        parsed = urlparse(url)
        if parsed.hostname == host and parsed.scheme == 'https' and parsed.path.lower().endswith('.pdf'):
            documents.setdefault(url, {
                'titulo': a.get_text(' ', strip=True), 'url': url,
                'url_fuente': base, 'procedencia': 'enlace publicado en inventario oficial',
            })
    if not documents:
        raise ValueError('Planning inventory has no source documents')
    return list(documents.values())


def _record(key, title, kind, url, documents):
    return {
        'id': 'derio-proy-' + key, 'municipio': 'Derio', 'codigo_ine': '48901',
        'provincia': 'Bizkaia', 'titulo': title, 'tipo': kind,
        'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'documentos': documents, 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'limitaciones': LIMITATIONS,
    }


class DerioAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = _soup(html)
        libraries = []
        for app in soup.select('.cf-app[data-json]'):
            settings = json.loads(app['data-json'])
            if settings.get('title', '').casefold() == 'normas subsidiarias':
                # In the reviewed single-folder gallery all rows are server-rendered;
                # limit controls client-side DataTables display, not response size.
                if settings.get('libraryType') != 'single_folder' or settings.get('isNestedFolders'):
                    raise ValueError('Changed document gallery coverage')
                libraries.append(app)
        if len(libraries) != 1:
            raise ValueError('Missing or ambiguous Normas Subsidiarias library')
        docs = _documents(libraries[0], SOURCE, 'www.derio.eus')
        titles = ' '.join(d['titulo'].lower() for d in docs)
        if not all(token in titles for token in ('normas urbanisticas', 'memoria', 'nnss')):
            raise ValueError('Incomplete Normas Subsidiarias document inventory')
        row = _record('nnss', 'Normas Subsidiarias de Derio', 'normas_subsidiarias', SOURCE, docs)
        urls = {urljoin(SOURCE, a['href']) for a in soup.select('a[href]')
                if a.get_text(' ', strip=True) == 'Derio HAPO PGOU'}
        if len(urls) != 1 or urlparse(next(iter(urls))).hostname != 'hapo-derio.eus':
            raise ValueError('Missing or ambiguous municipal PGOU link')
        return row, next(iter(urls))

    @staticmethod
    def documentation_url(html, home):
        soup = _soup(html)
        urls = {urljoin(home, a['href']) for a in soup.select('a[href]')
                if a.get_text(' ', strip=True).upper() == 'DOCUMENTACIÓN'}
        if len(urls) != 1 or urlparse(next(iter(urls))).hostname != 'hapo-derio.eus':
            raise ValueError('Missing or ambiguous PGOU documentation inventory')
        return next(iter(urls))

    @staticmethod
    def parse_pgou(html, url):
        soup = _soup(html)
        body = soup.select_one('.field--name-body')
        if body is None:
            raise ValueError('Missing PGOU document body')
        text = body.get_text(' ', strip=True)
        phase = re.search(r'Fase\s+3:\s*Exposición pública\s*\(Avance\)', text)
        if not phase:
            raise ValueError('PGOU phase changed; review instead of assigning stale status')
        docs = _documents(body, url, 'hapo-derio.eus')
        if not any(d['titulo'] == 'Documento de Avance' for d in docs):
            raise ValueError('PGOU lacks the actual Avance document')
        row = _record('pgou', 'Plan General de Ordenación Urbana de Derio (PGOU)',
                      'plan_general_ordenacion_urbana', url, docs)
        row['fase'] = phase[0]
        row['fase_fuente'] = url
        return row

    def _fetch(self, url, capture_name):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-derio/1.0'})
        response.raise_for_status()
        if len(response.content) > 8_000_000:
            raise ValueError('Source response exceeds reviewed size')
        if self.config.get('capture_dir'):
            target = Path(self.config['capture_dir'])
            target.mkdir(parents=True, exist_ok=True)
            (target / capture_name).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        nnss, home = self.parse_inventory(self._fetch(SOURCE, 'territorio.html'))
        url = self.documentation_url(self._fetch(home, 'hapo.html'), home)
        pgou = self.parse_pgou(self._fetch(url, 'documentacion.html'), url)
        pgou['url_portal'] = home
        self._write(out_jsonl, [nnss, pgou])
        return {'status': 'ok', 'rows': 2, 'source_urls': [SOURCE, home, url],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
