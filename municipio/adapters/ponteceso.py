"""Ponteceso's municipal PXOM document inventory (partial planning coverage)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.ponteceso.net/PXOM/pxom.html'
LIMITATIONS = [
    'Partial coverage: municipal PXOM inventory and MR-Lestimoño only; not the complete Xunta register or works inventory.',
    'The inventory footer says July 2015 although it links 2019 documents; it is not an update timestamp.',
    'The 2002 superseded plan, application forms, procurement and news are excluded.',
    'Document links are retained; not every linked PDF is downloaded or checked for availability.',
    'MR-Lestimoño approval date is not parsed from PDF; its publication date comes from the explicit DOG link label.',
    'No verified project geometry or coordinates; municipal-office map is not project geometry.',
]


def _url(href):
    return quote(urljoin(SOURCE, href), safe=':/?=&%#')


def _pagination(soup):
    for a in soup.select('a[href], link[href]'):
        if a['href'] in ('', '#'):
            continue
        label = a.get_text(' ', strip=True).casefold()
        rel = set(a.get('rel', []))
        if rel & {'next', 'prev'} or re.search(r'^(seguinte|siguiente|next|anterior|[»›])', label) or a.find_parent(class_=re.compile(r'pagin', re.I)):
            raise ValueError('PXOM inventory pagination detected; traversal requires review')


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    _pagination(soup)
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    if title != 'PXOM de Ponteceso' or 'Plan Xeral de Ordenación Municipal' not in soup.get_text(' ', strip=True):
        raise ValueError('Missing Ponteceso PXOM inventory (possibly challenge page)')
    groups = {'pxom': {}, 'mr-lestimono': {}}
    dog = None
    publication = None
    for a in soup.select('a[href], area[href]'):
        url = _url(a['href'])
        parts = urlsplit(url)
        label = a.get_text(' ', strip=True)
        path = unquote(parts.path)
        if parts.hostname == 'www.xunta.es' and '/dog/Publicados/' in path:
            candidate = url.replace('http://www.xunta.es/', 'https://www.xunta.gal/').replace('https://www.xunta.es/', 'https://www.xunta.gal/')
            if dog and dog != candidate:
                raise ValueError('Ambiguous base-plan DOG reference')
            dog = candidate
        if not path.lower().endswith('.pdf'):
            continue
        if parts.hostname == 'www.ponteceso.net' and path.startswith('/PXOM/PXOM2015/'):
            group = 'pxom'
        elif parts.hostname == 'www.ponteceso.net' and path.startswith('/PXOM/PXOM/') and 'modificación' in label.casefold() and 'lestimoño' in label.casefold():
            group = 'mr-lestimono'
            match = re.search(r'DOG\s+(\d{2}/\d{2}/\d{2})', label)
            if match:
                publication = datetime.strptime(match[1], '%d/%m/%y').date().isoformat()
        elif parts.hostname == 'www.ponteceso.net' and 'Informe de participación pública' in label:
            group = 'pxom'
        else:
            raise ValueError(f'Unclassified inventory PDF requires review: {url}')
        groups[group].setdefault(url, {
            'titulo': label or path.rsplit('/', 1)[-1],
            'url': url, 'url_fuente': SOURCE,
            'provenance': 'municipal_inventory_link',
        })
    if not dog or not publication or any(not docs for docs in groups.values()):
        raise ValueError('Incomplete PXOM instrument/document groups')
    if not any('NORMATIVA' in unquote(url).upper() for url in groups['pxom']):
        raise ValueError('Missing base-plan regulations')
    records = []
    for key, docs in groups.items():
        records.append({
            'id': 'ponteceso-planeamiento-' + key,
            'municipio': 'Ponteceso', 'codigo_ine': '15068', 'provincia': 'A Coruña',
            'titulo': 'Plan Xeral de Ordenación Municipal de Ponteceso (PXOM)' if key == 'pxom' else 'Modificación MR-Lestimoño do PXOM de Ponteceso',
            'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': publication if key != 'pxom' else None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'fecha_publicacion_fuente': SOURCE if key != 'pxom' else None,
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_pxom',
            'documentos': list(docs.values()), 'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'coverage': 'partial_municipal_planning_inventory',
        })
    return records, dog


def enrich_base_plan(record, html, url):
    """The DOG heading distinguishes the order date from its publication."""
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.title.get_text(' ', strip=True) if soup.title else ''
    match = re.fullmatch(
        r'DOG \d+ do (\d{2}/\d{2}/\d{4}) - ORDE do (\d{1,2}) de (\w+) de (\d{4}) de aprobación definitiva do Plan xeral de ordenación municipal de Ponteceso\.', text)
    if not match:
        raise ValueError('DOG no longer identifies the definitive Ponteceso base-plan order')
    months = 'xaneiro febreiro marzo abril maio xuño xullo agosto setembro outubro novembro decembro'.split()
    approval = datetime(int(match[4]), months.index(match[3]) + 1, int(match[2])).date().isoformat()
    record.update(fecha_publicacion=datetime.strptime(match[1], '%d/%m/%Y').date().isoformat(),
                  fecha_aprob=approval, fecha_aprob_fuente=url, fecha_publicacion_fuente=url,
                  fase='aprobación definitiva con condiciones')
    record['documentos'].append({'titulo': 'Orde de aprobación definitiva (DOG)', 'url': url,
                                  'url_fuente': SOURCE, 'provenance': 'linked_official_bulletin'})


class PontecesoAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, capture_name):
        response = requests.get(url, timeout=35, headers={'User-Agent': 'municipio-ponteceso/1.0'})
        response.raise_for_status()
        if len(response.content) > 5_000_000:
            raise ValueError('Source exceeds reviewed HTML size; no truncated parsing')
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture_name).write_bytes(response.content)
        # Both sites declare their true encoding in HTML; HTTP may say latin-1.
        return str(BeautifulSoup(response.content, 'html.parser'))

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        rows, dog = parse_inventory(self._fetch(SOURCE, 'pxom-inventory.html'))
        enrich_base_plan(rows[0], self._fetch(dog, 'pxom-dog.html'), dog)
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [SOURCE, dog], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # A complete refresh of this one-page inventory, no incremental date filter.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
