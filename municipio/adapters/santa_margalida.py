"""Partial snapshot of Santa Margalida's public planning transparency folder.

Document titles identify instruments; preview metadata creation dates are never
interpreted as planning decisions. Unknown documents/pagination fail closed.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://ajsantamargalida.sedelectronica.es'
SOURCE = BASE + '/transparency/42167d6c-2f17-4f87-b936-65b9efc7aa78/'
LIMITATIONS = [
    'Partial coverage: only documents in the municipal planning transparency folder; not a full historical or current-validity register.',
    'No granted-licence inventory extracted. No procurement or news records.',
    'Document creation dates are repository metadata, not publication or agreement dates.',
    'No verified geometry; coordinates remain null. PDF contents are linked, not parsed for decisions.',
]


def _norm(text):
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


def _official(url):
    return urlparse(url).scheme == 'https' and urlparse(url).netloc == urlparse(BASE).netloc


class SantaMargalidaAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE = SOURCE

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.select_one('table.TransparencyListPanel')
        if table is None or 'PLANEJAMENT URBAN' not in soup.get_text(' ', strip=True).upper():
            raise ValueError('Planning inventory missing or replaced by login/error page')
        # Wicket pagers can use AJAX, so checking href alone is insufficient.
        if soup.select('.pagination, .pager, .navigator, [class*="PagingNavigator"]'):
            raise ValueError('Pagination detected; review crawler before accepting partial inventory')
        for a in soup.select('a, button'):
            label = _norm(' '.join([a.get_text(' ', strip=True), a.get('aria-label', ''), a.get('title', '')]))
            if (set(a.get('rel', [])) & {'next', 'last'} or
                    re.search(r'\b(next|last|seguent|seguents|siguiente|ultima|ultim)\b', label) or
                    re.search(r'[?&]page=', a.get('href', ''))):
                raise ValueError('Pagination detected; inventory must not be truncated')
        groups = {}
        seen = {}
        for tr in table.select('tbody tr'):
            cell = tr.select_one('td.class_name')
            if cell is None:
                continue
            anchors = cell.select('a[href]')
            if len(anchors) != 1:
                raise ValueError('Unrecognized inventory row without one document link')
            a = anchors[0]
            title = a.get_text(' ', strip=True)
            url = urljoin(SOURCE, a['href'])
            if not _official(url) or not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(url).path):
                raise ValueError('Unexpected planning document URL')
            if url in seen:
                if seen[url] != title:
                    raise ValueError('Conflicting titles for one document')
                continue
            seen[url] = title
            n = _norm(title)
            if re.fullmatch(r'normes subsidiaries de santa margalida de\s*1986', n):
                key, project_title = 'nnss-1986', title
            elif n.startswith('modificacio de 2013 de nnss 1986: construccio piscines'):
                key, project_title = 'nnss-2013-piscines', title
            elif 'modificacio 2014 2015:' in n and 'zonificacio esportiva sector 7' in n:
                key = 'nnss-2014-2015-sector-7'
                project_title = 'Modificació NNSS 2014–2015: zonificació esportiva sector 7'
            elif re.match(r'edicte [12] modificacio 2016', n) and 'sanitari-assistencial' in n and "aparcaments publics" in n:
                key = 'nnss-2016-2017-sanitari-aparcaments'
                project_title = 'Modificació NNSS 2016–2017: sistema general sanitari-assistencial i aparcaments públics'
            else:
                raise ValueError('Unreviewed planning document; extend grouping rules: ' + title)
            row = groups.setdefault(key, {
                'id': 'santa-margalida-proy-' + key,
                'municipio': 'Santa Margalida', 'codigo_ine': '07055',
                'provincia': 'Illes Balears', 'titulo': project_title,
                'tipo': 'planeamiento_urbanistico', 'fase': None,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'url': SOURCE, 'source': 'ayuntamiento',
                'origen': 'portal_transparencia_planejament', 'documentos': [],
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'limitaciones': list(LIMITATIONS),
            })
            doc = {'titulo': title, 'url': url, 'source_url': SOURCE,
                   'id_origen': url.rsplit('/', 1)[-1]}
            # Only the explicit BOIB label establishes a publication date.
            match = re.search(r'\(BOIB (\d{1,2}) (\d{1,2}) (\d{4})\)', title)
            if match:
                row['fecha_publicacion'] = date(int(match[3]), int(match[2]), int(match[1])).isoformat()
                row['fecha_publicacion_fuente'] = url
            if 'aprovacio inicial' in n:
                doc['fase_documento'] = 'aprobación inicial'
            row['documentos'].append(doc)
        if not groups:
            raise ValueError('Empty planning inventory')
        for row in groups.values():
            row['documentos'].sort(key=lambda d: d['url'])
            row['descripcion'] = '\n'.join(d['titulo'] for d in row['documentos'])
        return sorted(groups.values(), key=lambda r: r['id'])

    @staticmethod
    def parse_preview(html, url):
        soup = BeautifulSoup(html, 'html.parser')
        frame = soup.select_one('iframe[src]')
        if not frame or 'Informació del document' not in soup.get_text(' ', strip=True):
            raise ValueError('Document preview missing public metadata/PDF')
        pdf = urljoin(url, frame['src'])
        if not _official(pdf) or not urlparse(pdf).path.startswith('/preview/pdf/'):
            raise ValueError('Unexpected PDF location')
        return {'url_pdf': pdf, 'formato': 'PDF'}

    def _fetch(self, url):
        response = requests.get(url, timeout=40, stream=True,
                                headers={'User-Agent': 'municipio-santa-margalida/1.0'})
        with response:
            response.raise_for_status()
            if not _official(response.url):
                raise ValueError('Source redirected outside municipal sede')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Source exceeds 4 MB; no partial parse')
                chunks.append(chunk)
            content = b''.join(chunks)
            capture_dir = self.config.get('capture_dir')
            if capture_dir:
                path = Path(capture_dir)
                path.mkdir(parents=True, exist_ok=True)
                name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
                (path / name).write_bytes(content)
            return content.decode(response.encoding or 'utf-8')

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = self.parse_inventory(self._fetch(SOURCE))
        urls = [SOURCE]
        for row in rows:
            for doc in row['documentos']:
                doc.update(self.parse_preview(self._fetch(doc['url']), doc['url']))
                urls.append(doc['url'])
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': urls,
                'limitations': list(LIMITATIONS), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot; never date-filter an inventory with unknown dates.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
