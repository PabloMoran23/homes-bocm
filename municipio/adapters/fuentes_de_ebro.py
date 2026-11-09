"""Current public board snapshot, not a historical licence or procurement register."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://fuentesdeebro.sedelectronica.es/board'
HOST = urlparse(SOURCE).hostname


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn')


class FuentesDeEbroAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.select_one('table.AdvertisementBoardListPanel')
        if table is None:
            raise ValueError('Official board table missing')
        # Wicket pagination is session-dependent: stop rather than emit page one.
        for control in soup.select('a, button, input[type=button]'):
            label = normalized(' '.join([control.get_text(' ', strip=True),
                control.get('title', ''), control.get('aria-label', ''), control.get('value', '')]))
            pagination = any(x in label for x in ('siguiente', 'next', 'ultima pagina', 'last page'))
            pagination |= 'next' in control.get('rel', [])
            pagination |= bool(control.find_parent(class_=re.compile(r'pagin|pager|navigator', re.I)))
            disabled = control.has_attr('disabled') or control.get('aria-disabled') == 'true'
            disabled |= 'disabled' in control.get('class', [])
            if pagination and not disabled and (control.has_attr('href') or control.has_attr('onclick') or control.name == 'button'):
                raise ValueError('Pagination detected; traversal needs review before extraction')
        groups = {}
        seen = 0
        for tr in table.select('tbody tr'):
            cells = tr.select('td')
            if not cells or not tr.get_text(strip=True):
                continue
            seen += 1
            def value(key):
                cell = tr.select_one('td.class_' + key)
                if cell is None:
                    raise ValueError('Board schema changed: ' + key)
                return cell.get_text(' ', strip=True)
            description = value('description')
            text = normalized(description)
            instrument = re.search(r'\b(estudio de detalle|plan especial|plan parcial|plan general|proyecto de (?:obras|urbanizacion|reparcelacion))\b', text)
            # Procurement category alone proves nothing. Require an instrument and
            # an explicit planning/works approval notice, not a call for tenders.
            if not instrument or not re.search(r'\baprobacion (?:inicial|provisional|definitiva)\b', text):
                continue
            if re.search(r'\b(licitacion|adjudicacion|solicitud de licencia|formulario)\b', text):
                continue
            expediente = value('folderCode')
            if not re.fullmatch(r'\d+/\d{4}', expediente):
                raise ValueError('Missing stable expediente identifier')
            publication = datetime.strptime(value('dateFrom'), '%d/%m/%Y').date().isoformat()
            link = tr.select_one('td.class_name a[href]')
            if link is None:
                raise ValueError('Notice has no document link')
            url = urljoin(SOURCE, link['href'])
            if urlparse(url).hostname != HOST or not re.fullmatch(r'/preview-document/[a-f0-9-]{36}', urlparse(url).path):
                raise ValueError('Unexpected document provenance')
            row = groups.setdefault(expediente, {
                'id': 'fuentes-de-ebro-proy-' + expediente.replace('/', '-'),
                'municipio': 'Fuentes de Ebro', 'provincia': 'Zaragoza', 'codigo_ine': '50115',
                'expediente': expediente, 'titulo': description,
                'tipo': 'obra_publica' if instrument[1] == 'proyecto de obras' else 'planeamiento_urbanistico',
                'descripcion': description, 'url': SOURCE, 'source': 'ayuntamiento',
                'origen': 'tablon_sede_electronica', 'fecha_publicacion': publication,
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'documentos': [], 'geometry': None, 'lat': None, 'lon': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            })
            doc = {'titulo': link.get_text(' ', strip=True), 'descripcion': description,
                   'url': url, 'fecha_publicacion': publication, 'procedimiento': value('folderName')}
            if not any(d['url'] == url for d in row['documentos']):
                row['documentos'].append(doc)
            row['fecha_publicacion'] = min(row['fecha_publicacion'], publication)
        if not seen or not groups:
            raise ValueError('No supported instruments in current board; review source')
        return sorted(groups.values(), key=lambda row: row['id'])

    def _fetch(self, session, url, capture_name):
        response = session.get(url, timeout=35)
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Unexpected source redirect')
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture_name).write_bytes(response.content)
        return response

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE]}

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-fuentes-de-ebro/1.0'
            rows = self.parse_inventory(self._fetch(session, SOURCE, 'board.html').text)
            for row in rows:
                for doc in row['documentos']:
                    identifier = doc['url'].rsplit('/', 1)[-1]
                    preview = self._fetch(session, doc['url'], 'preview-' + identifier + '.html')
                    soup = BeautifulSoup(preview.text, 'html.parser')
                    frame = soup.select_one('iframe[src]')
                    if frame is None or 'Informaci' not in soup.get_text():
                        raise ValueError('Document preview missing metadata or PDF')
                    pdf_url = urljoin(doc['url'], frame['src'])
                    if urlparse(pdf_url).hostname != HOST or not urlparse(pdf_url).path.startswith('/preview/pdf/'):
                        raise ValueError('Unexpected PDF provenance')
                    pdf = self._fetch(session, pdf_url, identifier + '.pdf')
                    if not pdf.content.startswith(b'%PDF-'):
                        raise ValueError('Source document is not a PDF')
                    # Session-dependent PDF URL is captured locally; retain stable preview URL.
                    doc['formato'] = 'PDF'
        return self._write(out_jsonl, rows)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
