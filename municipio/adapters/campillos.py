"""Campillos public noticeboard: grouped extraordinary-action project documents."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://campillos.sedelectronica.es/board'
HOST = 'campillos.sedelectronica.es'


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def parse_rows(html):
    rows = []
    soup = BeautifulSoup(html, 'html.parser')
    for tr in soup.select('tr'):
        a = tr.select_one('td.class_name a[href]')
        if not a:
            continue
        def cell(name):
            td = tr.select_one('td.class_' + name)
            if td is None:
                raise ValueError('Noticeboard columns changed: ' + name)
            return td.get_text(' ', strip=True)
        url = urljoin(SOURCE, a['href'])
        if urlparse(url).hostname != HOST or not urlparse(url).path.startswith('/preview-document/'):
            raise ValueError('Unexpected document provenance')
        rows.append({'titulo': a.get_text(' ', strip=True), 'url': url,
                     'expediente': cell('folderCode'), 'procedimiento': cell('folderName'),
                     'categoria': cell('boardCategory'), 'descripcion': cell('description'),
                     'fecha_publicacion': datetime.strptime(cell('dateFrom'), '%d/%m/%Y').date().isoformat()})
    return rows


def next_action(html):
    soup = BeautifulSoup(html, 'html.parser')
    controls = [x for x in soup.select('button,a') if norm(x.get_text(' ', strip=True)) in
                {'mostrar mas', 'siguiente', 'next'}]
    if not controls:
        return None
    if len(controls) != 1:
        raise ValueError('Ambiguous pagination')
    control = controls[0]
    match = re.search(r"wicketAjaxGet\('([^']+)'", control.get('onclick', ''))
    if not match or not match[1].startswith('?x='):
        raise ValueError('Unsupported pagination; refusing partial extraction')
    return match[1]


def ajax_components(xml):
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response' or root.find('redirect') is not None:
        raise ValueError('Unexpected pagination response')
    components = root.findall('component')
    if not components:
        raise ValueError('Missing pagination components')
    return '\n'.join(c.text or '' for c in components)


def group_projects(rows):
    unique = {r['url']: r for r in rows}
    groups = {}
    for row in unique.values():
        if norm(row['categoria']) == 'urbanismo':
            groups.setdefault(row['expediente'], []).append(row)
    projects = []
    for expediente, docs in groups.items():
        project = next((d for d in docs if re.search(r'proyecto\s+(?:para\s+)?actuacion', norm(d['titulo']))), None)
        if not project:
            continue
        if not re.fullmatch(r'\d+/\d{4}', expediente):
            raise ValueError('Missing project expediente')
        projects.append({'id': 'campillos-proy-' + expediente.replace('/', '-'),
                         'municipio': 'Campillos', 'provincia': 'Málaga', 'codigo_ine': '29032',
                         'expediente': expediente, 'titulo': project['titulo'],
                         'tipo': 'proyecto_actuacion_extraordinaria', 'url': project['url'],
                         'inventory_url': SOURCE, 'source': 'ayuntamiento',
                         'origen': 'tablon_anuncios', 'fecha_publicacion': project['fecha_publicacion'],
                         'fecha_acuerdo': None, 'fecha_aprob': None,
                         'documentos': docs, 'geometry_status': 'unavailable',
                         'publication_ready': False})
    if not projects:
        raise ValueError('No supported genuine project documents on current noticeboard')
    return projects


class CampillosAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, session, url, name, ajax=False):
        if urlparse(url).hostname != HOST:
            raise ValueError('Unexpected source host')
        headers = {'Wicket-Ajax': 'true', 'Wicket-Ajax-BaseURL': 'board', 'Referer': SOURCE} if ajax else {}
        r = session.get(url, timeout=60, headers=headers)
        r.raise_for_status()
        if urlparse(r.url).hostname != HOST or not r.content:
            raise ValueError('Empty or redirected official source')
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_bytes(r.content)
        return r

    def _document_text(self, session, doc):
        identifier = doc['url'].rsplit('/', 1)[-1]
        preview = self._get(session, doc['url'], identifier + '.html')
        frame = BeautifulSoup(preview.content, 'html.parser').select_one('iframe[src]')
        if not frame:
            raise ValueError('Missing public PDF preview')
        pdf_url = urljoin(doc['url'], frame['src'])
        pdf = self._get(session, pdf_url, identifier + '.pdf')
        if not pdf.content.startswith(b'%PDF-'):
            raise ValueError('Expected official PDF')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'document.pdf'
            path.write_bytes(pdf.content)
            result = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                                    check=True, capture_output=True, timeout=60)
        # Stable preview URL is retained; temporary signed iframe URL is not an identifier.
        return ' '.join(result.stdout.decode('utf-8').split())

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-campillos/1.0'
            html = self._get(session, SOURCE, 'board.html').text
            rows = parse_rows(html)
            action = next_action(html)
            seen = set()
            pages = 1
            while action:
                if action in seen or pages >= 100:
                    raise ValueError('Pagination loop/limit; no partial output written')
                seen.add(action)
                response = self._get(session, SOURCE + action, f'board-page-{pages + 1}.xml', ajax=True)
                html = ajax_components(response.text)
                new_rows = parse_rows(html)
                if not new_rows or not any(r['url'] not in {x['url'] for x in rows} for r in new_rows):
                    raise ValueError('Pagination did not advance')
                rows.extend(new_rows)
                # Wicket explicitly replaces the more-results container at each step.
                if not BeautifulSoup(html, 'html.parser').select_one('div.more_results, div[style*="display:none"]'):
                    raise ValueError('Pagination completion cannot be verified')
                action = next_action(html)
                pages += 1
            projects = group_projects(rows)
            for project in projects:
                texts = [(doc, self._document_text(session, doc)) for doc in project['documentos']]
                primary = next(text for doc, text in texts if doc['url'] == project['url'])
                title = re.search(r'(PROYECTO PARA ACTUACIÓN EXTRAORDINARIA.*?)\s*PROMOTOR:', primary, re.I)
                if not title:
                    raise ValueError('Project PDF identity could not be verified')
                project['titulo'] = title[1].strip()
                notices = [text for doc, text in texts if 'anuncio' in norm(doc['titulo'])]
                notice = next((t for t in notices if 'se somete a informacion publica' in norm(t)), None)
                if not notice or f"[Expte. {project['expediente']}]" not in notice:
                    raise ValueError('Project public consultation provenance missing')
                project['fase'] = 'información pública'
                project['descripcion'] = notice[notice.index('En el Ayuntamiento'):notice.index('El proyecto de actuación')].strip()
                # The decree admits the application; it is not project approval or a licence.
                project['date_notes'] = 'fecha_publicacion: tablón municipal; no equivale a publicación BOP, acuerdo de aprobación ni licencia.'
        self._write(out_jsonl, projects)
        return {'status': 'ok', 'rows': len(projects), 'pages': pages,
                'inventory_documents': len({r['url'] for r in rows}),
                'source_urls': [SOURCE] + [d['url'] for p in projects for d in p['documentos']],
                'coverage': 'current_noticeboard_extraordinary_action_projects', 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
