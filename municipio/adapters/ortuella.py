"""Ortuella's public Urbanismo library: grouped planning instruments, no licences."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.ortuella.eus'
AREA = '/es-ES/Servicios/Urbanismo/'
INVENTORY = BASE + AREA + "_api/web/lists/getbytitle('Páginas')/items?$select=Id,Title,FileRef,Modified&$top=100"
# Deliberate coverage: published instrument libraries, not every Urbanismo page.
INSTRUMENTS = {
    'PGOU': 'PGOU',
    'Catálogo de patrimonio': 'catalogo_patrimonio',
    'Plan de acción del paisaje de Ortuella': 'plan_accion_paisaje',
}


def official(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'www.ortuella.eus':
        raise ValueError('Source URL outside official municipal host')
    return url


def parse_inventory(payload):
    """Return one OData page and its continuation, never ignore next links."""
    if not isinstance(payload.get('value'), list):
        raise ValueError('Expected public SharePoint OData inventory')
    rows = payload['value']
    for row in rows:
        if not all(k in row for k in ('Id', 'Title', 'FileRef', 'Modified')):
            raise ValueError('Urbanismo inventory schema changed')
        if not row['FileRef'].startswith(AREA + 'Paginas/'):
            raise ValueError('Unexpected inventory page path')
    return rows, payload.get('odata.nextLink') or payload.get('@odata.nextLink')


def parse_page(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#centerColumn, #ProcedureContent, #MainContent .CenterZone')
    if content is None or not content.get_text(strip=True):
        raise ValueError('Missing municipal instrument content: ' + url)
    docs, children = {}, set()
    for a in content.select('a[href]'):
        label = a.get_text(' ', strip=True)
        href = urljoin(url, a['href'])
        if (a.get('rel') and 'next' in a['rel']) or label.lower() in {'siguiente', 'next', 'hurrengoa', '›', '»'}:
            raise ValueError('Uncovered HTML pagination: ' + url)
        parts = urlsplit(href)
        if parts.netloc != 'www.ortuella.eus':
            continue
        href = official(href)
        if unquote(parts.path).lower().endswith('.pdf'):
            # Encode spaces/accents consistently; preserve case-sensitive file paths.
            href = quote(unquote(href), safe=':/?=&%+#')
            body = a.find_parent(class_='ms-WPBody')
            header = body.find_previous_sibling(class_='ms-WPHeader') if body else None
            docs[href] = {'titulo': label, 'url': href, 'source_page': url,
                          'seccion': header.get_text(' ', strip=True) if header else None}
        elif parts.path.startswith(AREA + 'Paginas/') and parts.path.lower().endswith('.aspx'):
            children.add(href.split('#')[0])
    return content.get_text(' ', strip=True), list(docs.values()), children


class OrtuellaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='ortuella', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []

    def _fetch(self, url, json_response=False):
        official(url)
        response = requests.get(url, timeout=35, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-ortuella/1.0'),
            'Accept': 'application/json' if json_response else 'text/html',
        })
        response.raise_for_status()
        official(response.url)
        self.source_urls.append(response.url)
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20]
            (directory / (name + ('.json' if json_response else '.html'))).write_bytes(response.content)
        return response.json() if json_response else response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        url, seen, inventory = INVENTORY, set(), {}
        while url:
            url = official(urljoin(INVENTORY, url))
            if url in seen or len(seen) >= 100:
                raise ValueError('OData pagination cycle or excessive pages; output not written')
            seen.add(url)
            items, url = parse_inventory(self._fetch(url, json_response=True))
            for item in items:
                key = item['FileRef']
                if key in inventory and inventory[key] != item:
                    raise ValueError('Conflicting duplicate inventory entry')
                inventory[key] = item
        selected = [x for x in inventory.values() if x['Title'] in INSTRUMENTS]
        if {x['Title'] for x in selected} != set(INSTRUMENTS):
            raise ValueError('Reviewed planning libraries missing; review source changes')
        cache, rows = {}, []
        for item in sorted(selected, key=lambda x: x['Id']):
            root = BASE + item['FileRef']
            pending, visited, docs, descriptions = [root], set(), {}, {}
            while pending:
                page = pending.pop()
                if page in visited:
                    continue
                if len(visited) >= 100:
                    raise ValueError('Instrument page graph exceeds reviewed bound')
                visited.add(page)
                if urlsplit(page).path not in inventory:
                    raise ValueError('Linked instrument page absent from full inventory')
                if page not in cache:
                    cache[page] = parse_page(self._fetch(page), page)
                text, attachments, children = cache[page]
                descriptions[page] = text
                for doc in attachments:
                    entry = docs.setdefault(doc['url'], {**doc, 'source_pages': []})
                    if page not in entry['source_pages']:
                        entry['source_pages'].append(page)
                pending.extend(sorted(children - visited))
            if not docs:
                raise ValueError('Instrument has no linked source documents')
            if item['Title'] == 'PGOU' and not any('/aprobacion_inicial_textos/' in u for u in docs):
                raise ValueError('PGOU initial-stage documentation missing')
            rows.append({
                'id': 'ortuella-proy-' + str(item['Id']),
                'municipio': 'Ortuella', 'codigo_ine': '48083', 'provincia': 'Bizkaia',
                'titulo': 'Plan General de Ordenación Urbana de Ortuella (revisión)' if item['Title'] == 'PGOU' else item['Title'],
                'tipo': INSTRUMENTS[item['Title']],
                'fase': 'documentación de aprobación inicial' if item['Title'] == 'PGOU' else None,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'source_modified_at': item['Modified'],
                'url': root, 'source': 'ayuntamiento', 'origen': 'biblioteca_municipal_urbanismo',
                'descripcion': descriptions[root],
                'documentos': sorted(docs.values(), key=lambda d: d['url']),
                'source_pages': sorted(visited), 'inventory_url': INVENTORY,
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'coverage': 'Bibliotecas municipales seleccionadas; no registro exhaustivo de expedientes ni licencias. Documentos históricos conservados; sin fecha de acuerdo verificada.',
            })
        return {**self._write(out_jsonl, rows), 'source_urls': sorted(set(self.source_urls)), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full replacement snapshot; Modified is not a legal event cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
