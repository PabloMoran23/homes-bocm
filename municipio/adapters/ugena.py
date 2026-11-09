"""Partial official planning inventory of Ugena; documents grouped by instrument."""
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

HOST = 'ugena.sedelectronica.es'
SOURCE = f'https://{HOST}/transparency/a9e4a3f2-d04c-4680-94ba-7d79c4f796e9/'
LIMITATIONS = [
    'Partial inventory: NNSS and Plan parcial SECTOR 13 EL LLANO only; modificaciones puntuales, POM en tramitación, execution notices and other works excluded.',
    'Inventory classification en vigor is retained; no approval or publication dates inferred from folder placement or crawl time.',
    'Document links and source titles retained, PDF contents not interpreted; no verified project geometry. publication_ready=false.',
    'Licences disabled; historical licence lists exist but are outside this adapter scope.',
]


def official(url):
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != HOST:
        raise ValueError('Unexpected source host')
    return url


def page_content(text):
    """Wicket pagination sends HTML in XML components; never execute evaluate JS."""
    if text.lstrip().startswith('<?xml'):
        root = ET.fromstring(text)
        if root.tag != 'ajax-response':
            raise ValueError('Unexpected XML response')
        text = '\n'.join(node.text or '' for node in root.findall('component'))
        if not text:
            raise ValueError('No inventory components in Wicket response')
    return BeautifulSoup(text, 'html.parser')


def action_url(element, base):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing public inventory navigation action')
    return official(urljoin(base, match[1]))


def inventory_entries(soup):
    # Restrict extraction to inventory rows (also present in Wicket fragments).
    docs, folders = [], []
    for a in soup.select('td.class_name a.gIconLink'):
        title = a.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            count = a.select_one('.linkExtraInfo')
            match = re.fullmatch(r'\s*\(\s*(\d+)\s*\)\s*', count.get_text() if count else '')
            if not match:
                raise ValueError('Missing folder document count')
            name = title[:title.rfind('(')].strip()
            folders.append((name, int(match[1]), a))
        elif '/preview-document/' in a.get('href', ''):
            docs.append({'titulo': title, 'url': official(a['href'])})
    return docs, folders


def make_record(title, url, docs, tipo):
    if not docs or len({d['url'] for d in docs}) != len(docs):
        raise ValueError('Missing or duplicate instrument documents')
    return {
        'id': 'ugena-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Ugena', 'provincia': 'Toledo', 'codigo_ine': '45176',
        'titulo': title, 'tipo': tipo, 'fase': None,
        'estado_fuente': 'NORMATIVA EN VIGOR',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': url, 'inventory_url': SOURCE, 'url_documento': docs[0]['url'],
        'documentos': docs, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'unavailable', 'coverage': 'partial_current_inventory',
    }


class UgenaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, session, url):
        official(url)
        with session.get(url, timeout=30, stream=True) as response:
            response.raise_for_status()
            official(response.url)
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Inventory response exceeds size limit')
                chunks.append(chunk)
            content = b''.join(chunks)
            if self.config.get('capture_dir'):
                directory = Path(self.config['capture_dir'])
                directory.mkdir(parents=True, exist_ok=True)
                (directory / f'source-{len(self.source_urls):03d}.html').write_bytes(content)
            # For Wicket actions, relative URLs resolve against the response URL.
            self.source_urls.append(response.url)
            return page_content(content.decode('utf-8')), response.url

    def _folder(self, session, soup, base, seen, depth=0):
        if depth > 5:
            raise ValueError('Unexpected folder depth')
        documents, children = [], []
        while True:
            docs, folders = inventory_entries(soup)
            documents.extend({**doc, 'inventory_url': base} for doc in docs)
            children.extend((name, count, action_url(a, base)) for name, count, a in folders)
            more = [b for b in soup.select('.more_results button[onclick]') if 'Mostrar más' in b.get_text()]
            if not more:
                break
            target = action_url(more[0], base)
            signature = tuple(d['url'] for d in docs) + tuple(name for name, _, _ in folders)
            if signature in seen or len(seen) >= 100:
                raise ValueError('Pagination stalled or exceeded safety bound; refusing partial output')
            seen.add(signature)
            soup, base = self._get(session, target)
        for name, expected, target in children:
            sub_soup, sub_base = self._get(session, target)
            child_docs = self._folder(session, sub_soup, sub_base, seen, depth + 1)
            if len(child_docs) != expected:
                raise ValueError(f'Incomplete folder {name}: {len(child_docs)} != {expected}')
            documents.extend(child_docs)
        if len({d['url'] for d in documents}) != len(documents):
            raise ValueError('Duplicate documents in inventory')
        return documents

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-ugena/1.0 (public planning inventory)'
            soup, base = self._get(session, SOURCE)
            docs, folders = inventory_entries(soup)
            nnss = [(name, count, a) for name, count, a in folders if name == 'NORMAS SUBSIDIARIAS MUNICIPALES DE UGENA']
            sector = [d for d in docs if d['titulo'] == 'Plan parcial SECTOR 13 EL LLANO']
            if len(nnss) != 1 or len(sector) != 1:
                raise ValueError('Expected named instruments missing or ambiguous')
            # Root is an explicit scope selection; never silently ignore root pagination.
            if soup.select('.more_results button[onclick]'):
                raise ValueError('Root inventory changed: pagination needs review')
            name, expected, element = nnss[0]
            child, child_base = self._get(session, action_url(element, base))
            instrument_url = child_base
            documents = self._folder(session, child, child_base, set())
            if len(documents) != expected:
                raise ValueError(f'Incomplete NNSS: {len(documents)} != {expected}')
            rows = [make_record(name, instrument_url, documents, 'Normas subsidiarias'),
                    make_record(sector[0]['titulo'], sector[0]['url'],
                                [{**sector[0], 'inventory_url': SOURCE}], 'Plan parcial')]
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'live_records': len(rows),
                'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': list(dict.fromkeys(self.source_urls)),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
