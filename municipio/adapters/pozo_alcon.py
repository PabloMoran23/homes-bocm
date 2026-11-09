"""Current public project notices on Pozo Alcón's official electronic board."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://pozoalcon.sedelectronica.es/board'
HOST = 'pozoalcon.sedelectronica.es'


def more_button(soup):
    buttons = [b for b in soup.select('.more_results button')
               if 'Mostrar más' in b.get_text(' ', strip=True)]
    if len(buttons) > 1:
        raise ValueError('Ambiguous board pagination')
    return buttons[0] if buttons else None


def apply_ajax(soup, payload, pagination_id):
    """Apply Wicket row additions and component replacements, without running JS."""
    root = ET.fromstring(payload)
    if root.tag != 'ajax-response' or root.find('redirect') is not None:
        raise ValueError('Unexpected Wicket response')
    components = root.findall('component')
    if not components:
        raise ValueError('Pagination returned no components')
    for component in components:
        fragment = BeautifulSoup(component.text or '', 'html.parser')
        old = soup.find(id=component.get('id'))
        if old is not None:
            old.replace_with(fragment)
        else:
            rows = fragment.find_all('tr', recursive=False)
            body = soup.select_one('table tbody')
            if not rows or body is None:
                raise ValueError('Unrecognized board pagination component')
            for row in rows:
                body.append(row)
    if soup.find(id=pagination_id) is None:
        raise ValueError('Pagination control disappeared without terminal component')
    return soup


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.select('td.class_description'):
        raise ValueError('Board table missing; refusing empty/login page')
    grouped = {}
    for row in soup.select('tr'):
        description = row.select_one('td.class_description')
        if description is None:
            continue
        text = description.get_text(' ', strip=True)
        # Require a named technical instrument explicitly in public consultation.
        # Tender notices, application forms, unrelated notices and news are excluded.
        match = re.fullmatch(
            r'Información pública del (Proyecto de Ejecución de la obra\s+.+)',
            text, re.I)
        if not match or re.search(r'licitaci[oó]n|contrataci[oó]n', text, re.I):
            continue
        code = row.select_one('td.class_folderCode')
        published = row.select_one('td.class_dateFrom')
        links = row.select('td.class_name a[href]')
        if code is None or published is None or not links:
            raise ValueError('Project notice lacks provenance')
        expediente = code.get_text(' ', strip=True)
        if not re.fullmatch(r'\d+/\d{4}', expediente):
            raise ValueError('Unexpected expediente')
        publication = datetime.strptime(published.get_text(' ', strip=True), '%d/%m/%Y').date().isoformat()
        title = match[1]
        documents = []
        for a in links:
            target = urljoin(SOURCE, a['href'])
            parsed = urlparse(target)
            if parsed.scheme != 'https' or parsed.hostname != HOST or not re.fullmatch(
                    r'/preview-document/[0-9a-f-]{36}', parsed.path):
                raise ValueError('Unexpected project document URL')
            document = {'titulo': a.get_text(' ', strip=True), 'url': target,
                        'fecha_publicacion': publication, 'inventory_url': SOURCE}
            if document not in documents:
                documents.append(document)
        # One municipal expediente may have several documents for this instrument.
        identity = expediente + ':' + ' '.join(title.casefold().split())
        if identity not in grouped:
            grouped[identity] = {
                'id': 'pozo-alcon-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
                'municipio': 'Pozo Alcón', 'provincia': 'Jaén', 'codigo_ine': '23070',
                'titulo': title, 'tipo': 'proyecto de obra pública',
                'fase': 'información pública', 'expediente': expediente,
                'descripcion': text, 'fecha_publicacion': publication,
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': documents[0]['url'], 'inventory_url': SOURCE,
                'source': 'ayuntamiento', 'origen': 'tablon_municipal',
                'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            }
        record = grouped[identity]
        record['fecha_publicacion'] = min(record['fecha_publicacion'], publication)
        for document in documents:
            if document not in record['documentos']:
                record['documentos'].append(document)
    return list(grouped.values())


class PozoAlconAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='pozo-alcon', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('evidence_dir')
        def capture(name, content):
            if captures:
                folder = Path(captures)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / name).write_text(content, encoding='utf-8')

        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-pozo-alcon/1.0'
            response = session.get(SOURCE, timeout=40)
            response.raise_for_status()
            if response.url != SOURCE:
                raise ValueError('Unexpected board redirect')
            capture('board-live.html', response.text)
            soup = BeautifulSoup(response.text, 'html.parser')
            if not soup.select('td.class_description'):
                raise ValueError('Missing board inventory')
            pages = 1
            while (button := more_button(soup)) is not None:
                if pages >= 100:
                    raise ValueError('Pagination safety limit reached; snapshot incomplete')
                parent = button.find_parent(class_='more_results')
                if parent is None or not parent.get('id'):
                    raise ValueError('Missing pagination component')
                match = re.search(r"wicketAjaxGet\('([^']+)'", button.get('onclick', ''))
                if not match or not match[1].startswith('?x='):
                    raise ValueError('Unsupported pagination action')
                before = len(soup.select('td.class_description'))
                response = session.get(urljoin(SOURCE, match[1]), timeout=40, headers={
                    'Wicket-Ajax': 'true', 'Wicket-Ajax-BaseURL': 'board', 'Referer': SOURCE})
                response.raise_for_status()
                if urlparse(response.url).hostname != HOST:
                    raise ValueError('Unexpected pagination redirect')
                capture(f'board-page-{pages + 1}.xml', response.text)
                soup = apply_ajax(soup, response.text, parent['id'])
                pages += 1
                if len(soup.select('td.class_description')) <= before:
                    raise ValueError('Pagination made no progress')
            capture('board-complete.html', str(soup))
            records = parse_inventory(str(soup))
            if not records:
                raise ValueError('No usable public project notices in current board')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
        return {'count': len(records), 'written': len(records), 'pages': pages,
                'board_rows': len(soup.select('td.class_description')),
                'source_urls': [SOURCE], 'coverage': 'current_board_public_consultation_works',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Notices expire; refresh the entire currently visible board, not an archive.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
