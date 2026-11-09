"""Sollana's public Gestiona planning inventory (anonymous, complete snapshots)."""
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

BASE = 'https://sollana.sedelectronica.es'
SOURCE = BASE + '/transparency'


def local_url(base, link):
    url = urljoin(base, link)
    if urlparse(url).scheme != 'https' or urlparse(url).netloc != urlparse(BASE).netloc:
        raise ValueError('Unexpected external inventory URL')
    return url


def action_url(base, element):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing supported public Wicket action')
    return local_url(base, match[1])


def parse_listing(html, fragment=False):
    """Only inventory table links, never site navigation or arbitrary scripts."""
    soup = BeautifulSoup(html, 'html.parser')
    table = soup if fragment else soup.select_one('table.TransparencyListPanel')
    if table is None:
        raise ValueError('Planning inventory table missing')
    entries = []
    for a in table.select('a.gIconLink'):
        title = ' '.join(a.get_text(' ', strip=True).split())
        count = a.select_one('.linkExtraInfo')
        if 'exp' in a.get('class', []):
            if not count or not re.fullmatch(r'\s*\(\s*\d+\s*\)\s*', count.get_text()):
                raise ValueError('Folder lacks document count')
            entries.append({'title': title[:title.rfind('(')].strip(),
                            'count': int(re.search(r'\d+', count.get_text())[0]), 'element': a})
        elif re.fullmatch(r'https://sollana\.sedelectronica\.es/preview-document/[0-9a-f-]{36}', a.get('href', '')):
            entries.append({'titulo': title, 'url': a['href']})
        else:
            raise ValueError('Unsupported inventory entry: ' + title)
    more = [b for b in soup.select('button[onclick], a[onclick]')
            if b.get_text(' ', strip=True).lower() in {'mostrar más', 'mostrar mas'}]
    # Fail closed if a different pagination control appears.
    for a in soup.select('a[rel~=next], a.next, button.next'):
        raise ValueError('Unsupported inventory pagination')
    if len(more) > 1:
        raise ValueError('Ambiguous pagination')
    return entries, more[0] if more else None


def ajax_fragment(xml):
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response':
        raise ValueError('Unexpected Wicket pagination response')
    parts = [node.text or '' for node in root.findall('component')]
    if not parts:
        raise ValueError('Pagination has no content components')
    return ''.join(parts)


def make_record(title, url, docs, inventories):
    if not docs:
        raise ValueError('Instrument without documents')
    unique = {d['url']: d for d in docs}
    return {
        'id': 'sollana-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Sollana', 'provincia': 'Valencia', 'codigo_ine': '46233',
        'titulo': title, 'tipo': 'planeamiento_urbanistico',
        'source': 'ayuntamiento', 'origen': 'portal_transparencia_planeamiento',
        'url': url, 'source_urls': sorted(set(inventories)),
        'documentos': list(unique.values()),
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'fase': None, 'descripcion': 'Instrumento identificado en el inventario municipal; '
        'los documentos enlazados se agrupan, sin inferir vigencia ni aprobación de su inclusión.',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No se ha extraído geometría verificada de los documentos',
    }


class SollanaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='sollana', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.session = requests.Session()
        self.source_urls = set()
        self._captures = 0

    def _get(self, url, ajax=False):
        local_url(BASE, url)
        headers = {'User-Agent': self.config.get('user_agent', 'municipio-sollana/1.0')}
        if ajax:
            headers['Wicket-Ajax'] = 'true'
        response = self.session.get(url, headers=headers, timeout=35)
        response.raise_for_status()
        local_url(BASE, response.url)
        if len(response.content) > 5_000_000:
            raise ValueError('Inventory response exceeds reviewed size')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            self._captures += 1
            (path / f'source-{self._captures:03d}.{"xml" if ajax else "html"}').write_bytes(response.content)
        if not ajax:
            self.source_urls.add(response.url)
        return response

    def _folder(self, page_url, element):
        response = self._get(action_url(page_url, element), ajax=True)
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Public folder did not supply canonical Ajax-Location')
        url = local_url(response.url, location)
        if not re.fullmatch(r'/transparency/[0-9a-f-]{36}/', urlparse(url).path):
            raise ValueError('Unexpected folder redirect')
        return url

    def _listing(self, url):
        response = self._get(url)
        entries, more = parse_listing(response.text)
        seen = set()
        while more is not None:
            action = action_url(url, more)
            if action in seen or len(seen) >= 100:
                raise ValueError('Pagination cycle or safety limit; no partial output')
            seen.add(action)
            response = self._get(action, ajax=True)
            added, more = parse_listing(ajax_fragment(response.text), fragment=True)
            if not added:
                raise ValueError('Pagination made no progress')
            entries.extend(added)
        keys = [e.get('url') or e['title'] for e in entries]
        if len(keys) != len(set(keys)):
            raise ValueError('Duplicate entries across inventory pages')
        return entries

    def _child(self, url, prefix):
        matches = [e for e in self._listing(url) if e.get('title', '').startswith(prefix)]
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous planning section ' + prefix)
        entry = matches[0]
        return self._folder(url, entry['element']), entry

    def _documents(self, url, expected, ancestors=()):
        if url in ancestors or len(ancestors) >= 10:
            raise ValueError('Folder cycle or depth limit')
        docs = []
        inventories = [url]
        for entry in self._listing(url):
            if 'url' in entry:
                docs.append({**entry, 'source_url': url})
            else:
                child = self._folder(url, entry['element'])
                nested, sources = self._documents(child, entry['count'], (*ancestors, url))
                docs.extend(nested)
                inventories.extend(sources)
        if len(docs) != expected or len({d['url'] for d in docs}) != len(docs):
            raise ValueError(f'Incomplete inventory at {url}: expected {expected}, found {len(docs)}')
        return docs, inventories

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = set()
        urban, _ = self._child(SOURCE, '7. URBANISME')
        planning, _ = self._child(urban, '7.1.')
        nnss, nnss_entry = self._child(planning, '7.1.1.')
        plans, base_entry = self._child(nnss, '7.1.1.1.')
        docs, sources = self._documents(plans, base_entry['count'])
        # The normative text belongs to the same NNSS, not a separate project.
        regulations, _ = self._child(urban, '7.3.')
        texts = [e for e in self._listing(regulations)
                 if e.get('titulo', '').startswith('7.3.1. Ordenances Normes Subsidiàries')]
        if len(texts) != 1:
            raise ValueError('NNSS normative document missing or ambiguous')
        docs.append({**texts[0], 'source_url': regulations})
        rows = [make_record('Normes Subsidiàries de Planejament Urbanístic de Sollana',
                            plans, docs, [*sources, regulations])]
        planning_documents = base_entry['count']
        for prefix in ('7.1.1.2.', '7.1.1.3.'):
            container, container_entry = self._child(nnss, prefix)
            container_documents = 0
            for entry in self._listing(container):
                if 'element' not in entry:
                    raise ValueError('Instrument grouping changed; review inventory')
                instrument = self._folder(container, entry['element'])
                docs, sources = self._documents(instrument, entry['count'])
                container_documents += len(docs)
                rows.append(make_record(entry['title'], instrument, docs, sources))
            if container_documents != container_entry['count']:
                raise ValueError('Incomplete instrument container; no partial output')
            planning_documents += container_documents
        if planning_documents != nnss_entry['count']:
            raise ValueError('Planning branches changed; no partial output')
        if len(rows) < 2:
            raise ValueError('Planning inventory unexpectedly empty')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(self.source_urls),
                'documents': sum(len(r['documentos']) for r in rows), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
