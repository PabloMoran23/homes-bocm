"""Ses Salines' official planning document inventory (not a licence register)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://ajsessalines.net'
INVENTORY = BASE + '/ca/arxius-i-documents/urbanisme'
SOURCE = INVENTORY + '/00-normes-subsidiaries-de-planejament'
LIMITATIONS = [
    'Partial coverage: only the municipal Normes Subsidiàries document inventory; no historical works or licence register.',
    'Maps, catalogues and bilingual consolidated texts are grouped under NNSS as published; legal currency is not verified.',
    'Portal document dates describe publication/upload, not agreements or approvals. No instrument-level date inferred.',
    'PDF contents and project geometries are not parsed; no coordinates inferred.',
]


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn')


def _main(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None:
        raise ValueError('Missing municipal main content')
    # This inventory currently has no pagination. A changed source must fail
    # visibly rather than returning a successful incomplete first-page snapshot.
    if soup.select('.pager, .pagination, a[rel~=next]') or main.select('a[href*="page="]'):
        raise ValueError('Pagination detected: inventory coverage requires review; no output written')
    return main


def parse_inventory(html, source_url=SOURCE):
    main = _main(html)
    heading = main.select_one('h1')
    if not heading or 'normes subsidiaries de planejament' not in _norm(heading.get_text(' ', strip=True)):
        raise ValueError('Unexpected planning inventory heading')
    documents = {}
    for a in main.select('a[download][href]'):
        target = urljoin(source_url, a['href'])
        parsed = urlparse(target)
        if parsed.scheme != 'https' or parsed.hostname != 'ajsessalines.net' or not parsed.path.startswith('/sites/cilma_ses_salines/files/') or not parsed.path.lower().endswith('.pdf'):
            raise ValueError('Unexpected municipal document URL')
        card = a.parent
        title_node = card.select_one('h3')
        if title_node is None:
            raise ValueError('Document title missing from inventory card')
        title = title_node.get_text(' ', strip=True)
        dates = re.findall(r'\b\d{2}/\d{2}/\d{4}\b', card.get_text(' ', strip=True))
        if len(dates) != 1:
            raise ValueError('Ambiguous document publication date')
        publication = datetime.strptime(dates[0], '%d/%m/%Y').date().isoformat()
        norm = _norm(title)
        if norm.startswith('pla especial de reforma interior'):
            key, kind = norm, 'plan especial de reforma interior'
        elif (norm.startswith(('text refos de les normes', 'texto refundido de las normas', 'cataleg '))
              or re.match(r'^\d+(?:-\d+)? \d{4} ', norm)):
            key, kind = 'nnss', 'normas subsidiarias de planeamiento'
        else:
            raise ValueError(f'Unclassified inventory document requires review: {title}')
        doc = {'titulo': title, 'url': target, 'source_url': source_url,
               'fecha_publicacion': publication, 'fecha_tipo': 'fecha mostrada en el inventario municipal; publicación/subida',
               'instrument_key': key, 'tipo_instrumento': kind}
        if target in documents and documents[target] != doc:
            raise ValueError('Conflicting duplicate document metadata')
        documents[target] = doc
    if not documents:
        raise ValueError('No actual planning documents found')
    return list(documents.values())


def group_documents(documents):
    groups = {}
    for document in documents:
        groups.setdefault(document['instrument_key'], []).append(document)
    rows = []
    for key, docs in groups.items():
        title = (next((d['titulo'] for d in docs if _norm(d['titulo']).startswith('text refos de les normes')), None)
                 or 'Normes subsidiàries de planejament de Ses Salines') if key == 'nnss' else docs[0]['titulo']
        rows.append({
            'id': 'salines-ses-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Salines, Ses', 'codigo_ine': '07059', 'provincia': 'Illes Balears',
            'titulo': title, 'tipo': docs[0]['tipo_instrumento'],
            'url': SOURCE, 'inventory_url': INVENTORY,
            'url_documento': docs[0]['url'],
            'documentos': [{k: v for k, v in d.items() if k not in ('instrument_key', 'tipo_instrumento')} for d in docs],
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'fase': None, 'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'geometry_status': 'unavailable',
            'limitations': LIMITATIONS,
        })
    return rows


class SalinesSesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url, capture):
        response = requests.get(url, timeout=45, headers={'User-Agent': 'municipio-salines-ses/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != 'ajsessalines.net':
            raise ValueError('Unexpected source redirect')
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML inventory')
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture).write_bytes(response.content)
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        root = _main(self._fetch(INVENTORY, 'urbanisme.html'))
        links = [a for a in root.select('a[href]') if urljoin(INVENTORY, a['href']) == SOURCE]
        if len(links) != 1:
            raise ValueError('Planning folder missing or ambiguous in current inventory')
        count = re.search(r'\b(\d+) documents?\b', links[0].get_text(' ', strip=True))
        if not count:
            raise ValueError('Folder document count missing')
        docs = parse_inventory(self._fetch(SOURCE, 'normes.html'))
        if len(docs) != int(count[1]):
            raise ValueError('Incomplete inventory: document count differs from parent folder')
        rows = group_documents(docs)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'documents': len(docs),
                'source_urls': [INVENTORY, SOURCE], 'limitations': LIMITATIONS,
                'coverage': 'complete current folder; partial municipal coverage', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Complete refreshed snapshot; never claim a date-based incremental feed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'Application forms are not granted licences; no verified public register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
