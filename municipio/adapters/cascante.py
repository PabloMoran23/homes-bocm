"""Cascante: planning instruments identified in the current public notice board.

The board is a snapshot, not a historical register. Document creation and board
publication dates do not establish agreement dates. No licence inference.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://cascante.sedelectronica.es/board'
HOST = 'cascante.sedelectronica.es'
LIMITATIONS = [
    'Only current board notices for planning instruments; no historical coverage.',
    'Publication dates refer to the municipal board, not BON publication or agreement dates.',
    'PDF notices are linked and verified; technical plan contents are not parsed.',
    'No granted licences, verified geometry or coordinates are supplied.',
    'New pagination causes an explicit failure pending crawler review.',
]


def _norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def _official(url, path):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != HOST or not parsed.path.startswith(path):
        raise ValueError('Unexpected source document URL: ' + url)
    return url


class CascanteAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        # Reviewed board has no paginator. Refuse newly introduced pagination,
        # including Wicket AJAX-only links, instead of returning a first page.
        for node in soup.select('a, button, input, .pagination, .paginator, .paging, .navigator, [class*="Paging"], [class*="Paginator"]'):
            label = _norm(' '.join([node.get_text(' ', strip=True), node.get('title', ''),
                                    node.get('aria-label', ''), node.get('value', '')]))
            classes = ' '.join(node.get('class', [])).lower()
            paging = any(word in classes for word in ('pagination', 'paginator', 'paging', 'navigator'))
            paging = paging or bool(set(node.get('rel', [])) & {'next', 'last'})
            paging = paging or bool(re.search(r'\b(siguiente|next|ultima pagina|pagina siguiente)\b', label))
            if paging and node.get('aria-disabled') != 'true' and not node.has_attr('disabled') and 'disabled' not in classes:
                if node.get('href') or node.get('onclick') or node.name in {'button', 'input'} or node.select('a, button, input'):
                    raise ValueError('Unreviewed board pagination; refusing partial extraction')
        table = soup.select_one('table.AdvertisementBoardListPanel')
        if table is None or 'Fecha de Publicación' not in table.get_text(' ', strip=True):
            raise ValueError('Public board table missing or changed')
        groups = {}
        for tr in table.select('tbody tr'):
            if not tr.select_one('td.class_folderName'):
                continue  # Empty Wicket placeholder rows.
            def cell(name):
                node = tr.select_one('td.class_' + name)
                if node is None:
                    raise ValueError('Incomplete board row: ' + name)
                return node.get_text(' ', strip=True)
            procedure = cell('folderName')
            title = cell('description')
            normal = _norm(title)
            if _norm(procedure) not in {'planeamiento general', 'actuaciones urbanisticas'}:
                continue
            stage = re.search(r'\baprobacion (inicial|provisional|definitiva)\b', normal)
            instrument = re.search(r'\b(plan general|plan municipal|plan parcial|plan especial|estudio de detalle|reparcelacion)\b', normal)
            if not stage or not instrument:
                continue
            reference = cell('folderCode')
            if not re.fullmatch(r'\d+/\d{4}', reference):
                raise ValueError('Planning notice lacks municipal expediente')
            published = datetime.strptime(cell('dateFrom'), '%d/%m/%Y').date().isoformat()
            links = tr.select('td.class_name a[href]')
            if len(links) != 1:
                raise ValueError('Planning notice lacks unambiguous document')
            url = _official(urljoin(SOURCE, links[0]['href']), '/preview-document/')
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(url).path):
                raise ValueError('Unexpected document identity')
            row = groups.setdefault(reference, {
                'id': 'cascante-proy-' + reference.replace('/', '-'),
                'municipio': 'Cascante', 'codigo_ine': '31068', 'provincia': 'Navarra',
                'expediente': reference, 'titulo': title,
                'tipo': 'instrumento_urbanistico', 'source': 'ayuntamiento',
                'origen': 'tablon_municipal_vigente', 'url': SOURCE,
                'fecha': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'coverage': 'partial_current_notice_board',
            })
            doc = {'titulo': links[0].get_text(' ', strip=True), 'descripcion': title,
                   'url': url, 'fecha_publicacion': published,
                   'fase': 'aprobación ' + stage[1], 'procedimiento': procedure}
            if doc not in row['documentos']:
                row['documentos'].append(doc)
        if not groups:
            raise ValueError('No supported planning instruments; review current board')
        for row in groups.values():
            row['documentos'].sort(key=lambda d: (d['fecha_publicacion'], d['url']))
            row['fecha_publicacion'] = row['documentos'][0]['fecha_publicacion']
            stages = {doc['fase'] for doc in row['documentos']}
            row['fase'] = next(iter(stages)) if len(stages) == 1 else None
            row['descripcion'] = '\n'.join(dict.fromkeys(d['descripcion'] for d in row['documentos']))
        return sorted(groups.values(), key=lambda r: r['id'])

    @staticmethod
    def parse_preview(html, url):
        soup = BeautifulSoup(html, 'html.parser')
        frames = soup.select('iframe[src]')
        if len(frames) != 1:
            raise ValueError('Planning document preview missing PDF')
        return _official(urljoin(url, frames[0]['src']), '/preview/pdf/')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('capture_dir')
        sources = [SOURCE]
        def fetch(session, url, label, pdf=False, referer=None):
            response = session.get(url, timeout=35, headers={'Referer': referer} if referer else {})
            response.raise_for_status()
            _official(response.url, '/')
            body = response.content
            if len(body) > 20_000_000:
                raise ValueError('Source exceeds reviewed response size')
            if pdf and not body.startswith(b'%PDF-'):
                raise ValueError('Document response is not a PDF')
            if captures:
                directory = Path(captures)
                directory.mkdir(parents=True, exist_ok=True)
                (directory / label).write_bytes(body)
            return response
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-cascante/1.0 (public planning inventory)'
            rows = self.parse_inventory(fetch(session, SOURCE, 'board.html').text)
            verified = {}
            for row in rows:
                for doc in row['documentos']:
                    url = doc['url']
                    if url not in verified:
                        identity = url.rsplit('/', 1)[-1]
                        preview = fetch(session, url, identity + '.html')
                        pdf_url = self.parse_preview(preview.text, url)
                        # PDF paths are session-bound; retain the stable preview URL
                        # as provenance and the verified content hash, not the token.
                        pdf = fetch(session, pdf_url, identity + '.pdf', pdf=True, referer=url)
                        verified[url] = hashlib.sha256(pdf.content).hexdigest()
                        sources.append(url)
                    doc['sha256'] = verified[url]
                    doc['formato'] = 'application/pdf'
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Refresh complete visible snapshot; disappearance is not a revocation.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
