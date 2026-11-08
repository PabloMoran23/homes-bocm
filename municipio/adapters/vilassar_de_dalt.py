"""Vilassar de Dalt's two public municipal planning document inventories.

One POUM dossier and one record per named instrument in the processing index.
Listing membership is provenance, not proof of present legal approval/status.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.vilassardedalt.cat'
POUM = BASE + '/temes/territori/pla-dordenacio-urbanistica-municipal-poum'
PROCESSING = BASE + '/temes/territori/planejament-urbanistic-en-tramit'
SOURCES = (POUM, PROCESSING)
HEADINGS = {POUM: "Pla d'Ordenació Urbanística Municipal (POUM)",
            PROCESSING: 'Planejament urbanístic en tràmit'}
LIMITATIONS = [
    'Partial coverage: two municipal planning document indexes only; no complete works or licence register.',
    'Index membership is not verified current legal status. Can Reig links contain aprovacio_definitiva despite the en tràmit index title.',
    'No agreement, approval or publication dates asserted; page-update timestamps and filename dates are not these dates.',
    'POUM annexes and sector sheets remain documents of the POUM, not separate approved projects.',
    'No verified geometry or coordinates; no municipal centroid or jitter substituted.',
    'Document links retained; PDF contents are not automatically interpreted or all downloaded.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _official(url):
    parts = urlsplit(url)
    return parts.scheme == 'https' and parts.netloc == 'www.vilassardedalt.cat'


def parse_inventory(html: str, source_url: str) -> list[dict]:
    if source_url not in SOURCES:
        raise ValueError('Unsupported municipal inventory')
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find('h1')
    if heading is None or _text(heading) != HEADINGS[source_url]:
        raise ValueError('Missing expected municipal planning heading')
    # These inventories expose their whole table in one response. Fail closed
    # if the site introduces pagination rather than silently taking page one.
    if soup.select('a[rel~=next], .pagination a[href], .paginacio a[href], .paginacion a[href], .pager a[href]'):
        raise ValueError('Inventory pagination detected; crawler must be extended')
    for anchor in soup.select('a[href]'):
        if re.search(r'[?&](?:page|pagina|offset|start)=', anchor['href'], re.I):
            raise ValueError('Inventory pagination detected')
    tables = [t for t in soup.select('table')
              if [_text(th) for th in t.select('thead th')] == ['Títol', 'Document', 'Url']]
    if len(tables) != 1:
        raise ValueError('Expected one complete planning document table')
    groups = {}
    current = None
    section = None
    for tr in tables[0].select('tbody tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 3:
            raise ValueError('Malformed planning document row')
        title, label = _text(cells[0]), _text(cells[1])
        anchors = cells[2].select('a[href]')
        if not label or len(anchors) != 1:
            raise ValueError('Planning document lacks a unique labelled link')
        doc_url = urljoin(source_url, anchors[0]['href'])
        if not _official(doc_url) or not urlsplit(doc_url).path.lower().endswith('.pdf'):
            raise ValueError('Unexpected planning document URL')
        if source_url == POUM:
            current = HEADINGS[POUM]
            if title:
                section = title
        elif title:
            # This first column is a category for modifications, unlike the
            # other named instruments. Its document label identifies the plan.
            current = label if title == 'Modificacions puntuals en tràmit' else title
            section = title
        elif current is None:
            raise ValueError('Orphan document before a named instrument')
        docs = groups.setdefault(current, [])
        doc = {'titulo': label, 'url': doc_url, 'seccion': section,
               'source_url': source_url}
        if doc not in docs:
            docs.append(doc)
    if not groups:
        raise ValueError('Empty planning inventory')
    update_match = re.search(r"darrera actualització d'aquest contingut:\s*(\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2})", soup.get_text(' ', strip=True))
    rows = []
    for title, docs in groups.items():
        identity = source_url + '#' + unicodedata.normalize('NFC', title).casefold()
        rows.append({
            'id': 'vilassar-de-dalt-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:20],
            'municipio': 'Vilassar de Dalt', 'provincia': 'Barcelona', 'codigo_ine': '08214',
            'titulo': title, 'tipo': 'POUM' if source_url == POUM else 'planeamiento_urbanistico',
            'fase': None, 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': source_url, 'url_documento': docs[0]['url'], 'documentos': docs,
            'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
            'source_inventory_title': HEADINGS[source_url],
            'source_page_updated_text': update_match[1] if update_match else None,
            'descripcion': 'Inventari documental municipal: ' + HEADINGS[source_url] + '. ' + title,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'No verified instrument geometry extracted',
        })
    return rows


class VilassarDeDaltAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-vilassar-de-dalt/1.0'}) as response:
            response.raise_for_status()
            if not _official(response.url) or 'html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Unexpected inventory response or redirect')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 5_000_000:
                    raise ValueError('Inventory exceeds response size limit')
            return bytes(body)

    @staticmethod
    def _write(out_jsonl, rows):
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temporary = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(out_jsonl)

    def backfill_proyectos(self, out_jsonl):
        rows = []
        for source in SOURCES:
            body = self._fetch(source)
            if self.config.get('evidence_dir'):
                folder = Path(self.config['evidence_dir'])
                folder.mkdir(parents=True, exist_ok=True)
                (folder / ('poum_live.html' if source == POUM else 'processing_live.html')).write_bytes(body)
            rows.extend(parse_inventory(body.decode('utf-8'), source))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh of the two unpaginated inventories, no date cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0,
                'reason': 'Application forms are not granted licences; no verified public licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
