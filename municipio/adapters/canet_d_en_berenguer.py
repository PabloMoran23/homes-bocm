"""Anonymous municipal planning inventory; document labels are the evidence boundary."""
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

BASE = 'https://canetdenberenguer.sedelectronica.es'
PLANNING = BASE + '/transparency/4f94eb9b-8055-4b3b-8870-f70c995e9c2d/'
PMUS = BASE + '/transparency/581614e3-9da2-408d-964b-7a1d3c17c661/'
LIMITATIONS = [
    'Partial coverage: municipal 7.1 planning inventory and PMUS only; 7.2 urban regulations and other inventories excluded.',
    'Document labels and public preview links extracted; PDF contents and legal validity not independently assessed.',
    'Standalone Abanca/Joanot Martorell agreement excluded; no verified project in its inventory label.',
    'No granted-licence register, project geometry or coordinates extracted. Publication is disabled.',
]


def parse_page(text):
    """Wicket load-more returns XML CDATA components, never executable code."""
    if text.lstrip().startswith('<?xml') or '<ajax-response' in text[:200]:
        root = ET.fromstring(text)
        text = '\n'.join(el.text or '' for el in root.iter('component'))
    soup = BeautifulSoup(text, 'html.parser')
    entries = []
    for a in soup.select('a.gIconLink'):
        title = a.get_text(' ', strip=True)
        href = a.get('href', '')
        if 'exp' in a.get('class', []):
            match = re.search(r'\(\s*(\d+)\s*\)$', title)
            if not match:
                raise ValueError('Folder lacks document count')
            entries.append({'titulo': title[:match.start()].strip(), 'count': int(match[1]), 'action': action(a)})
        elif href.startswith(BASE + '/preview-document/'):
            entries.append({'titulo': title, 'url': href})
    more = [action(b) for b in soup.select('button[onclick]') if b.get_text(' ', strip=True) == 'Mostrar más']
    if len(more) > 1:
        raise ValueError('Ambiguous pagination')
    return entries, more[0] if more else None


def action(tag):
    match = re.search(r"wicketAjaxGet\('([^']+)'", tag.get('onclick', ''))
    if not match or not re.fullmatch(r'(?:\.\./)*\?x=[A-Za-z0-9*_-]+', match[1]):
        raise ValueError('Unsupported public navigation action')
    return match[1]


class CanetDEnBerenguerAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []

    def _fetch(self, session, url):
        if urlparse(url).hostname != urlparse(BASE).hostname:
            raise ValueError('Unexpected source host')
        with session.get(url, timeout=40, stream=True) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != urlparse(BASE).hostname:
                raise ValueError('Unexpected redirect host')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 4_000_000:
                    raise ValueError('Source exceeds response limit')
            text = content.decode('utf-8')
            self.source_urls.append(response.url)
            if self.config.get('capture_dir'):
                folder = Path(self.config['capture_dir'])
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f'source-{len(self.source_urls):03d}.html').write_text(text, encoding='utf-8')
            return response.url, text

    def _inventory(self, session, url, expected=None, depth=0):
        if depth > 5:
            raise ValueError('Unexpected folder depth')
        canonical, text = self._fetch(session, url)
        items, more = parse_page(text)
        seen = set()
        for _ in range(100):
            if not more:
                break
            # Parent folder counts include all descendant documents.
            total = sum(item.get('count', 1) for item in items)
            if expected is not None and total == expected:
                break
            next_url = urljoin(canonical, more)
            if next_url in seen:
                raise ValueError('Pagination loop before advertised count')
            seen.add(next_url)
            _, next_text = self._fetch(session, next_url)
            extra, more = parse_page(next_text)
            if not extra:
                raise ValueError('Pagination made no progress')
            items.extend(extra)
        else:
            raise ValueError('Pagination limit reached')
        total = sum(item.get('count', 1) for item in items)
        if not items or (expected is not None and total != expected):
            raise ValueError('Inventory incomplete or document count changed')
        docs = []
        for item in items:
            if 'action' in item:
                _, children, _ = self._inventory(session, urljoin(canonical, item['action']), item['count'], depth + 1)
                docs.extend(children)
            else:
                docs.append({**item, 'source_url': canonical})
        if len({d['url'] for d in docs}) != len(docs):
            raise ValueError('Duplicate documents: review grouping/counts')
        return canonical, docs, items

    @staticmethod
    def record(title, url, docs, kind, phase=None):
        return {
            'id': 'canet-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'municipio': "Canet d'En Berenguer", 'codigo_ine': '46082', 'provincia': 'Valencia',
            'titulo': title, 'tipo': kind, 'fase': phase,
            'url': url, 'url_documento': docs[0]['url'], 'documentos': docs,
            'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
            'descripcion': title, 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'coverage': 'partial', 'date_provenance': 'Only explicit document labels; no crawl timestamps used as event dates.',
        }

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-canet-d-en-berenguer/1.0'
            # Fetch the parent inventory first: its advertised subtree count is verified.
            canonical, text = self._fetch(session, PLANNING)
            entries, more = parse_page(text)
            if more or not entries:
                raise ValueError('Planning root changed; review pagination before extraction')
            rows = []
            direct = [e for e in entries if 'url' in e]
            supported = set()
            for entry in entries:
                if 'action' not in entry:
                    continue
                title = entry['titulo']
                if title.startswith('Borrador Catálago Bienes y Espacios Protegidos'):
                    kind, phase = 'catalogo_protecciones', 'borrador'
                elif title == 'CONVENIO URBANISTICO Y PROYECTO URBANIZACION POLIGONO XX':
                    kind, phase = 'proyecto_urbanizacion', None
                else:
                    raise ValueError('Unreviewed planning folder: ' + title)
                url, docs, _ = self._inventory(session, urljoin(canonical, entry['action']), entry['count'])
                supported.add(kind if kind == 'catalogo_protecciones' else 'XX')
                row = self.record(title, url, docs, kind, phase)
                for doc in docs:
                    match = re.fullmatch(r'DECRETO 2026-0515 \[Aprobación Proyecto de Urbanización Polígono XX\) (\d{2})/(\d{2})/(\d{4})', doc['titulo'])
                    if match:
                        from datetime import date
                        row['fecha_aprob'] = date(int(match[3]), int(match[2]), int(match[1])).isoformat()
                        row['fase'] = 'aprobación del proyecto de urbanización'
                        row['fecha_aprob_fuente'] = doc['url']
                rows.append(row)
            xiii = [d for d in direct if d['titulo'] in {'PROYECTO URBANIZACION POLIGONO XIII', 'CONVENIO 2022-0008 [CONVENIO CESIÓN POLÍGONO XIII]'}]
            if len(xiii) != 2 or supported != {'catalogo_protecciones', 'XX'}:
                raise ValueError('Required planning instruments missing')
            project = next(d for d in xiii if d['titulo'].startswith('PROYECTO'))
            rows.append(self.record(project['titulo'], project['url'], [{**d, 'source_url': canonical} for d in xiii], 'proyecto_urbanizacion'))
            unknown = [d for d in direct if d not in xiii and not d['titulo'].startswith('Convenio urbanístico entre el Ayto.')]
            if unknown:
                raise ValueError('Unreviewed standalone planning documents')
            url, docs, _ = self._inventory(session, PMUS)
            row = self.record('Plan de Movilidad Urbana Sostenible (PMUS)', url, docs, 'plan_movilidad')
            if any(d['titulo'] == 'Certificado de acuerdo Pleno 19 junio 2026' for d in docs):
                row['fecha_acuerdo'] = '2026-06-19'
                row['fecha_acuerdo_fuente'] = next(d['url'] for d in docs if d['titulo'] == 'Certificado de acuerdo Pleno 19 junio 2026')
            rows.append(row)
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls, 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        raise NotImplementedError('Licences disabled: no verified granted-licence inventory')

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
