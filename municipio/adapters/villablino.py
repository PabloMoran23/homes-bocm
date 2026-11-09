"""Villablino's current PLAU inventory, linked by the official municipal portal.

The archive's agreement date does not establish the approval stage. Historical
entries, licences, procurement and the municipal news feed are outside coverage.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://servicios.jcyl.es/PlanPublica/'
MUNICIPAL_SOURCE = 'https://www.aytovillablino.com/pagina-principal/areas-municipales/urbanismo/'
SOURCE = ROOT + ('searchVPubDocMuniPlau.do?bInfoPublica=N&pager.sortname=fPublicacion'
                 '&pager.sortindex=-3&provincia=24&municipio=202&filtroSelDoc=TODOS')
LIMITATIONS = [
    'Only the current (historical checkbox off) regional planning inventory linked by the municipality.',
    'No granted-licence register, procurement, news or comprehensive public-works coverage.',
    'Agreement dates retain archive semantics; approval dates and stages are not inferred.',
    'File links retained; PDF contents and the 615 MB municipal RAR are not downloaded or interpreted.',
    'No verified project geometry; coordinates remain null and publication_ready is false.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _date(value):
    if not value:
        return None
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


def _canonical(href):
    parts = urlsplit(urljoin(ROOT, href))
    if parts.hostname != 'servicios.jcyl.es' or not parts.path.startswith('/PlanPublica/'):
        raise ValueError('Unexpected archive link host/path')
    return urlunsplit(('https', parts.netloc, re.sub(r';jsessionid=[^/;?]+', '', parts.path), parts.query, ''))


def _check_pagination(soup):
    # Current inventory fits on one page (default size 15). Fail closed if it
    # expands: never return the first page as a complete municipal inventory.
    for a in soup.select('a'):
        target = (a.get('href', '') + ' ' + a.get('onclick', ''))
        offsets = re.findall(r'pager\.offset=(\d+)', target)
        if any(int(n) > 0 for n in offsets) or 'next' in a.get('rel', []):
            raise ValueError('Archive pagination detected; traversal needs review')
        if _text(a).lower() in {'siguiente', 'next', 'mostrar más', 'última', 'ultima', '>>', '>'}:
            raise ValueError('Archive pagination detected; traversal needs review')


class VillablinoAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.aytovillablino.com')

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        if not re.search(r'VILLABLINO\s+Código INE:\s*24202\b', _text(soup), re.I):
            raise ValueError('Archive municipality identity missing or changed')
        _check_pagination(soup)
        table = soup.select_one('table.cuadroAplicacion')
        if table is None or [_text(th) for th in table.select('tr')[0].select('th')][:5] != [
            'Libro', 'Instrumento', 'Fecha de publicación', 'Fecha de acuerdo', 'Título'
        ]:
            raise ValueError('Planning inventory columns changed')
        rows = []
        for tr in table.select('tr')[1:]:
            cells = tr.find_all('td', recursive=False)
            if len(cells) != 6:
                raise ValueError('Malformed planning inventory row')
            book, kind, publication, agreement, title = map(_text, cells[:5])
            if book not in {'PU', 'GU'} or kind not in {'PGOU', 'PP', 'PAU'} or not title:
                raise ValueError('Unreviewed instrument type in current inventory')
            links = [a['href'] for a in cells[5].select('a[href]') if 'ldoc_files.do' in a['href']]
            ids = {parse_qs(urlsplit(_canonical(h)).query).get('cDocId', [''])[0] for h in links}
            if len(ids) > 1 or (ids and not next(iter(ids)).isdigit()):
                raise ValueError('Ambiguous archive document identifier')
            doc_id = next(iter(ids), None)
            if not doc_id and not cells[5].select_one('img[alt="No hay documentos"]'):
                raise ValueError('Missing archive document identifier without explicit no-documents marker')
            rows.append({'archive_id': doc_id, 'titulo': title, 'tipo': kind,
                         'fecha_publicacion': _date(publication), 'fecha_acuerdo': _date(agreement),
                         'url': _canonical(links[0]) if links else SOURCE})
        if not rows:
            raise ValueError('Empty planning inventory')
        if len(rows) >= 15:
            raise ValueError('Full archive page; pagination must be reviewed before extraction')
        keys = [(r['archive_id'], r['titulo']) for r in rows]
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate planning inventory rows')
        return rows

    @staticmethod
    def parse_files(html, expected_title):
        soup = BeautifulSoup(html, 'html.parser')
        text = _text(soup)
        if 'Villablino' not in text or 'León' not in text or expected_title not in text:
            raise ValueError('File inventory municipality/title mismatch')
        _check_pagination(soup)
        table = soup.select_one('table.cuadroAplicacion')
        if table is None or 'Nombre del Fichero' not in _text(table):
            raise ValueError('Missing file inventory')
        files = {}
        for tr in table.select('tr')[1:]:
            cells = tr.find_all('td', recursive=False)
            if len(cells) != 2:
                raise ValueError('Malformed file inventory row')
            anchors = cells[1].select('a[href]')
            if len(anchors) != 1 or 'openFichero.do' not in anchors[0]['href']:
                raise ValueError('Missing file link')
            url = _canonical(anchors[0]['href'])
            file_id = parse_qs(urlsplit(url).query).get('cFicheroId', [''])[0]
            if not file_id.isdigit() or not _text(cells[0]):
                raise ValueError('Missing file identifier/name')
            files[url] = {'titulo': _text(cells[0]), 'url': url}
        if not files:
            raise ValueError('Empty file inventory')
        return list(files.values())

    @staticmethod
    def group_projects(entries):
        # The sole current PGOU revision and the explicitly PGOU partial-annulment
        # entry are one instrument. Never turn a court publication into a new plan.
        plans = [r for r in entries if r['tipo'] == 'PGOU' and r['titulo'].startswith('PLAN GENERAL')]
        events = [r for r in entries if r['titulo'].startswith('SENTENCIA')]
        if events and (len(plans) != 1 or any('ANULACIÓN PARCIAL DEL PGOU' not in r['titulo'] for r in events)):
            raise ValueError('Ambiguous court-document relationship')
        output = []
        for entry in entries:
            if entry in events:
                continue
            related = [entry] + (events if entry in plans else [])
            identity = entry['archive_id'] or hashlib.sha256(
                (entry['tipo'] + ':' + entry['titulo']).encode()).hexdigest()[:16]
            row = {
                'id': 'villablino-proy-' + identity, 'municipio': 'Villablino',
                'provincia': 'León', 'codigo_ine': '24202', 'titulo': entry['titulo'],
                'tipo': entry['tipo'], 'fase': None, 'fecha': None,
                'fecha_publicacion': entry['fecha_publicacion'],
                'fecha_acuerdo': entry['fecha_acuerdo'], 'fecha_aprob': None,
                'url': entry['url'], 'source': 'ayuntamiento', 'origen': 'archivo_planeamiento_jcyl',
                'source_urls': [MUNICIPAL_SOURCE, SOURCE],
                'archivo_id': entry['archive_id'],
                'documentos': [dict(d, archivo_id=r['archive_id'], url_inventario=r['url'])
                               for r in related for d in r.get('documentos', [])],
                'entradas_archivo': [{k: v for k, v in r.items() if k != 'documentos'} for r in related],
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'limitations': LIMITATIONS,
            }
            if entry in plans and events:
                row['observaciones'] = 'El archivo publica una sentencia de anulación parcial del PGOU; véanse las entradas y documentos relacionados.'
            output.append(row)
        return output

    def _fetch(self, url, capture_name):
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-villablino/1.0'}) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Archive HTML exceeds size bound')
            html = data.decode(response.encoding or 'utf-8')
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir']) / capture_name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        entries = self.parse_inventory(self._fetch(SOURCE, 'live_inventory.html'))
        for entry in entries:
            entry['documentos'] = (self.parse_files(
                self._fetch(entry['url'], 'live_files_' + entry['archive_id'] + '.html'), entry['titulo'])
                if entry['archive_id'] else [])
        rows = self.group_projects(entries)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_entries': len(entries),
                'source_urls': [MUNICIPAL_SOURCE, SOURCE] + [r['url'] for r in entries if r['archive_id']],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current snapshot; do not pretend this is an historical delta.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
