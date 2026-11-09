"""Current public planning folders in Cenes de la Vega's official sede.

Folder labels establish documentary identity, not approval or current legal validity.
Wicket action URLs are discovered anew in an anonymous session on every refresh.
"""
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

BASE = 'https://cenesdelavega.sedelectronica.es'
SOURCES = (
    BASE + '/transparency/d61c3b92-0726-4754-94b3-d73d5b97fd5a/',
    BASE + '/transparency/b458133f-cced-4aeb-ac4d-63a971c7f33d/',
)
INSTRUMENT = re.compile(
    r'^(?:PGOU\.|REVISIÓN NNSS$|ESTUDIO DE DETALLE\b|'
    r'Propuesta de delimitación de Actuación de Transformación Urbanística\b|'
    r'Innovación del PGOU\b)', re.I
)


def official(url):
    p = urlparse(url)
    if p.scheme != 'https' or p.netloc != urlparse(BASE).netloc:
        raise ValueError('Unexpected source host: ' + url)
    return url


def action_url(node, page_url):
    match = re.search(r"wicketAjaxGet\('([^']+)'", node.get('onclick', ''))
    if not match:
        raise ValueError('Missing public Wicket navigation action')
    return official(urljoin(page_url, match[1]))


def parse_entries(markup, page_url, fragment=False):
    """Parse actual table entries only; return folders, documents and next action."""
    soup = BeautifulSoup(markup, 'html.parser')
    table = soup if fragment else soup.select_one('table.TransparencyListPanel')
    if table is None:
        raise ValueError('Planning inventory table missing')
    entries = []
    for a in table.select('a.gIconLink'):
        label = a.get_text(' ', strip=True)
        extra = a.select_one('.linkExtraInfo')
        if 'exp' in a.get('class', []):
            match = re.fullmatch(r'\s*\(\s*(\d+)\s*\)\s*', extra.get_text() if extra else '')
            if not match:
                raise ValueError('Folder has no document count')
            title = label[:label.rfind(extra.get_text(' ', strip=True))].strip()
            entries.append({'kind': 'folder', 'title': title, 'count': int(match[1]),
                            'action': action_url(a, page_url)})
        else:
            target = official(urljoin(page_url, a.get('href', '')))
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(target).path):
                raise ValueError('Unexpected document link')
            entries.append({'kind': 'document', 'title': label, 'url': target})
    button = soup.select_one('.more_results button')
    more = action_url(button, page_url) if button else None
    return entries, more


def parse_more(xml, page_url, control_id):
    """Wicket appends rows via component CDATA; scripts are never executed."""
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response' or root.find('redirect') is not None:
        raise ValueError('Unexpected pagination response')
    components = [c.text or '' for c in root.findall('component')]
    rows = [c for c in components if BeautifulSoup(c, 'html.parser').select_one('tr')]
    controls = [c.text or '' for c in root.findall('component') if c.get('id') == control_id]
    if len(controls) != 1:
        raise ValueError('Pagination did not return rows and a completion control')
    parsed = parse_entries(''.join(rows + controls), page_url, fragment=True)
    if not parsed[1] and not re.search(r'display:\s*none', controls[0]):
        raise ValueError('Pagination completion not explicit')
    if not rows and parsed[1]:
        raise ValueError('Pagination made no progress')
    return parsed


class CenesDeLaVegaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, url, **kwargs):
        official(url)
        response = self.session.get(url, timeout=40, **kwargs)
        response.raise_for_status()
        official(response.url)
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            filename = f'source-{len(self.captures) + 1:03d}.txt'
            (directory / filename).write_text(response.text, encoding='utf-8')
            self.captures.append({'file': filename, 'url': response.url,
                                  'status': response.status_code})
        return response

    def _listing(self, url):
        response = self._get(url)
        canonical = response.url
        if not re.fullmatch(r'/transparency/[0-9a-f-]{36}/', urlparse(canonical).path):
            raise ValueError('Folder did not resolve to a canonical public URL')
        entries, more = parse_entries(response.text, canonical)
        control = BeautifulSoup(response.text, 'html.parser').select_one('.more_results')
        control_id = control.get('id') if control else None
        for _ in range(100):
            if not more:
                break
            response = self._get(more, headers={
                'Wicket-Ajax': 'true',
                'Wicket-Ajax-BaseURL': urlparse(canonical).path.lstrip('/'),
                'Referer': canonical,
            })
            batch, more = parse_more(response.text, canonical, control_id)
            existing = {(e['kind'], e.get('url', e['title'])) for e in entries}
            if any((e['kind'], e.get('url', e['title'])) in existing for e in batch):
                raise ValueError('Pagination repeated entries')
            entries.extend(batch)
        else:
            raise ValueError('Pagination safety bound exceeded; refusing partial output')
        identities = [(e['kind'], e.get('url', e['title'])) for e in entries]
        if len(set(identities)) != len(identities):
            raise ValueError('Repeated inventory entries')
        return canonical, entries

    def _documents(self, url, expected, path=()):
        canonical, entries = self._listing(url)
        if canonical in self.visited:
            raise ValueError('Repeated document folder')
        self.visited.add(canonical)
        documents = []
        for entry in entries:
            if entry['kind'] == 'folder':
                _, nested = self._documents(entry['action'], entry['count'], path + (entry['title'],))
                documents.extend(nested)
            else:
                documents.append({'titulo': entry['title'], 'url': entry['url'],
                                  'inventory_url': canonical, 'carpeta': list(path)})
        if len(documents) != expected:
            raise ValueError(f'Document count mismatch at {canonical}: {len(documents)} != {expected}')
        return canonical, documents

    def _discover(self, url, inventory, depth=0):
        if depth > 12:
            raise ValueError('Inventory nesting safety bound exceeded')
        canonical, entries = self._listing(url)
        if canonical in self.visited:
            raise ValueError('Repeated inventory folder')
        self.visited.add(canonical)
        for entry in entries:
            if entry['kind'] != 'folder' or not entry['count']:
                continue
            title = entry['title']
            if INSTRUMENT.match(title):
                target, docs = self._documents(entry['action'], entry['count'])
                if not docs:
                    raise ValueError('Instrument has no documents')
                self.rows.append({
                    'id': 'cenes-de-la-vega-plan-' + hashlib.sha256(target.encode()).hexdigest()[:16],
                    'municipio': 'Cenes de la Vega', 'codigo_ine': '18047', 'provincia': 'Granada',
                    'titulo': title, 'tipo': 'instrumento urbanístico',
                    'url': target, 'inventory_url': inventory, 'documentos': docs,
                    'source': 'ayuntamiento', 'origen': 'sede_transparencia_planeamiento',
                    'publication_ready': False, 'geometry_status': 'unavailable',
                })
            elif re.match(r'^(?:8\.1\.1\.|FINALIZADOS$|EN TRÁMITE DE INFORMACIÓN PÚBLICA$|\d{4}$)', title):
                self._discover(entry['action'], inventory, depth + 1)
            # Fiscal, personnel, service viability, climate and sports plans are
            # outside this explicitly urban-planning documentary inventory.

    def backfill_proyectos(self, out_jsonl: Path):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'municipio-cenes-planning/1.0'
        self.visited, self.rows, self.captures = set(), [], []
        try:
            for source in SOURCES:
                self._discover(source, source)
        finally:
            self.session.close()
        if not self.rows:
            raise ValueError('No usable planning instruments found')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in self.rows), encoding='utf-8')
        return {'count': len(self.rows), 'written': len(self.rows), 'source_urls': list(SOURCES),
                'coverage': 'current_public_urban_planning_folders', 'captures': self.captures,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Complete snapshot: do not pretend a folder listing is a dated event feed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
