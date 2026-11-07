"""Cubelles' current municipal project inventory (partial municipal coverage)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.cubelles.cat/ajuntament/urbanisme/projectes'
HOST = 'www.cubelles.cat'


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split()) if node else ''


def _official(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != HOST:
        raise ValueError(f'Unexpected non-municipal URL: {url}')
    return url


def parse_inventory(html: str, url: str = SOURCE):
    """Return all dated inventory entries and all pagination destinations."""
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#readspeakerPage')
    if not content or _text(content.select_one('h1')) != 'Projectes':
        raise ValueError('Missing Cubelles project inventory')
    entries = {}
    for item in content.select('ul.articlelist > li.article-item'):
        anchor = item.select_one('a[href]')
        if not anchor:
            raise ValueError('Inventory item without detail link')
        target = _official(urljoin(url, anchor['href']))
        title = _text(anchor)
        if not urlparse(target).path.startswith(urlparse(SOURCE).path + '/'):
            raise ValueError('Unexpected project detail path')
        # Fail on changed inventory semantics rather than emit announcements/forms.
        if not title.startswith(('Projecte constructiu ', "Projecte d'urbanització ")):
            raise ValueError(f'Unreviewed inventory item type: {title}')
        raw_date = _text(item.select_one('.date'))
        publication = datetime.strptime(raw_date, '%d/%m/%Y').date().isoformat() if raw_date else None
        entry = {'url': target, 'titulo': title, 'fecha_publicacion': publication,
                 'inventory_url': url}
        if target in entries and entries[target] != entry:
            raise ValueError('Conflicting project entries')
        entries[target] = entry
    if not entries:
        raise ValueError('Empty or changed project inventory')
    pages = set()
    for anchor in content.select('.pager a[href], .pagination a[href], a[rel~=next]'):
        if anchor['href'].startswith('#'):
            raise ValueError('Unsupported client-side pagination')
        target = _official(urljoin(url, anchor['href']))
        if urlparse(target).path.rstrip('/') != urlparse(SOURCE).path:
            raise ValueError('Unexpected pagination destination')
        pages.add(target)
    for control in content.select('.pager button, .pager select, .pagination button, .pagination select'):
        raise ValueError('Unsupported pagination control')
    return list(entries.values()), sorted(pages)


def parse_project(html: str, entry: dict):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#readspeakerPage .containerArticle')
    title = _text(content.select_one('h1')) if content else ''
    if title != entry['titulo']:
        raise ValueError('Project detail does not match inventory title')
    description = _text(content.select_one('.ddbbtext'))
    documents = {}
    for anchor in soup.select('#page-documents .documents a[href]'):
        target = _official(urljoin(entry['url'], anchor['href']))
        if not urlparse(target).path.lower().endswith('.pdf'):
            raise ValueError('Unreviewed document format')
        label = anchor.select_one('.txt')
        if not label:
            raise ValueError('Missing document label')
        label = BeautifulSoup(str(label), 'html.parser')
        author = _text(label.select_one('.author')) or None
        for extra in label.select('.author, .file-size'):
            extra.decompose()
        documents[target] = {'titulo': _text(label), 'url': target,
                             'publisher': author, 'source_url': entry['url']}
    technical = [d for d in documents.values() if d['titulo'].startswith('Projecte')]
    if not technical:
        raise ValueError('No technical project document; notices alone are insufficient')
    phase = ('aprobación inicial' if "Informació pública de l'aprovació inicial del Projecte" in description else None)
    return {
        **entry,
        'id': 'cubelles-proy-' + hashlib.sha256(entry['url'].encode()).hexdigest()[:16],
        'municipio': 'Cubelles', 'provincia': 'Barcelona', 'codigo_ine': '08074',
        'tipo': 'proyecto de obra o urbanización', 'fase': phase,
        'fecha': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'fecha_publicacion_source': entry['inventory_url'],
        'descripcion': description or None,
        'fase_source': entry['url'] if phase else None,
        'url_documento': technical[0]['url'], 'documentos': list(documents.values()),
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_projectes',
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class CubellesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='cubelles', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def _fetch(self, url):
        _official(url)
        with requests.get(url, timeout=45, stream=True,
                          headers={'User-Agent': 'municipio-cubelles/1.0'}) as response:
            response.raise_for_status()
            _official(response.url)
            if response.url != url:
                raise ValueError('Unexpected source redirect')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Source exceeds HTML size limit')
            html = data.decode('utf-8')
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (directory / name).write_text(html, encoding='utf-8')
        return html

    def backfill_proyectos(self, out_jsonl: Path):
        pending, visited, entries = [SOURCE], [], {}
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Pagination safety limit exceeded; no partial output written')
            rows, pages = parse_inventory(self._fetch(url), url)
            visited.append(url)
            for row in rows:
                old = entries.get(row['url'])
                if old and any(old[k] != row[k] for k in ('titulo', 'fecha_publicacion')):
                    raise ValueError('Conflicting entries across inventory pages')
                entries.setdefault(row['url'], row)
            pending.extend(page for page in pages if page not in visited)
        records = [parse_project(self._fetch(row['url']), row) for row in entries.values()]
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in records), encoding='utf-8')
        return {'status': 'ok', 'rows': len(records), 'source_urls': visited + list(entries),
                'coverage': 'current municipal Projectes inventory; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
