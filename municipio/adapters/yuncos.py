"""Yuncos: complete traversal of section 7.1, conservative instrument grouping."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://yuncos.sedelectronica.es/transparency/88406f55-4cff-40e9-b00f-eb5d4101f315/'
HOST = 'yuncos.sedelectronica.es'
LIMITATIONS = [
    'Partial municipal coverage: section 7.1 Planeamiento Urbanístico only; not an exhaustive project or licence register.',
    'Only explicitly identified NNSS, PERI Casa-Palacio and sector 18/26 plan documents are grouped. Other cartography and auxiliary documents are inventoried but excluded.',
    'Inventory presence does not establish approval, legal validity or execution. No publication/agreement/approval dates or geometry verified.',
    'Document links are official preview pages, not asserted direct PDF downloads. PDF contents are not parsed.',
]


def official(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != HOST or parsed.port not in (None, 443):
        raise ValueError('Unexpected source URL: ' + url)
    return url


def fragment(text):
    """Read Wicket component HTML as data, never evaluate returned JavaScript."""
    if text.lstrip().startswith('<?xml'):
        root = ET.fromstring(text)
        if root.tag != 'ajax-response' or root.find('redirect') is not None:
            raise ValueError('Unexpected Wicket response')
        text = ''.join(c.text or '' for c in root.findall('component'))
    return BeautifulSoup(text, 'html.parser')


def action(node, base):
    match = re.search(r"wicketAjaxGet\('([^']+)'", node.get('onclick', ''))
    if not match:
        raise ValueError('Missing public folder/pagination action')
    return official(urljoin(base, match[1]))


def entries(text, base):
    soup = fragment(text)
    docs, folders = [], []
    for a in soup.select('td.class_name a.gIconLink'):
        title = a.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            count = re.search(r'\(\s*(\d+)\s*\)\s*$', title)
            if not count:
                raise ValueError('Folder lacks document count')
            folders.append((title[:count.start()].strip(), int(count[1]), action(a, base)))
        elif '/preview-document/' in a.get('href', ''):
            docs.append({'titulo': title, 'url': official(urljoin(base, a['href']))})
        else:
            raise ValueError('Unrecognized inventory entry')
    buttons = [b for b in soup.select('button') if b.get_text(' ', strip=True) == 'Mostrar más']
    if len(buttons) > 1:
        raise ValueError('Ambiguous pagination')
    return docs, folders, action(buttons[0], base) if buttons else None


def group_documents(documents):
    groups = {}
    excluded = []
    for doc in documents:
        title = doc['titulo']
        sector = re.search(r'(?:Sector\s+|S-)(18|26)\b', title, re.I)
        path_sector = re.search(r'P\.P\. Sector (18|26)\b', doc['carpeta'], re.I)
        if path_sector or (sector and re.search(r'Plan Parcial|P\.P\.', title, re.I)):
            number = (path_sector or sector)[1]
            key, name, kind = 'pp-' + number, 'Plan Parcial de Ordenación Sector ' + number, 'plan parcial'
        elif 'NNSS Yuncos' in title:
            key, name, kind = 'nnss', 'Normas Subsidiarias de Yuncos — texto refundido y anexos', 'normas subsidiarias'
        elif 'Plan Especial de Reforma Interior' in title and 'Casa-Palacio' in title:
            key, name, kind = 'peri-casa-palacio', 'Plan Especial de Reforma Interior de la Unidad de Actuación Plaza Casa-Palacio', 'plan especial de reforma interior'
        else:
            excluded.append(doc)
            continue
        if key not in groups:
            groups[key] = {
                'id': 'yuncos-plan-' + key, 'municipio': 'Yuncos', 'provincia': 'Toledo',
                'codigo_ine': '45205', 'titulo': name, 'tipo': kind,
                'url': ROOT, 'inventory_url': ROOT, 'source': 'ayuntamiento',
                'origen': 'inventario_planeamiento', 'documentos': [],
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None, 'lat': None, 'lon': None,
                'geometry': None, 'publication_ready': False,
                'geometry_status': 'unavailable',
                'descripcion': 'Instrumento identificado por los títulos del inventario oficial. Su presencia no acredita vigencia ni aprobación.',
            }
        groups[key]['documentos'].append(doc)
    if not groups:
        raise ValueError('No identifiable planning instruments')
    for row in groups.values():
        row['documentos'].sort(key=lambda d: (d['carpeta'], d['titulo'], d['url']))
        row['url_documento'] = row['documentos'][0]['url']
    return sorted(groups.values(), key=lambda r: r['id']), excluded


class YuncosAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='yuncos', config=None, base_url=''):
        super().__init__(slug, config, base_url or ROOT)

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        capture_dir = Path(captures) if captures else None
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
        source_urls, visited, documents = [], set(), {}
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-yuncos/1.0 (public planning inventory)'

            def fetch(url):
                official(url)
                response = session.get(url, timeout=40, allow_redirects=False)
                # Public Wicket folder actions redirect to canonical UUID URLs.
                for _ in range(5):
                    if response.status_code not in (301, 302, 303, 307, 308):
                        break
                    response = session.get(official(urljoin(response.url, response.headers['Location'])), timeout=40, allow_redirects=False)
                response.raise_for_status()
                if response.is_redirect or not response.content:
                    raise ValueError('Empty response or redirect loop')
                if capture_dir:
                    (capture_dir / f'source-{len(source_urls):03d}.txt').write_text(response.text, encoding='utf-8')
                source_urls.append(response.url)
                return response.text, response.url

            def walk(url, path, expected=None):
                if len(source_urls) > 200:
                    raise ValueError('Traversal safety bound exceeded; no partial output written')
                text, base = fetch(url)
                if base in visited:
                    raise ValueError('Repeated folder/page')
                visited.add(base)
                folder_source = base
                folder_docs, children = {}, []
                while True:
                    docs, folders, more = entries(text, base)
                    for doc in docs:
                        doc['carpeta'] = path
                        doc['inventory_url'] = folder_source
                        folder_docs[doc['url']] = doc
                    children.extend(folders)
                    if not more:
                        break
                    if len(source_urls) > 200 or more in visited:
                        raise ValueError('Pagination cycle or safety bound exceeded')
                    visited.add(more)
                    text, base = fetch(more)
                for title, count, child_url in children:
                    child_docs = walk(child_url, path + '/' + title, count)
                    for doc in child_docs:
                        folder_docs[doc['url']] = doc
                if expected is not None and len(folder_docs) != expected:
                    raise ValueError(f'Incomplete inventory {path}: expected {expected}, got {len(folder_docs)}')
                return list(folder_docs.values())

            # Read advertised recursive counts on every run, rather than assume 52 forever.
            text, base = fetch(ROOT)
            _, folders, more = entries(text, base)
            if more or not folders or 'PLANEAMIENTO' not in fragment(text).get_text():
                raise ValueError('Unexpected planning root inventory')
            for title, count, url in folders:
                for doc in walk(url, title, count):
                    documents[doc['url']] = doc
        rows, excluded = group_documents(list(documents.values()))
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'live_records': len(rows),
                'inventory_documents': len(documents), 'excluded_documents': excluded,
                'source_urls': list(dict.fromkeys([ROOT] + source_urls)),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences; application forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
