"""Named planning packages in Vilallonga's official transparency inventory.

Wicket callbacks are discovered per session, never persisted as source URLs.
Documents and subfolders are exhausted before any JSONL is replaced.
"""
from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://ayuntamientodevillalonga.sedelectronica.es'
SOURCE = BASE + '/transparency/4ae93831-fe0b-4cee-b3ad-c6942bc90c38/'
PACKAGE = re.compile(r'^(?:Modificaci[oó]|Pla |Plan |Estudi |Proyecto |Projecte )', re.I)
UUID = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'


def official_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != urlparse(BASE).netloc:
        raise ValueError('Unexpected destination outside official municipal sede')
    return url


def callback(element, page_url):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing Wicket callback')
    return official_url(urljoin(page_url, match.group(1)))


def parse_page(html, ajax=False):
    """Return inventory entries and the next load-more control (HTML or XML)."""
    if ajax:
        root = ET.fromstring(html)
        if root.tag != 'ajax-response' or root.find('redirect') is not None:
            raise ValueError('Unexpected pagination response')
        fragments = [node.text or '' for node in root.findall('component')]
        if not fragments:
            raise ValueError('Pagination response contains no components')
        soup = BeautifulSoup(''.join(fragments), 'html.parser')
        scope = soup
    else:
        soup = BeautifulSoup(html, 'html.parser')
        scope = soup.select_one('table.TransparencyListPanel')
        if scope is None:
            raise ValueError('Official inventory table missing')
    entries = []
    for a in scope.select('td a.gIconLink[href]'):
        text = a.get_text(' ', strip=True)
        if not text:
            raise ValueError('Untitled inventory entry')
        count = a.select_one('.linkExtraInfo')
        total = None
        if count:
            match = re.fullmatch(r'\s*\(\s*(\d+)\s*\)\s*', count.get_text())
            if not match:
                raise ValueError('Unrecognized folder count')
            total = int(match.group(1))
            text = text[:text.rfind(count.get_text(' ', strip=True))].strip()
        entries.append({'titulo': text, 'href': a['href'], 'count': total,
                        'onclick': a.get('onclick', '')})
    controls = soup.select('.more_results button, .more_results a[href]')
    if len(controls) > 1:
        raise ValueError('Ambiguous pagination controls')
    if controls and controls[0].get_text(' ', strip=True).lower() not in {'mostrar más', 'mostrar més'}:
        raise ValueError('Unknown pagination control')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'següent'}:
            raise ValueError('Unsupported alternate pagination')
    return entries, controls[0] if controls else None


class VilallongaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, *, ajax=False, referer=None):
        official_url(url)
        headers = {'User-Agent': 'municipio-vilallonga/1.0'}
        if ajax:
            headers.update({'Wicket-Ajax': 'true', 'Referer': referer})
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        official_url(response.url)
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            self._capture_index += 1
            (directory / f'inventory-{self._capture_index:03d}.{"xml" if ajax else "html"}').write_text(
                response.text, encoding='utf-8')
        time.sleep(.15)
        return response

    def _entries(self, session, url):
        entries, more = parse_page(self._fetch(session, url).text)
        all_entries = list(entries)
        pages = 0
        while more is not None:
            target = callback(more, url)
            pages += 1
            if pages > 100:
                raise ValueError('Pagination safety limit; output not accepted')
            response = self._fetch(session, target, ajax=True, referer=url)
            if response.headers.get('Ajax-Location'):
                raise ValueError('Unexpected pagination redirect')
            entries, more = parse_page(response.text, ajax=True)
            old = {(e['href'], e['titulo']) for e in all_entries}
            if not entries or all((e['href'], e['titulo']) in old for e in entries):
                raise ValueError('Pagination made no progress')
            all_entries.extend(entries)
        unique = {}
        for entry in all_entries:
            key = (entry['href'], entry['titulo'])
            unique.setdefault(key, entry)
        return list(unique.values())

    def _folder_url(self, session, entry, parent):
        response = self._fetch(session, callback(entry, parent), ajax=True, referer=parent)
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Folder callback lacks public destination')
        target = official_url(urljoin(parent, location))
        if not re.fullmatch('/transparency/' + UUID + '/', urlparse(target).path):
            raise ValueError('Unexpected folder destination')
        return target

    def _documents(self, session, url, expected, trail, visited):
        if url in visited:
            raise ValueError('Folder cycle or duplicate folder')
        visited.add(url)
        documents = {}
        for entry in self._entries(session, url):
            if entry['href'] == '#':
                child = self._folder_url(session, entry, url)
                docs = self._documents(session, child, entry['count'], trail + [entry['titulo']], visited)
            else:
                target = official_url(urljoin(url, entry['href'])).rstrip('/')
                if not re.fullmatch('/preview-document/' + UUID, urlparse(target).path):
                    raise ValueError('Unexpected non-document link in planning package')
                docs = [{'titulo': entry['titulo'], 'url': target, 'inventory_url': url,
                         'carpetas': trail}]
            for doc in docs:
                documents.setdefault(doc['url'], doc)
        if not documents or (expected is not None and len(documents) != expected):
            raise ValueError(f'Incomplete document coverage at {url}: {len(documents)} != {expected}')
        return list(documents.values())

    @staticmethod
    def _write(out_jsonl, rows):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(output)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        self._capture_index = 0
        rows = []
        visited = set()
        with requests.Session() as session:
            entries = self._entries(session, SOURCE)
            for entry in entries:
                # Individual links here are generic viewers / base-plan documents,
                # not additional named packages. Scope is explicitly partial.
                if entry['href'] != '#':
                    continue
                if not PACKAGE.match(entry['titulo']):
                    raise ValueError('Unrecognized planning folder; review scope')
                url = self._folder_url(session, entry, SOURCE)
                docs = self._documents(session, url, entry['count'], [], visited)
                key = urlparse(url).path.strip('/').split('/')[-1]
                rows.append({'id': 'vilallonga-plan-' + key, 'municipio': 'Vilallonga / Villalonga',
                             'codigo_ine': '46255', 'provincia': 'Valencia',
                             'titulo': entry['titulo'], 'tipo': 'planeamiento_urbanistico',
                             'url': url, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
                             'origen': 'inventario_municipal_planeamiento', 'documentos': docs,
                             'geometry_status': 'unavailable', 'publication_ready': False})
        if not rows:
            raise ValueError('No usable named planning package in official inventory')
        return {**self._write(out_jsonl, rows), 'coverage': 'named_planning_folders_only',
                'source_urls': [SOURCE] + [row['url'] for row in rows],
                'documents': sum(len(row['documentos']) for row in rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
