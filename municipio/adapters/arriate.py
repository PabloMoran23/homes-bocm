"""Arriate's public Gestiona inventory: grouped instruments, no inferred approvals."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'arriate.sedelectronica.es'
SOURCE = f'https://{HOST}/transparency/6515c79d-5996-4dea-9e23-0170fb71a39f/'
LIMITATIONS = [
    'Partial current documentary inventory: UE-6, PMVS 2019-2023 and EDAR/colectores only; not a complete history or a register of granted licences.',
    'Documents are grouped by municipal folder, including nested folders; loose documents in the generic planning folder are not assigned to UE-6.',
    'No approval, agreement or publication dates inferred from filenames, plan periods or document creation dates; current validity and execution are unverified.',
    'No verified geometry; publication_ready=false. Normative compilation and private FTTH deployment are outside this extraction scope.',
]


def official(url):
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != HOST:
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def callback(element, base):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing Gestiona navigation callback')
    return official(urljoin(base, match[1]))


def prepare(html, base):
    soup = BeautifulSoup(html, 'html.parser')
    for element in soup.select('[onclick]'):
        if 'wicketAjaxGet(' in element['onclick']:
            element['data-callback'] = callback(element, base)
    return soup


def apply_ajax(soup, xml, base):
    """Apply Wicket component replacements and appended rows without executing JS."""
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response':
        raise ValueError('Unexpected pagination response')
    changed = False
    for component in root.findall('component'):
        if component.get('encoding') not in (None, 'wicket1'):
            raise ValueError('Unsupported Wicket component encoding')
        # Wicket's wicket1 escaping encodes ] as ]^ (for CDATA transport).
        markup = component.text or ''
        if component.get('encoding') == 'wicket1':
            markup = markup.replace(']^', ']')
        fragment = prepare(markup, base)
        element = fragment.find()
        if element is None:
            continue
        existing = soup.find(id=component.get('id'))
        if existing is not None:
            existing.replace_with(element)
            changed = True
        elif element.name == 'tr':
            body = soup.select_one('.TransparencyListPanel tbody')
            if body is None:
                raise ValueError('Missing inventory body')
            body.append(element)
            changed = True
    if not changed:
        raise ValueError('Pagination did not change inventory')


def parse_inventory(soup):
    table = soup.select_one('.TransparencyListPanel')
    if table is None:
        raise ValueError('Missing official transparency inventory')
    docs, folders = {}, []
    for anchor in table.select('a[href]'):
        title = anchor.get_text(' ', strip=True)
        if '/preview-document/' in anchor['href']:
            url = official(urljoin(SOURCE, anchor['href']))
            docs[url] = {'titulo': title, 'url': url}
        elif 'exp' in anchor.get('class', []):
            match = re.search(r'\(\s*(\d+)\s*\)\s*$', title)
            if not match:
                raise ValueError('Folder lacks document count')
            folders.append({'titulo': title[:match.start()].strip(),
                            'count': int(match[1]), 'callback': anchor['data-callback']})
    return list(docs.values()), folders


def more_button(soup):
    buttons = [b for b in soup.select('button[onclick],a[onclick]')
               if b.get_text(' ', strip=True).lower() in ('mostrar más', 'siguiente', 'next')
               and not any('display:none' in p.get('style', '').replace(' ', '')
                           for p in [b, *b.parents] if hasattr(p, 'get'))]
    if len(buttons) > 1:
        raise ValueError('Ambiguous pagination')
    return buttons[0] if buttons else None


class ArriateAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE = SOURCE

    def _fetch(self, session, url):
        response = session.get(official(url), timeout=45)
        response.raise_for_status()
        official(response.url)
        if response.status_code != 200 or not response.content.strip():
            raise ValueError('Empty or challenged source response')
        self.source_urls.append(response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / f'source-{len(self.source_urls):03d}.html').write_text(response.text, encoding='utf-8')
        return response

    def _inventory(self, session, url):
        response = self._fetch(session, url)
        canonical = response.url
        if not urlparse(canonical).path.startswith('/transparency/'):
            raise ValueError('Navigation did not resolve to a stable folder URL')
        soup = prepare(response.text, canonical)
        seen = set()
        while (button := more_button(soup)) is not None:
            target = button['data-callback']
            if target in seen:
                raise ValueError('Repeated pagination callback')
            seen.add(target)
            response = self._fetch(session, target)
            if response.text.lstrip().startswith('<?xml'):
                apply_ajax(soup, response.text, response.url)
            else:
                soup = prepare(response.text, response.url)
        docs, folders = parse_inventory(soup)
        return canonical, docs, folders

    def _collect(self, session, folder, visited):
        url, docs, children = self._inventory(session, folder['callback'])
        if url in visited:
            raise ValueError('Cyclic or duplicate instrument folder')
        visited.add(url)
        for doc in docs:
            doc['inventory_url'] = url
        for child in children:
            _, nested = self._collect(session, child, visited)
            docs.extend(nested)
        if len(docs) != folder['count']:
            raise ValueError(f"Incomplete folder {folder['titulo']}: {len(docs)} != {folder['count']}")
        if len({d['url'] for d in docs}) != len(docs):
            raise ValueError('Duplicate document across instrument folders')
        return url, docs

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        rows = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'MunicipalDocumentInventory/1.0'
            _, _, folders = self._inventory(session, SOURCE)
            planning = next((f for f in folders if f['titulo'] == 'PLANEAMIENTO URBANÍSTICO'), None)
            if planning is None:
                raise ValueError('Planning section missing')
            _, _, instruments = self._inventory(session, planning['callback'])
            selected = [(f, 'planeamiento_urbanistico') for f in instruments
                        if f['titulo'].startswith('Innovación PGOU Arriate')]
            selected += [(f, 'plan_vivienda_suelo') for f in folders if f['titulo'].startswith('PMVS ')]
            selected += [(f, 'proyecto_saneamiento') for f in folders
                         if 'EDAR Y COLECTORES ARRIATE' in f['titulo']]
            if len(selected) != 3:
                raise ValueError('Reviewed inventory scope changed; expected three named instruments')
            visited = set()
            for folder, kind in selected:
                url, docs = self._collect(session, folder, visited)
                if not docs:
                    raise ValueError('Instrument lacks source documents')
                rows.append({'id': 'arriate-' + url.rstrip('/').split('/')[-1],
                             'municipio': 'Arriate', 'codigo_ine': '29020', 'provincia': 'Málaga',
                             'titulo': folder['titulo'], 'tipo': kind, 'url': url,
                             'inventory_url': SOURCE, 'source': 'ayuntamiento',
                             'origen': 'inventario_documental_transparencia', 'documentos': docs,
                             'geometry_status': 'unavailable', 'publication_ready': False})
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'document_count': sum(len(r['documentos']) for r in rows),
                'source_urls': list(dict.fromkeys(self.source_urls)), 'limitations': LIMITATIONS}

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
