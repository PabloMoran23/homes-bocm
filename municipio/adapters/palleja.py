"""Current public-works snapshot from Pallejà's anonymous municipal notice board."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://palleja.eadministracio.cat/board/'
HOST = 'palleja.eadministracio.cat'


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def _more(soup):
    control = soup.select_one('.more_results')
    if control is None:
        return None  # validated hidden terminal placeholder from parse_ajax
    buttons = control.select('button, a[href]')
    if not buttons:
        return None
    if len(buttons) != 1 or "veure'n mes" not in _norm(buttons[0].get_text(' ', strip=True)) or not buttons[0].get('onclick'):
        raise ValueError('Changed pagination control; refusing truncation')
    return buttons[0]


def parse_ajax(xml, control_id=None):
    """Read Wicket's public load-more response, including its explicit end marker."""
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response' or root.find('redirect') is not None:
        raise ValueError('Unexpected board AJAX response or session redirect')
    fragments = []
    for node in root.findall('component'):
        if node.get('encoding') not in (None, 'wicket1'):
            raise ValueError('Unknown Wicket component encoding')
        text = node.text or ''
        fragments.append(text.replace(']^', ']') if node.get('encoding') else text)
    soup = BeautifulSoup(''.join(fragments), 'html.parser')
    control = soup.select_one('.more_results')
    if control is None:
        # Wicket replaces the exhausted control with its hidden placeholder.
        control = soup.find('div', id=control_id) if control_id else None
        if control is None or control.get('style', '').replace(' ', '').rstrip(';') != 'display:none' or control.find(['button', 'a']):
            raise ValueError('Missing pagination completion control')
    return soup


def parse_documents(soup):
    docs = []
    for tr in soup.select('tr:has(td.class_name)'):
        def field(name):
            cell = tr.select_one('td.class_' + name)
            if cell is None:
                raise ValueError('Changed board table schema')
            return cell.get_text(' ', strip=True)
        a = tr.select_one('td.class_name a[href]')
        if not a:
            raise ValueError('Board row lacks document provenance')
        url = urljoin(SOURCE, a['href'])
        if urlparse(url).hostname != HOST or not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(url).path):
            raise ValueError('Unexpected public document URL')
        docs.append({'titulo': a.get_text(' ', strip=True), 'url': url,
                     'expediente': field('folderCode'), 'procedimiento': field('folderName'),
                     'descripcion': field('description'),
                     'fecha_publicacion': datetime.strptime(field('dateFrom'), '%d/%m/%Y').date().isoformat()})
    return docs


def group_projects(documents):
    groups = {}
    for doc in documents:
        text = _norm(doc['titulo'] + ' ' + doc['descripcion'])
        # Narrow, reviewed coverage: technical physical works, not procurement,
        # environmental licence applications, administrative plans or news.
        if _norm(doc['procedimiento']) != 'actuacions urbanistiques':
            continue
        if re.search(r'licitacio|contractacio|adjudicacio|plec', text):
            continue
        if not re.search(r'memoria tecnica|\bmtv\b|projecte', text):
            continue
        if not re.search(r'circuit|pintura|senyal|enllumenat|vorera|asfalt|urbanitz|claveguer|paviment|coberta', text):
            continue
        code = doc['expediente']
        if not re.fullmatch(r'\d+/\d{4}', code):
            raise ValueError('Physical work lacks municipal expediente')
        groups.setdefault(code, []).append(doc)
    rows = []
    for code, docs in sorted(groups.items()):
        docs = sorted({d['url']: d for d in docs}.values(), key=lambda d: d['url'])
        title = next((d['descripcion'] for d in docs if 'aprovacio inicial' in _norm(d['descripcion'])), docs[0]['descripcion'])
        rows.append({
            'id': 'palleja-proy-' + code.replace('/', '-'),
            'municipio': 'Pallejà', 'codigo_ine': '08157', 'provincia': 'Barcelona',
            'expediente': code, 'titulo': title, 'tipo': 'proyecto_obra_publica',
            'fase': 'aprobación inicial' if 'aprovacio inicial' in _norm(title) else None,
            'fecha': None, 'fecha_publicacion': min(d['fecha_publicacion'] for d in docs),
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'url_documento': docs[0]['url'], 'documentos': docs,
            'source': 'ayuntamiento', 'origen': 'tablon_municipal_obras_publicas',
            'descripcion': '\n'.join(dict.fromkeys(d['descripcion'] for d in docs)),
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'coverage': 'Current board snapshot; publication date is earliest attached notice visible in this snapshot, not agreement date',
        })
    if not rows:
        raise ValueError('No usable physical public works in current board snapshot')
    return rows


class PallejaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.palleja.cat')

    def backfill_proyectos(self, out_jsonl):
        evidence = Path(self.config['evidence_dir']) if self.config.get('evidence_dir') else None
        if evidence:
            evidence.mkdir(parents=True, exist_ok=True)
        captures = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-palleja/1.0'
            def fetch(url, name, ajax=False):
                if urlparse(url).hostname != HOST or urlparse(url).scheme != 'https':
                    raise ValueError('Unexpected source host')
                headers = {'Wicket-Ajax': 'true', 'Wicket-Ajax-BaseURL': 'board/', 'Referer': SOURCE} if ajax else {}
                with session.get(url, headers=headers, timeout=30, stream=True) as response:
                    response.raise_for_status()
                    if urlparse(response.url).hostname != HOST:
                        raise ValueError('Source redirected outside municipal seat')
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > 5_000_000:
                            raise ValueError('Source exceeds 5 MB bound')
                        chunks.append(chunk)
                    content = b''.join(chunks)
                if evidence:
                    (evidence / name).write_bytes(content)
                captures.append({'capture': name, 'sha256': hashlib.sha256(content).hexdigest()})
                return content
            soup = BeautifulSoup(fetch(SOURCE, 'live-board-0.html'), 'html.parser')
            if not soup.select_one('table.AdvertisementBoardListPanel') or not soup.select_one('.more_results'):
                raise ValueError('Missing municipal board inventory or pagination control')
            control_id = soup.select_one('.more_results').get('id')
            documents, seen, pages = [], set(), 0
            while True:
                batch = parse_documents(soup)
                new = [d for d in batch if d['url'] not in seen]
                if not new:
                    raise ValueError('Empty or repeated board page; refusing partial snapshot')
                documents.extend(new)
                seen.update(d['url'] for d in new)
                pages += 1
                button = _more(soup)
                if button is None:
                    break
                if pages >= 100:
                    raise ValueError('Pagination exceeds 100 pages; refusing truncation')
                match = re.search(r"wicketAjaxGet\('([^']+)'", button['onclick'])
                if not match:
                    raise ValueError('Changed load-more action')
                soup = parse_ajax(fetch(urljoin(SOURCE, match[1]), f'live-board-{pages}.xml', ajax=True), control_id)
            rows = group_projects(documents)
            # Stable preview links expose document metadata and the PDF viewer;
            # ephemeral signed PDF URLs are not persisted as canonical provenance.
            for row in rows:
                for doc in row['documentos']:
                    key = doc['url'].rsplit('/', 1)[-1]
                    preview = BeautifulSoup(fetch(doc['url'], f'live-document-{key}.html'), 'html.parser')
                    frame = preview.select_one('iframe[src]')
                    if frame is None or not urlparse(urljoin(doc['url'], frame['src'])).path.startswith('/preview/pdf/'):
                        raise ValueError('Document preview no longer exposes a PDF')
                    if doc['titulo'] not in preview.get_text(' ', strip=True):
                        raise ValueError('Document preview title mismatch')
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'board_documents': len(documents), 'pages': pages,
                'source_urls': [SOURCE] + [d['url'] for r in rows for d in r['documentos']],
                'captures': captures, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # The active board is a complete refresh, not an archive or date cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
