"""Constantí's approved urbanisation-project inventory (public Gestiona folders)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://constanti.eadministracio.cat'
SOURCE = BASE + '/transparency/c093c419-6c40-46b3-bb7b-a79e5dc96654/'
LIMITATIONS = [
    'Partial coverage: only the approved urbanisation-project inventory, not all municipal planning or works.',
    'Folder classification supplies approval phase, not an agreement or approval date.',
    'Dates on BOPT/DOGC links are publication dates; document bodies are not parsed.',
    'Document URLs are official preview/register links; no verified geometry or granted-licence register.',
]


def _soup(html):
    return BeautifulSoup(html, 'html.parser')


def _title(a):
    return ' '.join(a.stripped_strings).rsplit(' (', 1)[0].strip()


def _action(element, url):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing public Wicket navigation action')
    return _local(urljoin(url, match[1]))


def _local(url):
    if urlparse(url).scheme != 'https' or urlparse(url).netloc != urlparse(BASE).netloc:
        raise ValueError('Unexpected municipal redirect/action')
    return url


def parse_index(html):
    soup = _soup(html)
    content = soup.select_one('#content')
    if content is None or "Projectes d'urbanització" not in content.get_text(' ', strip=True):
        raise ValueError('Missing urbanisation inventory')
    if content.select_one('.more_results button'):
        raise ValueError('Inventory gained pagination; refusing partial coverage')
    folders = content.select('table a.exp')
    if not folders or any(not _title(a).startswith("Projecte d'urbanització") for a in folders):
        raise ValueError('Unexpected project inventory structure')
    result = []
    for a in folders:
        count = a.select_one('.linkExtraInfo')
        match = re.fullmatch(r'\s*\(\s*(\d+)\s*\)\s*', count.get_text() if count else '')
        if not match:
            raise ValueError('Missing document count')
        result.append((_title(a), int(match[1]), a))
    return result


def parse_documents(html, url):
    soup = _soup(html)
    documents = []
    for a in soup.select('td.class_name a[href]'):
        href = a['href']
        if href == '#' or not href:
            continue
        target = urljoin(url, href)
        if urlparse(target).scheme not in ('https', 'http'):
            raise ValueError('Invalid document link')
        title = a.get_text(' ', strip=True)
        if not title:
            raise ValueError('Untitled document')
        publication = None
        match = re.search(r'\b(BOPT|DOGC) (\d{2})/(\d{2})/(\d{4})\b', title)
        if match:
            publication = date(int(match[4]), int(match[3]), int(match[2])).isoformat()
        documents.append({'titulo': title, 'url': target, 'fecha_publicacion': publication})
    return documents, soup.select_one('.more_results button')


def ajax_fragments(xml):
    root = ElementTree.fromstring(xml)
    if root.tag != 'ajax-response' or root.find('redirect') is not None:
        raise ValueError('Unexpected pagination response')
    components = root.findall('component')
    if not components:
        raise ValueError('Missing pagination components')
    return '\n'.join(c.text or '' for c in components)


def build_record(title, url, documents, expected):
    unique = {d['url']: d for d in documents}
    if len(unique) != expected or expected == 0:
        raise ValueError(f'Document count mismatch: expected {expected}, found {len(unique)}')
    if not any('/preview-document/' in d['url'] for d in unique.values()):
        raise ValueError('Project has no technical documents')
    expediente = re.search(r'\(Exp\. ([^)]+)\)', title)
    return {
        'id': 'constanti-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Constantí', 'codigo_ine': '43047', 'provincia': 'Tarragona',
        'titulo': title, 'tipo': 'proyecto de urbanización',
        'fase': 'aprobación definitiva', 'fase_provenance': 'official approved-project folder classification',
        'expediente': expediente[1] if expediente else None,
        'url': url, 'inventory_url': SOURCE, 'documentos': list(unique.values()),
        'source': 'ayuntamiento', 'origen': 'inventario_proyectos_urbanizacion',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'unavailable', 'coverage': 'approved_urbanisation_project_inventory',
    }


class ConstantiAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _get(self, session, url, ajax=False):
        headers = {'Wicket-Ajax': 'true'} if ajax else {}
        response = session.get(_local(url), headers=headers, timeout=30)
        response.raise_for_status()
        _local(response.url)
        if len(response.content) > 5_000_000:
            raise ValueError('Source response exceeds 5 MB')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            folder = Path(capture_dir)
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20]
            (folder / (name + ('.xml' if ajax else '.html'))).write_bytes(response.content)
        return response

    def backfill_proyectos(self, out_jsonl: Path):
        rows, source_urls = [], [SOURCE]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-constanti/1.0 (public urban planning inventory)'
            index = self._get(session, SOURCE)
            for title, expected, folder in parse_index(index.text):
                navigation = self._get(session, _action(folder, SOURCE), ajax=True)
                location = navigation.headers.get('Ajax-Location')
                if not location:
                    raise ValueError('Missing stable public folder location')
                url = _local(urljoin(SOURCE, location))
                if not re.fullmatch(r'/transparency/[0-9a-f-]{36}/', urlparse(url).path):
                    raise ValueError('Unexpected public folder URL')
                page = self._get(session, url)
                if title not in _soup(page.text).get_text(' ', strip=True):
                    raise ValueError('Folder title mismatch')
                documents, more = parse_documents(page.text, url)
                seen = set()
                while more is not None:
                    action = _action(more, url)
                    if action in seen or len(seen) >= 1000:
                        raise ValueError('Pagination loop or excessive pages; no partial output')
                    seen.add(action)
                    response = self._get(session, action, ajax=True)
                    fragment = ajax_fragments(response.text)
                    extra, more = parse_documents(fragment, url)
                    if not extra:
                        raise ValueError('Pagination made no progress')
                    documents.extend(extra)
                rows.append(build_record(title, url, documents, expected))
                source_urls.append(url)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'live_records': len(rows), 'rows': len(rows),
                'source_urls': source_urls, 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
