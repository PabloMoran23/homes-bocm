"""Cacabelos planning inventory linked by the municipal urban-planning page."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL_SOURCE = 'https://www.cacabelos.org/ayuntamiento/urbanismo/normativa-urbanistica/'
ARCHIVE = 'https://servicios.jcyl.es/PlanPublica/'
SOURCE = ARCHIVE + 'searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=030'


def _text(node):
    return node.get_text(' ', strip=True)


def _canonical(href, base):
    parts = urlsplit(urljoin(base, href))
    return urlunsplit((parts.scheme, parts.netloc, re.sub(r';jsessionid=[^/?;]+', '', parts.path), parts.query, ''))


def _check_pagination(soup, row_count):
    # The reviewed server page size is 15. Fail explicitly on any indication of
    # further pages (including JS controls), rather than publish a partial page.
    if row_count >= 15:
        raise ValueError('Inventory may be paginated (15 rows); extend traversal before extraction')
    for control in soup.select('a, button, input'):
        attrs = ' '.join(str(v) for v in control.attrs.values())
        if any(int(n) for n in re.findall(r'pager\.offset=(\d+)', unquote(attrs))):
            raise ValueError('Pagination detected; extraction aborted without writing partial output')
        if ('next' in control.get('rel', []) or
                re.search(r'\b(siguiente|next|última|ultima|last)\b', _text(control) + ' ' + attrs, re.I)):
            raise ValueError('Pagination control detected; review source')


def _date(text):
    if not text.strip():
        return None
    return datetime.strptime(text.strip(), '%d/%m/%Y').date().isoformat()


class CacabelosAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        if not any('CACABELOS' in _text(h).upper() for h in soup.select('h1')):
            raise ValueError('Missing Cacabelos inventory heading')
        if not any(re.search(r'Código INE:\s*24030\b', _text(h)) for h in soup.select('h2')):
            raise ValueError('Inventory is not INE 24030')
        tables = [t for t in soup.select('table.cuadroAplicacion')
                  if [_text(h) for h in t.select('th')][:5] ==
                  ['Libro', 'Instrumento', 'Fecha de publicación', 'Fecha de acuerdo', 'Título']]
        if len(tables) != 1:
            raise ValueError('Planning inventory schema changed')
        entries = [tr.find_all('td', recursive=False) for tr in tables[0].select('tr') if tr.find('td')]
        _check_pagination(soup, len(entries))
        rows = {}
        for cells in entries:
            if len(cells) != 6:
                raise ValueError('Unexpected planning row')
            if _text(cells[0]) != 'PU':
                continue  # No licences, forms or other administrative books.
            title, instrument = _text(cells[4]), _text(cells[1])
            if not re.match(r'^(NORMAS SUBSIDIARIAS|MODIFICACIÓN|PLAN PARCIAL|PLAN ESPECIAL|ESTUDIO DE DETALLE)\b', title, re.I):
                raise ValueError('Unreviewed planning instrument: ' + title)
            links = [_canonical(a['href'], SOURCE) for a in cells[5].select('a[href]')]
            files = [u for u in links if urlsplit(u).path == '/PlanPublica/ldoc_files.do'
                     and urlsplit(u).hostname == 'servicios.jcyl.es']
            if len(files) != 1:
                raise ValueError('Instrument lacks an unambiguous document inventory')
            ids = parse_qs(urlsplit(files[0]).query).get('cDocId', [])
            if len(ids) != 1 or not ids[0].isdigit() or ids[0] in rows:
                raise ValueError('Missing or duplicated planning identifier')
            doc_id = ids[0]
            rows[doc_id] = {
                'id': 'cacabelos-plau-' + doc_id, 'municipio': 'Cacabelos',
                'codigo_ine': '24030', 'provincia': 'León',
                'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'instrumento_fuente': instrument, 'plau_id': doc_id,
                'fecha': None, 'fecha_publicacion': _date(_text(cells[2])),
                'fecha_acuerdo': _date(_text(cells[3])), 'fecha_aprob': None,
                'url': files[0], 'url_inventario': SOURCE,
                'url_boletin': ARCHIVE + 'openBoletinDoc.do?cDocId=' + doc_id,
                'source': 'ayuntamiento', 'organismo_fuente': 'Junta de Castilla y León',
                'origen': 'archivo_planeamiento_enlazado_por_ayuntamiento',
                'url_procedencia_municipal': MUNICIPAL_SOURCE,
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'geometry_status': 'unavailable',
            }
        if not rows:
            raise ValueError('No usable planning instruments in current inventory')
        return list(rows.values())

    @staticmethod
    def parse_documents(html, row):
        soup = BeautifulSoup(html, 'html.parser')
        text = _text(soup)
        if not re.search(r'Cacabelos\s*\(León\s*\)', text) or not any(
                _text(h) == row['titulo'] for h in soup.select('h1')):
            raise ValueError('Document inventory municipality/title does not match instrument')
        tables = [t for t in soup.select('table.cuadroAplicacion')
                  if [_text(h) for h in t.select('th')] == ['Nombre del Fichero', 'Fichero']]
        if len(tables) != 1:
            raise ValueError('Document inventory schema changed')
        entries = [tr.find_all('td', recursive=False) for tr in tables[0].select('tr') if tr.find('td')]
        _check_pagination(soup, len(entries))
        docs = {}
        for cells in entries:
            if len(cells) != 2:
                raise ValueError('Unexpected document row')
            anchors = cells[1].select('a[href]')
            if len(anchors) != 1 or not _text(cells[0]):
                raise ValueError('Document row lacks filename or link')
            url = _canonical(anchors[0]['href'], row['url'])
            parts = urlsplit(url)
            ids = parse_qs(parts.query).get('cFicheroId', [])
            if (parts.hostname != 'servicios.jcyl.es' or parts.path != '/PlanPublica/openFichero.do'
                    or len(ids) != 1 or not ids[0].isdigit()):
                raise ValueError('Unexpected document URL')
            docs[url] = {'titulo': _text(cells[0]), 'url': url, 'url_procedencia': row['url']}
        if not docs:
            raise ValueError('Instrument has no linked source files')
        return list(docs.values())

    def _fetch(self, session, url, capture_name):
        response = session.get(url, timeout=(15, 60))
        response.raise_for_status()
        if len(response.content) > 4_000_000:
            raise ValueError('Unexpectedly large HTML inventory')
        html = response.text
        self.source_urls.append(url)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture_name).write_text(html, encoding='utf-8')
        return html

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-cacabelos/1.0 (public planning inventory)'
            municipal = BeautifulSoup(self._fetch(session, MUNICIPAL_SOURCE, 'normativa-urbanistica.html'), 'html.parser')
            if SOURCE not in [_canonical(a['href'], MUNICIPAL_SOURCE) for a in municipal.select('main a[href]')]:
                raise ValueError('Municipal page no longer links the reviewed Cacabelos archive')
            rows = self.parse_inventory(self._fetch(session, SOURCE, 'plau-inventory.html'))
            for row in rows:
                row['documentos'] = self.parse_documents(
                    self._fetch(session, row['url'], 'plau-' + row['plau_id'] + '-files.html'), row)
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': self.source_urls, 'coverage': 'current non-historical PLAU inventory; partial municipal coverage'}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
