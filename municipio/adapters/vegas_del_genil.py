"""Anonymous municipal Gestiona planning inventory; no inferred approvals."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://vegasdelgenil.sedelectronica.es/transparency/'
HOST = urlparse(SOURCE).hostname
LIMITATIONS = [
    'Partial coverage: section 7.1 planning inventory only; not a licence register or all municipal works.',
    'Folder labels and document metadata, not PDF contents, determine grouping; no approval, validity or execution status inferred.',
    'Generic announcements, finca normalization and folders without an identifiable planning instrument are excluded.',
    'Document preview URLs retained; no verified geometry or agreement/publication dates extracted.',
]


def norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def label(anchor):
    return re.sub(r'\s*\(\s*\d+\s*\)\s*$', '', anchor.get_text(' ', strip=True)).strip()


def official(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != HOST:
        raise ValueError('Unexpected source URL: ' + url)
    return url


def ajax_url(anchor, base):
    match = re.search(r"wicketAjaxGet\('([^']+)'", anchor.get('onclick', ''))
    if not match:
        raise ValueError('Missing Gestiona navigation callback')
    return official(urljoin(base, match[1]))


def ajax_components(text):
    root = ET.fromstring(text)
    if root.tag != 'ajax-response':
        raise ValueError('Unexpected pagination response')
    parts = []
    for component in root.findall('component'):
        value = component.text or ''
        encoding = component.get('encoding')
        if encoding and encoding != 'wicket1':
            raise ValueError('Unknown Wicket encoding')
        if encoding == 'wicket1':
            value = value.replace(']^', ']')
        parts.append(value)
    if not parts:
        raise ValueError('Missing pagination components')
    return BeautifulSoup(''.join(parts), 'html.parser')


class Inventory:
    def __init__(self, capture_dir=None):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'municipal-planning-inventory/1.0'
        self.capture_dir = Path(capture_dir) if capture_dir else None
        self.source_urls = set()
        self.pages = 0

    def get(self, url, ajax=False):
        official(url)
        response = self.session.get(url, timeout=40, headers={'Wicket-Ajax': 'true'} if ajax else {})
        response.raise_for_status()
        official(response.url)
        if len(response.content) > 5_000_000:
            raise ValueError('Source exceeds response size limit')
        self.pages += 1
        if not ajax:
            self.source_urls.add(response.url)
        if self.capture_dir:
            self.capture_dir.mkdir(parents=True, exist_ok=True)
            (self.capture_dir / f'source-{self.pages:03d}.txt').write_text(response.text, encoding='utf-8')
        return response

    def folder_url(self, anchor, base):
        response = self.get(ajax_url(anchor, base), ajax=True)
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Missing folder redirect')
        target = official(urljoin(response.url, location))
        if not re.fullmatch(r'/transparency/[0-9a-f-]{36}/', urlparse(target).path):
            raise ValueError('Unexpected folder path')
        return target

    def listing(self, url):
        soup = BeautifulSoup(self.get(url).text, 'html.parser')
        if not soup.select_one('.TransparencyListPanel'):
            raise ValueError('Planning inventory table missing')
        entries = list(soup.select('.TransparencyListPanel a.gIconLink'))
        button = soup.select_one('.more_results button')
        seen = set()
        for _ in range(100):
            if button is None:
                return entries
            container_id = button.find_parent(class_='more_results').get('id')
            target = ajax_url(button, url)
            soup = ajax_components(self.get(target, ajax=True).text)
            new = soup.select('a.gIconLink')
            signature = tuple((label(a), a.get('href')) for a in new)
            if not new or signature in seen:
                raise ValueError('Pagination stalled or repeated')
            seen.add(signature)
            marker = soup.find(id=container_id) if container_id else None
            hidden_end = marker is not None and 'display:none' in marker.get('style', '').replace(' ', '')
            if not soup.select_one('.more_results') and not hidden_end:
                raise ValueError('Pagination completion marker missing')
            entries.extend(new)
            button = soup.select_one('.more_results button')
        raise ValueError('Pagination safety limit reached; refusing partial extraction')

    def section(self, base, prefix):
        # Navigation only: root also lists unrelated council announcements.
        soup = BeautifulSoup(self.get(base).text, 'html.parser')
        return self.child(soup.select('.TransparencyListPanel a.exp'), prefix, base)

    def child(self, entries, prefix, base):
        matches = [a for a in entries if label(a).startswith(prefix)]
        if len(matches) != 1:
            raise ValueError('Missing or ambiguous section ' + prefix)
        return self.folder_url(matches[0], base)


def document(anchor, inventory_url):
    url = official(urljoin(inventory_url, anchor.get('href', '')))
    if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(url).path):
        raise ValueError('Unexpected document link')
    return {'titulo': label(anchor), 'url': url, 'inventory_url': inventory_url}


def build_records(packages, loose, inventory_url):
    """packages: (source folder title, stable URL, complete document list)."""
    grouped = {}
    for title, folder, docs in packages:
        text = norm(title)
        # Named instruments, never generic folders or licence application forms.
        if any(x in text for x in ('licencia', 'solicitud', 'contratacion', 'licitacion')):
            continue
        if not any(x in text for x in ('plan general', 'plan parcial', 'innovacion', 'estudio detalle', 'estudio de detalle',
                                       'proyecto', 'p pp8', 'pp p12')):
            if not ('ge 3791 pp12' in text and any('proyecto reformado de urbanizacion' in norm(d['titulo']) for d in docs)):
                continue
        if not docs:
            raise ValueError('Identified instrument has no documents: ' + title)
        key = folder
        # Both source packages belong to the same named intervention/expediente.
        if re.search(r'\bp[\s.-]*u[\s.-]*e[\s.-]*2\b', text):
            key = 'ambito-pue2'
        if '825/2024' in text:
            key = 'expediente-825-2024'
        group = grouped.setdefault(key, {'titles': [], 'folders': [], 'docs': []})
        group['titles'].append(title)
        group['folders'].append(folder)
        group['docs'].extend(docs)
    # Root-level publications for identifiable instruments: keep related notices together.
    for anchor in loose:
        title = norm(label(anchor))
        detail = norm(anchor.get('title', ''))
        if 'estudio de detalle calle encina' in detail:
            key = 'estudio-detalle-calle-encina'
            group = grouped.setdefault(key, {'titles': ['Estudio de detalle Calle Encina (expediente 4916/2022)'], 'folders': [inventory_url], 'docs': []})
        elif 'pp12 estudio detalle' in title or 'estudio de detalle pp-12' in title:
            matches = [g for g in grouped.values() if any('4867' in t for t in g['titles'])]
            if len(matches) != 1:
                raise ValueError('Cannot associate PP12 announcement')
            group = matches[0]
        else:
            continue
        group['docs'].append(document(anchor, inventory_url))
    rows = []
    for key, group in grouped.items():
        docs = list({d['url']: d for d in group['docs']}.values())
        rows.append({
            'id': 'vegas-del-genil-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Vegas del Genil', 'codigo_ine': '18911', 'provincia': 'Granada',
            'titulo': ' / '.join(group['titles']), 'tipo': 'instrumento o proyecto urbanístico',
            'url': group['folders'][0], 'inventory_url': inventory_url,
            'source_urls': group['folders'], 'documentos': docs,
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'source_entity_type': 'documento',
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False, 'coverage': 'partial_current_planning_inventory',
        })
    if not rows:
        raise ValueError('No usable named planning instruments found')
    return rows


class VegasDelGenilAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        client = Inventory(self.config.get('capture_dir'))
        urban = client.section(SOURCE, '7. URBANISMO')
        planning = client.section(urban, '7.1. PLANEAMIENTO')
        entries = client.listing(planning)
        packages, loose = [], []
        for anchor in entries:
            if 'exp' not in anchor.get('class', []):
                loose.append(anchor)
                continue
            folder = client.folder_url(anchor, planning)
            children = client.listing(folder)
            if any('exp' in a.get('class', []) for a in children):
                raise ValueError('Nested instrument folder requires explicit grouping')
            docs = [document(a, folder) for a in children]
            count = re.search(r'\(\s*(\d+)\s*\)\s*$', anchor.get_text(' ', strip=True))
            if count is None or len(docs) != int(count[1]):
                raise ValueError('Instrument document count mismatch: ' + label(anchor))
            packages.append((label(anchor), folder, docs))
        rows = build_records(packages, loose, planning)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'source_urls': sorted(client.source_urls),
                'limitations': LIMITATIONS, 'inventory_entries': len(entries),
                'document_links': sum(len(r['documentos']) for r in rows), 'pages_fetched': client.pages}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
