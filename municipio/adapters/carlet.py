"""Carlet's public planning folders; one record per documented instrument."""
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

ORIGIN = 'https://carlet.sedelectronica.es'
PLANNING = ORIGIN + '/transparency/589a7057-d378-4c62-af6c-dad93cd7d7ed/'
PAI = ORIGIN + '/transparency/8787db3a-7f67-4cd4-8086-6b2ce4e90270/'
INSTRUMENT = re.compile(r'^(?:Expedient de modificació puntual del Pla General número \d+|Catàleg de Proteccions|PP AUSIAS MARCH|7\.10 PAI AUSIAS MARCH)', re.I)


def action_url(element, base):
    """Read public Wicket navigation as data, never execute JavaScript."""
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing public folder/pagination navigation')
    url = urljoin(base, match[1])
    if urlparse(url).netloc != urlparse(ORIGIN).netloc:
        raise ValueError('Unexpected navigation host')
    return url


def parse_entries(soup, base):
    table = soup.select_one('table.TransparencyListPanel')
    if table is None:
        raise ValueError('Missing municipal transparency inventory')
    entries = []
    for a in table.select('a.exp, a[href]'):
        title = re.sub(r'\s*\(\s*\d+\s*\)\s*$', '', a.get_text(' ', strip=True))
        if not title:
            continue
        if 'exp' in a.get('class', []):
            entries.append({'kind': 'folder', 'titulo': title, 'url': action_url(a, base)})
        elif a.get('href') not in {'', '#'}:
            target = urljoin(base, a['href'])
            kind = 'document' if target.startswith(ORIGIN + '/preview-document/') else 'external'
            entries.append({'kind': kind, 'titulo': title, 'url': target})
    # Nested anchors in the source must not create duplicate documents.
    return list({(e['kind'], e['url']): e for e in entries}.values())


def merge_components(soup, xml):
    """Apply only HTML components from load-more responses; ignore script blocks."""
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response':
        raise ValueError('Unexpected pagination response')
    changed = False
    for component in root.findall('component'):
        fragment = BeautifulSoup(component.text or '', 'html.parser')
        node = fragment.find()
        if node is None:
            continue
        old = soup.find(id=component.get('id'))
        if old is not None:
            old.replace_with(node)
        elif node.name == 'tr':
            body = soup.select_one('table.TransparencyListPanel tbody')
            if body is None:
                raise ValueError('Pagination lost table body')
            body.append(node)
        else:
            raise ValueError('Unrecognized pagination component')
        changed = True
    if not changed:
        raise ValueError('Empty pagination response')


def make_record(title, url, documents):
    if not INSTRUMENT.match(title) or not documents:
        raise ValueError('Instrument requires a specific title and source documents')
    docs = list({d['url']: {'titulo': d['titulo'], 'url': d['url']} for d in documents}.values())
    return {
        'id': 'carlet-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Carlet', 'codigo_ine': '46085', 'provincia': 'Valencia',
        'titulo': title, 'tipo': 'programa_actuacion_integrada' if url == PAI else 'instrumento_planeamiento', 'url': url,
        'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
        'inventory_url': PLANNING if url != PAI else PAI,
        'documentos': docs, 'publication_ready': False, 'geometry_status': 'unavailable',
    }


class CarletAyuntamientoAdapter(AyuntamientoAdapter):
    """Full refresh of two explicitly scoped current public inventories.

    config.capture_dir optionally stores the fetched HTML/XML for local review.
    Licences, other transparency branches and unavailable PGOU are not covered.
    """

    def _fetch(self, session, url):
        response = session.get(url, timeout=40)
        response.raise_for_status()
        if urlparse(response.url).netloc != urlparse(ORIGIN).netloc:
            raise ValueError('Unexpected source redirect')
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
            (capture / name).write_text(response.text, encoding='utf-8')
        self.source_urls.add(response.url)
        return response

    def _folder(self, session, url):
        response = self._fetch(session, url)
        canonical = response.url
        if not re.fullmatch(r'/transparency/[\da-f-]{36}/', urlparse(canonical).path):
            raise ValueError('Folder did not resolve to a stable municipal URL')
        soup = BeautifulSoup(response.text, 'html.parser')
        entries = { (e['kind'], e['url']): e for e in parse_entries(soup, canonical) }
        # Gestíona uses a load-more button, not ordinary page-number links.
        for _ in range(100):
            more = soup.select_one('.more_results button')
            if more is None:
                break
            next_response = self._fetch(session, action_url(more, canonical))
            before = len(entries)
            if next_response.text.lstrip().startswith('<?xml'):
                merge_components(soup, next_response.text)
            else:
                soup = BeautifulSoup(next_response.text, 'html.parser')
            # New AJAX controls are relative to the root; resolve both forms
            # against the stable folder URL (../../ and ?x work at root too).
            for e in parse_entries(soup, canonical):
                entries[(e['kind'], e['url'])] = e
            if len(entries) == before and soup.select_one('.more_results button'):
                raise ValueError('Pagination made no progress')
        else:
            raise ValueError('Pagination exceeded safety bound; no partial output')
        if soup.select_one('a[rel=next], .pagination a[href], .paging a[href]'):
            raise ValueError('Unrecognized pagination; review before accepting partial coverage')
        return canonical, list(entries.values())

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = set()
        rows = []
        visited = set()
        excluded = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-carlet/1.0 (public planning inventory)'

            def walk(url, title=None, owner=None):
                canonical, entries = self._folder(session, url)
                if canonical in visited:
                    raise ValueError('Duplicate/cyclic inventory folder')
                visited.add(canonical)
                if len(visited) > 200:
                    raise ValueError('Inventory grew beyond reviewed scope')
                instrument = owner
                if title and INSTRUMENT.match(title) and owner is None:
                    instrument = {'title': title, 'url': canonical, 'documents': []}
                for entry in entries:
                    if entry['kind'] == 'folder':
                        walk(entry['url'], entry['titulo'], instrument)
                    elif entry['kind'] == 'document' and instrument:
                        instrument['documents'].append(entry)
                    else:
                        excluded.append(entry)
                if instrument is not None and owner is None:
                    if instrument['documents']:
                        rows.append(make_record(instrument['title'], canonical, instrument['documents']))
                    else:
                        excluded.append({'titulo': title, 'url': canonical, 'reason': 'empty instrument folder'})

            walk(PLANNING)
            walk(PAI, '7.10 PAI AUSIAS MARCH II UE-2')
        if not rows:
            raise ValueError('No documented planning instruments found')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(output)
        return {'count': len(rows), 'written': len(rows), 'source_urls': sorted(self.source_urls),
                'excluded': excluded, 'coverage': 'current_planning_and_pai_document_folders',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        raise NotImplementedError('Licences disabled: no verified grants inventory')

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
