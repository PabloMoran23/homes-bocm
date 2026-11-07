"""Nules: complete snapshot of section 7.4, a partial municipal works inventory."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'nules.sedelectronica.es'
SOURCE = f'https://{HOST}/transparency/78972904-42ef-4ad2-88f7-9508369feada/'
PARENT = f'https://{HOST}/transparency/bf0fb568-5cb9-44b9-9842-d643c2626ea3/'


def official_url(url: str) -> str:
    if urlparse(url).scheme != 'https' or urlparse(url).netloc != HOST:
        raise ValueError(f'Unexpected external URL: {url}')
    return url


def parse_inventory(html: str, url: str, *, require_complete: bool = True) -> list[dict]:
    """Read one fully visible table; pagination is an error, never a cutoff."""
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.TransparencyListPanel')
    if table is None:
        raise ValueError('Missing official transparency inventory table')
    if require_complete and any(re.fullmatch(r"(?:Veure.n més|Ver más|Show more|Load more)",
                        a.get_text(' ', strip=True), re.I)
           for a in soup.select('a,button')):
        raise ValueError('Unconsumed inventory pagination: refusing partial snapshot')
    entries = []
    for a in table.select('a.gIconLink'):
        title = a.get_text(' ', strip=True)
        count_node = a.select_one('.linkExtraInfo')
        if 'exp' in a.get('class', []):
            if not count_node or not re.fullmatch(r'\s*\(\s*\d+\s*\)\s*', count_node.text):
                raise ValueError('Folder has no verifiable document count')
            count = int(re.search(r'\d+', count_node.text)[0])
            title = title[:title.rfind(count_node.get_text(' ', strip=True))].strip()
            match = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
            if not match:
                raise ValueError('Folder has no navigation action')
            entries.append({'title': title, 'count': count,
                            'action': official_url(urljoin(url, match[1]))})
        else:
            target = official_url(urljoin(url, a.get('href', '')))
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(target).path):
                raise ValueError('Unexpected document link')
            entries.append({'title': title, 'url': target,
                            'description': a.get('title', '')})
    if not entries:
        raise ValueError('Empty works inventory')
    return entries


def project_record(title: str, url: str, documents: list[dict]) -> dict:
    if not re.search(r'proje(?:ct|kt)|proyecto', title, re.I) or not documents:
        raise ValueError('Entry is not an identified works project with documents')
    if len({d['url'] for d in documents}) != len(documents):
        raise ValueError('Duplicate documents inside project')
    return {
        'id': 'nules-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Nules', 'codigo_ine': '12082', 'provincia': 'Castellón',
        'titulo': title, 'tipo': 'proyecto de obra pública',
        'url': url, 'inventory_url': SOURCE, 'documentos': documents,
        'source': 'ayuntamiento', 'origen': 'inventario_obras_publicas',
        'coverage': 'seccion_7.4_obras_publicas',
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class NulesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='nules', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'municipio-nules-inventory/1.0'
        self.source_urls: list[str] = []

    def _get(self, url, **kwargs):
        official_url(url)
        response = self.session.get(url, timeout=40, **kwargs)
        response.raise_for_status()
        official_url(response.url)
        if url not in self.source_urls:
            self.source_urls.append(url)
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha256(url.encode()).hexdigest()[:16]
            (directory / f'{key}.html').write_text(response.text, encoding='utf-8')
        return response

    def _folder_url(self, entry, base):
        response = self._get(entry['action'], headers={
            'Wicket-Ajax': 'true', 'Wicket-Ajax-BaseURL': urlparse(base).path.lstrip('/'),
            'Referer': base,
        })
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('No public folder redirect returned by Wicket')
        target = official_url(urljoin(response.url, location))
        if not re.fullmatch(r'/transparency/[0-9a-f-]{36}/', urlparse(target).path):
            raise ValueError('Unexpected folder location')
        return target

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        self.source_urls = []
        parent = self._get(PARENT)
        # The parent carries the recursive document count for the whole section.
        # Only look up section 7.4 here. Other parent categories are out of scope;
        # their pagination is deliberately not traversed or reported as covered.
        sections = parse_inventory(parent.text, parent.url, require_complete=False)
        works = [e for e in sections if e['title'].startswith('7.4.')]
        if len(works) != 1 or 'action' not in works[0]:
            raise ValueError('Missing unique section 7.4')
        source = self._folder_url(works[0], parent.url)
        if source != SOURCE:
            raise ValueError('Works section identity changed; review required')
        response = self._get(source)
        entries = parse_inventory(response.text, source)
        records = []
        for entry in entries:
            if 'action' in entry:
                target = self._folder_url(entry, source)
                response = self._get(target)
                documents = parse_inventory(response.text, target)
                if any('action' in d for d in documents):
                    raise ValueError('Nested works grouping changed; review required')
                if len(documents) != entry['count']:
                    raise ValueError('Incomplete project documents / pending pagination')
                title = entry['title']
            else:
                target = entry['url']
                documents = [entry]
                title = entry['description'] or entry['title']
            records.append(project_record(title, target, documents))
        doc_urls = [d['url'] for r in records for d in r['documentos']]
        if len(doc_urls) != works[0]['count'] or len(set(doc_urls)) != len(doc_urls):
            raise ValueError('Section document count mismatch or overlapping projects')
        if len({r['id'] for r in records}) != len(records):
            raise ValueError('Duplicate project identity')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records),
                          encoding='utf-8')
        return {'count': len(records), 'documents': len(doc_urls),
                'source_urls': [u for u in self.source_urls if '?x=' not in u],
                'coverage': 'complete_section_7.4_only', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
