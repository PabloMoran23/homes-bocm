"""Alaior's public initial-approval PG/POD inventory (complete folder snapshot)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://alaior.sedelectronica.es/transparency/4c3d0fe8-f28c-4967-abc0-6c4c0d6c7ba7/'
HOST = 'alaior.sedelectronica.es'
LIMITATIONS = [
    'Partial municipal coverage: only the published initial-approval PG/POD dossier; no claim of current legal validity.',
    'No granted-licence register, public-works inventory or other planning dossiers extracted.',
    'No verified coordinates or vector geometry; publication_ready is false.',
]


def official(url):
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != HOST:
        raise ValueError('Unexpected off-site inventory URL')
    return url


def parse_inventory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.TransparencyListPanel')
    if table is None:
        raise ValueError('Public transparency inventory missing')
    if soup.select_one('.more_results button'):
        raise ValueError('Unexpanded load-more pagination')
    # Counts in the folders are checked again after recursively reading them.
    for a in soup.select('a[href], button'):
        if a.get('rel') == ['next'] or re.search(r'^(següent|siguiente|next|[›»])$', a.get_text(' ', strip=True), re.I):
            if not a.has_attr('disabled') and 'disabled' not in a.get('class', []):
                raise ValueError('Pagination detected; refusing an incomplete snapshot')
    documents, folders = {}, []
    for a in table.select('a.gIconLink'):
        title = a.get_text(' ', strip=True)
        href = a.get('href', '')
        if '/preview-document/' in href:
            link = official(urljoin(url, href))
            documents[link] = {'titulo': title, 'url': link, 'source_url': url}
        elif 'exp' in a.get('class', []):
            count = re.fullmatch(r'(.+?)\s*\(\s*(\d+)\s*\)', title)
            action = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
            if not count or not action:
                raise ValueError('Unrecognized public folder/count')
            folders.append({'titulo': count[1].strip(), 'count': int(count[2]),
                            'action': official(urljoin(url, action[1]))})
        else:
            raise ValueError('Unrecognized inventory entry')
    if not documents and not folders:
        raise ValueError('Empty public inventory')
    return list(documents.values()), folders


def agreement_date(text):
    match = re.search(r"Acord de Ple de data\s+(\d{1,2}) de març de (\d{4}).{0,100}?aprovat inicialment", ' '.join(text.split()), re.I)
    if not match:
        raise ValueError('BOIB initial-approval agreement narrative missing')
    return date(int(match[2]), 3, int(match[1])).isoformat()


def publication_date(title):
    match = re.search(r'BOIB\s+38 de data (\d{2})\.(\d{2})\.(\d{4})', title)
    if not match:
        raise ValueError('BOIB publication date missing')
    return date(int(match[3]), int(match[2]), int(match[1])).isoformat()


def apply_page(soup, xml):
    """Apply only public HTML components; never evaluate source JavaScript."""
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response':
        raise ValueError('Unexpected load-more response')
    components = root.findall('component')
    if not components:
        raise ValueError('Empty load-more response')
    for component in components:
        fragment = BeautifulSoup(component.text or '', 'html.parser')
        element = fragment.find()
        if element is None:
            raise ValueError('Empty load-more component')
        target = soup.find(id=component.get('id'))
        if target is not None:
            target.replace_with(element)
        elif element.name == 'tr':
            soup.select_one('table.TransparencyListPanel tbody').append(element)
        else:
            raise ValueError('Unknown load-more component target')


class AlaiorAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.aj-alaior.org')
        self.source_urls = []
        self._visited = set()

    def _get(self, session, url, headers=None):
        official(url)
        response = session.get(url, headers=headers, timeout=40, stream=True)
        response.raise_for_status()
        official(response.url)
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 10_000_000:
                response.close()
                raise ValueError('Source exceeds 10 MB; refusing truncated response')
            chunks.append(chunk)
        response.close()
        content = b''.join(chunks)
        self.source_urls.append(url)
        capture = self.config.get('capture_dir')
        if capture:
            target = Path(capture)
            target.mkdir(parents=True, exist_ok=True)
            suffix = '.pdf' if content.startswith(b'%PDF') else '.html'
            (target / (hashlib.sha256(url.encode()).hexdigest()[:20] + suffix)).write_bytes(content)
        return response, content

    def _inventory(self, session, url):
        if url in self._visited or len(self._visited) >= 100:
            raise ValueError('Cyclic or unexpectedly large folder inventory')
        self._visited.add(url)
        _, content = self._get(session, url)
        soup = BeautifulSoup(content, 'html.parser')
        pages = set()
        while (button := soup.select_one('.more_results button')) is not None:
            match = re.search(r"wicketAjaxGet\('([^']+)'", button.get('onclick', ''))
            if not match:
                raise ValueError('Unknown load-more action')
            action = official(urljoin(url, match[1]))
            if action in pages or len(pages) >= 100:
                raise ValueError('Repeated or excessive pagination')
            pages.add(action)
            _, xml = self._get(session, action, {'Wicket-Ajax': 'true', 'Referer': url})
            apply_page(soup, xml)
        return parse_inventory(str(soup), url)

    def _folder(self, session, folder, parent):
        response, _ = self._get(session, folder['action'], {'Wicket-Ajax': 'true', 'Referer': parent})
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Public folder navigation did not return Ajax-Location')
        url = official(urljoin(folder['action'], location))
        if not urlparse(url).path.startswith('/transparency/'):
            raise ValueError('Folder navigation left transparency inventory')
        documents, children = self._inventory(session, url)
        for child in children:
            _, items = self._folder(session, child, url)
            documents.extend(items)
        unique = {d['url']: d for d in documents}
        if len(unique) != folder['count']:
            raise ValueError(f"Incomplete folder {folder['titulo']}: expected {folder['count']}, got {len(unique)}")
        return url, list(unique.values())

    def backfill_proyectos(self, out_jsonl):
        self.source_urls, self._visited = [], set()
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-alaior/1.0 (public planning inventory)'
            shared, folders = self._inventory(session, SOURCE)
            expected = {'PLA GENERAL', "PLA D'ORDENACIÓ DETALLADA", 'INFORMES'}
            if {f['titulo'] for f in folders} != expected or len(folders) != 3:
                raise ValueError('PG/POD root inventory changed')
            notices = [d for d in shared if d['titulo'].startswith('BOIB 38 de data')]
            if len(notices) != 1:
                raise ValueError('Expected one Catalan BOIB initial-approval notice')
            notice = notices[0]
            _, preview = self._get(session, notice['url'])
            frame = BeautifulSoup(preview, 'html.parser').select_one('iframe[src]')
            if frame is None:
                raise ValueError('BOIB PDF preview missing')
            pdf_url = official(urljoin(notice['url'], frame['src']))
            _, pdf = self._get(session, pdf_url)
            if not pdf.startswith(b'%PDF'):
                raise ValueError('BOIB preview is not a PDF')
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'notice.pdf'
                path.write_bytes(pdf)
                result = subprocess.run(['pdftotext', '-layout', str(path), '-'], check=True, capture_output=True, timeout=30)
            agreed = agreement_date(result.stdout.decode('utf-8'))
            published = publication_date(notice['titulo'])
            resolved = {f['titulo']: self._folder(session, f, SOURCE) for f in folders}
        _, reports = resolved['INFORMES']
        rows = []
        for name, key in [('PLA GENERAL', 'pg'), ("PLA D'ORDENACIÓ DETALLADA", 'pod')]:
            url, documents = resolved[name]
            rows.append({
                'id': f'alaior-proy-{key}-aprobacion-inicial', 'municipio': 'Alaior', 'codigo_ine': '07002',
                'titulo': name.title() + ' d’Alaior — aprovació inicial',
                'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación inicial',
                'fecha': None, 'fecha_publicacion': published, 'fecha_acuerdo': agreed, 'fecha_aprob': agreed,
                'url': url, 'url_documento': notice['url'], 'source': 'ayuntamiento',
                'origen': 'portal_transparencia_planeamiento',
                'documentos': documents + shared + reports,
                'documentos_instrumento_count': len(documents),
                'date_provenance': {'fecha_publicacion': notice['url'], 'fecha_acuerdo': notice['url']},
                'descripcion': 'Documentación municipal de aprobación inicial; no acredita aprobación definitiva ni vigencia actual.',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'coverage': LIMITATIONS,
            })
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temp = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(set(self.source_urls)), 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        Path(out_jsonl).parent.mkdir(parents=True, exist_ok=True)
        Path(out_jsonl).write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
