"""Ayora's public planning inventory, grouped by instrument folder."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://ayora.sedelectronica.es/transparency/88db6e49-debd-458a-8554-540c216cc18b/'
HOST = 'ayora.sedelectronica.es'


def official_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != HOST:
        raise ValueError('Unexpected source host or scheme')
    return url


def callback(element, base):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing public Wicket navigation callback')
    return official_url(urljoin(base, match[1]))


def apply_ajax(soup, xml):
    """Apply returned HTML components only; never execute remote JavaScript."""
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response' or root.find('redirect') is not None:
        raise ValueError('Unexpected pagination response')
    components = root.findall('component')
    if not components:
        raise ValueError('Pagination returned no components')
    for component in components:
        content = component.text or ''
        if component.get('encoding') == 'wicket1':
            content = content.replace(']^', ']')
        elif component.get('encoding'):
            raise ValueError('Unknown Wicket encoding')
        fragment = BeautifulSoup(content, 'html.parser')
        node = fragment.find()
        if node is None:
            raise ValueError('Empty pagination component')
        if node.name == 'tr':
            soup.select_one('table.TransparencyListPanel tbody').append(node)
        else:
            old = soup.find(id=component.get('id'))
            if old is None:
                raise ValueError('Unknown pagination component target')
            old.replace_with(node)
    return soup


def documents(soup, url):
    result = {}
    for a in soup.select('table.TransparencyListPanel a[href*="/preview-document/"]'):
        target = official_url(urljoin(url, a['href']))
        result[target] = {'titulo': a.get_text(' ', strip=True), 'url': target,
                          'descripcion_fuente': a.get('title'), 'inventory_url': url}
    return list(result.values())


def folder_entries(soup):
    entries = []
    for a in soup.select('table.TransparencyListPanel a.exp'):
        title = a.get_text(' ', strip=True)
        count = re.search(r'\(\s*(\d+)\s*\)\s*$', title)
        if not count:
            raise ValueError('Folder lacks declared document count')
        entries.append((a, title[:count.start()].strip(), int(count[1])))
    return entries


def instrument_record(title, url, docs):
    if not re.search(r'\b(PLAN|MODIFICACI[ÓO]N|ESTUDIO|PROYECTO)\b', title, re.I) or not docs:
        raise ValueError('No documented planning instrument')
    return {
        'id': 'ayora-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Ayora', 'codigo_ine': '46044', 'provincia': 'Valencia',
        'titulo': re.sub(r'^\d+(?:\.\d+)*\.?\s*', '', title),
        'tipo': 'instrumento de planeamiento urbanístico',
        'url': url, 'inventory_url': SOURCE, 'documentos': docs,
        'source': 'ayuntamiento', 'origen': 'portal_transparencia_planeamiento',
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'geometry': None, 'lat': None, 'lon': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'Inventario documental 7.1; no acredita vigencia ni concesión de licencia.',
    }


class AyoraAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, session, url, **kwargs):
        official_url(url)
        response = session.get(url, timeout=40, allow_redirects=False, **kwargs)
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError('Unexpected source redirect')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20]
            (directory / (name + '.html')).write_text(response.text, encoding='utf-8')
            with (directory / 'requests.jsonl').open('a', encoding='utf-8') as log:
                log.write(json.dumps({'url': url, 'capture': name + '.html',
                                      'status': response.status_code}, ensure_ascii=False) + '\n')
        return response

    def _ajax(self, session, element, url):
        return self._get(session, callback(element, url), headers={
            'Wicket-Ajax': 'true', 'Wicket-Ajax-BaseURL': urlparse(url).path.lstrip('/'),
            'Referer': url})

    def _page(self, session, url):
        response = self._get(session, url)
        soup = BeautifulSoup(response.text, 'html.parser')
        if not soup.select_one('table.TransparencyListPanel'):
            raise ValueError('Planning inventory missing')
        seen = set()
        while True:
            more = soup.select_one('.more_results button[onclick]')
            if more is None:
                break
            target = callback(more, url)
            if target in seen:
                raise ValueError('Pagination loop; refusing partial inventory')
            seen.add(target)
            if len(seen) > 1000:
                raise ValueError('Pagination safety limit; refusing partial inventory')
            before = len(soup.select('table.TransparencyListPanel a.gIconLink'))
            ajax = self._ajax(session, more, url)
            soup = apply_ajax(soup, ajax.text)
            after = len(soup.select('table.TransparencyListPanel a.gIconLink'))
            if after <= before:
                raise ValueError('Pagination made no progress')
        return soup

    def _folder(self, session, anchor, parent_url):
        ajax = self._ajax(session, anchor, parent_url)
        destination = ajax.headers.get('Ajax-Location')
        if not destination:
            raise ValueError('Missing public folder destination')
        url = official_url(urljoin(ajax.url, destination))
        if not urlparse(url).path.startswith('/transparency/'):
            raise ValueError('Unexpected folder destination')
        return url

    def _collect(self, session, url, seen):
        if url in seen:
            raise ValueError('Cyclic planning folders')
        seen.add(url)
        soup = self._page(session, url)
        docs = documents(soup, url)
        for anchor, _, expected in folder_entries(soup):
            nested = self._collect(session, self._folder(session, anchor, url), seen)
            if len(nested) != expected:
                raise ValueError('Nested document count mismatch')
            docs.extend(nested)
        return list({doc['url']: doc for doc in docs}.values())

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-ayora/1.0 (public planning inventory)'
            soup = self._page(session, SOURCE)
            if '7.1. PLANEAMIENTO URBANÍSTICO' not in soup.get_text(' ', strip=True):
                raise ValueError('Wrong planning inventory')
            rows = []
            for anchor, title, expected in folder_entries(soup):
                url = self._folder(session, anchor, SOURCE)
                docs = self._collect(session, url, set())
                if len(docs) != expected:
                    raise ValueError('Instrument document count mismatch; refusing partial output')
                rows.append(instrument_record(title, url, docs))
        if not rows:
            raise ValueError('No usable planning instruments')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': [SOURCE] + [r['url'] for r in rows], 'coverage': 'section_7.1_only',
                'unassigned_documents': len(documents(soup, SOURCE)), 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
