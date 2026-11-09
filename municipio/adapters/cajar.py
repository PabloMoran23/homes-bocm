"""Cájar's public works inventory, grouped by municipal document folder."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://cajar.sedelectronica.es'
SOURCE = ROOT + '/transparency'
WORKS = ROOT + '/transparency/99df580b-c3d4-4a61-a5ba-c89c626ea539/'
LIMITATIONS = [
    'Partial coverage: only the public works/infrastructure transparency inventory.',
    'No granted licence register; forms, procurement and unrelated news excluded.',
    'Document creation dates are not agreement, approval or publication dates.',
    'No verified geometry, execution status or current legal validity.',
]


def official_url(url: str) -> str:
    if urlparse(url).scheme != 'https' or urlparse(url).netloc != 'cajar.sedelectronica.es':
        raise ValueError('Unexpected source host or scheme')
    return url


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.select('td.class_name'):
        raise ValueError('Missing transparency inventory table')
    # Fail explicitly rather than silently taking the first page after a redesign.
    for a in soup.select('a[href], a[onclick]'):
        marker = ' '.join([a.get('rel', [''])[0], a.get('title', ''),
                           a.get('aria-label', ''), ' '.join(a.get('class', [])),
                           a.get_text(' ', strip=True)]).lower()
        if re.search(r'\b(next|siguiente|última|last|pagination|paginacion)\b', marker):
            if a.get('href') not in (None, '#') or a.get('onclick'):
                raise ValueError('Pagination detected: extraction requires full traversal')
    entries = []
    for a in soup.select('td.class_name a.gIconLink'):
        label = a.get_text(' ', strip=True)
        count = a.select_one('.linkExtraInfo')
        if count:
            match = re.fullmatch(r'\s*\(\s*(\d+)\s*\)\s*', count.text)
            if not match:
                raise ValueError('Unrecognized inventory count')
            label = label[:label.rfind(count.get_text())].strip()
            action = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
            if not action:
                raise ValueError('Folder has no navigable action')
            entries.append({'title': label, 'count': int(match[1]), 'action': action[1]})
        else:
            url = official_url(urljoin(SOURCE, a.get('href', '')))
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(url).path):
                raise ValueError('Unrecognized document link')
            entries.append({'title': label, 'url': url})
    return entries


def parse_project(html: str, url: str) -> dict | None:
    entries = parse_inventory(html)
    documents = [e for e in entries if 'url' in e]
    projects = [e for e in documents if re.match(r'^PROYECTO\b', e['title'], re.I)]
    if not projects:
        return None
    if len(projects) != 1:
        raise ValueError('Multiple project documents in one folder require explicit grouping')
    project = projects[0]
    return {
        'id': 'cajar-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Cájar', 'codigo_ine': '18036', 'provincia': 'Granada',
        'titulo': project['title'], 'tipo': 'proyecto de obra pública',
        'url': url, 'url_documento': project['url'], 'inventory_url': WORKS,
        'documentos': documents, 'source': 'ayuntamiento',
        'origen': 'transparencia_obras_publicas',
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class CajarAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='cajar', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        captures = self.config.get('evidence_dir')
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-cajar/1.0 (public municipal inventory)'

            def get(url, **kwargs):
                official_url(url)
                response = session.get(url, timeout=40, **kwargs)
                response.raise_for_status()
                official_url(response.url)
                if '?x=' not in response.url:
                    source_urls.append(response.url)
                if captures and 'text/html' in response.headers.get('Content-Type', ''):
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
                    (directory / name).write_text(response.text, encoding='utf-8')
                return response

            seen = set()
            rows = []

            def walk(url, depth=0):
                if url in seen or depth > 8 or len(seen) >= 100:
                    raise ValueError('Cycle or unexpected inventory size/depth')
                seen.add(url)
                response = get(url)
                entries = parse_inventory(response.text)
                project = parse_project(response.text, url)
                if project:
                    rows.append(project)
                total = sum('url' in e for e in entries)
                for entry in entries:
                    if 'action' not in entry or entry['count'] == 0:
                        continue
                    ajax = get(urljoin(url, entry['action']), headers={
                        'Wicket-Ajax': 'true', 'Referer': url,
                        'X-Requested-With': 'XMLHttpRequest',
                    })
                    location = ajax.headers.get('Ajax-Location')
                    if not location:
                        raise ValueError('Missing Wicket folder redirect')
                    target = official_url(urljoin(url, location))
                    if not urlparse(target).path.startswith('/transparency/'):
                        raise ValueError('Unexpected folder target')
                    count = walk(target, depth + 1)
                    if count != entry['count']:
                        raise ValueError('Inventory document count mismatch; possible pagination')
                    total += count
                return total

            document_count = walk(WORKS)
        if not rows:
            raise ValueError('No genuine public works project in live inventory')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'live_records': len(rows), 'documents': document_count,
                'source_urls': list(dict.fromkeys([SOURCE, WORKS] + source_urls)),
                'limitations': LIMITATIONS, 'coverage': 'public_works_transparency_snapshot'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full current snapshot: no timestamp cursor and no invented history.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
