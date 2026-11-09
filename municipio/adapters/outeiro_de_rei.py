"""Published municipal planning packages; no inference of legal status or dates."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://outeiroderei.gal/urbanismo/'
HOSTS = {'outeiroderei.gal', 'www.outeiroderei.gal'}
LIMITATIONS = [
    'Partial coverage: document packages linked from the municipal Urbanismo inventory only.',
    'The general Parque empresarial presentation is excluded; no licence register, news or procurement extraction.',
    'Document labels and filenames are retained as provenance, not interpreted as agreement/publication dates or current legal status.',
    'No coordinates or geometry; linked PDF contents are not parsed.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('a[rel~=next], .pagination, .page-numbers, .td-page-nav, .page-links'):
        raise ValueError('Pagination detected: review traversal before extracting partial coverage')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'seguinte', 'siguiente', 'next', 'anterior', 'previous'}:
            raise ValueError('Pagination link detected')
    return soup


def parse_inventory(html, url=SOURCE):
    entries = {}
    for a in _soup(html).select('h2 a[href]'):
        title = a.get_text(' ', strip=True)
        target = urljoin(url, a['href']).split('#')[0].split('?')[0]
        parsed = urlparse(target)
        if parsed.hostname not in HOSTS or not parsed.path.startswith('/urbanismo/'):
            continue
        if not re.search(r'\b(?:plan de sectorización|modificación|normas subsidiarias)\b', title, re.I):
            continue
        entries.setdefault(target, {'titulo': title, 'url': target})
    if not entries:
        raise ValueError('No supported planning packages in municipal inventory')
    return list(entries.values())


def parse_package(html, entry, inventory_url=SOURCE):
    soup = _soup(html)
    docs = {}
    for a in soup.select('p.tdm-descr a[href]'):
        target = urljoin(entry['url'], a['href'])
        parsed = urlparse(target)
        if parsed.hostname not in HOSTS or not parsed.path.startswith('/wp-content/uploads/'):
            continue
        if not parsed.path.lower().endswith('.pdf'):
            continue
        docs.setdefault(target, {'titulo': a.get_text(' ', strip=True), 'url': target,
                                 'source_url': entry['url']})
    if not docs:
        raise ValueError(f"Planning package lacks PDF documents: {entry['url']}")
    return {
        'id': 'outeiro-de-rei-plan-' + hashlib.sha256(entry['url'].encode()).hexdigest()[:16],
        'municipio': 'Outeiro de Rei', 'codigo_ine': '27039', 'provincia': 'Lugo',
        'titulo': entry['titulo'], 'tipo': 'planeamiento_urbanistico',
        'url': entry['url'], 'inventory_url': inventory_url,
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_urbanismo',
        'documentos': list(docs.values()), 'coverage': 'partial_municipal_document_inventory',
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class OuteiroDeReiAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        sources = []
        captures = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'

            def fetch(url):
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if urlparse(response.url).hostname not in HOSTS:
                    raise ValueError('Unexpected non-municipal redirect')
                if 'text/html' not in response.headers.get('Content-Type', ''):
                    raise ValueError('Expected HTML inventory/package')
                response.encoding = 'utf-8'
                sources.append(url)
                if self.config.get('evidence_dir'):
                    directory = Path(self.config['evidence_dir'])
                    directory.mkdir(parents=True, exist_ok=True)
                    name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
                    (directory / name).write_bytes(response.content)
                    captures.append({'url': url, 'final_url': response.url, 'status': response.status_code,
                                     'capture': name, 'sha256': hashlib.sha256(response.content).hexdigest()})
                return response.text

            entries = parse_inventory(fetch(SOURCE))
            rows = [parse_package(fetch(entry['url']), entry) for entry in entries]
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': sources,
                'limitations': LIMITATIONS, 'captures': captures, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh: no date watermark can safely represent this static inventory.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
