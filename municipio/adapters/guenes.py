"""Güeñes planning instruments from the official Bizkaia planning register."""
from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador'
LIMITATIONS = [
    'Partial municipal coverage: only instruments returned by the provincial planning register; no works or licence register.',
    'Registry status is reported as supplied; historical documents do not prove current construction or a granted licence.',
    'No verified vector geometry; no inferred coordinates. PDF contents are not parsed.',
    'A result-count mismatch (including future pagination) fails explicitly instead of returning a truncated inventory.',
]


def text(node):
    return node.get_text(' ', strip=True) if node else ''


def official_url(href):
    url = urljoin(SOURCE, href.strip())
    if urlsplit(url).hostname != 'www.bizkaia.eus':
        raise ValueError('Unexpected non-official register link')
    return url


def discover_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    form = soup.select_one('form[data-fm-namespace]')
    if not form:
        raise ValueError('Register search form missing')
    namespace = form['data-fm-namespace']
    option = form.select_one('select[name$="select-municipios"] option[value="45"]')
    if text(option).upper() != 'GUEÑES':
        raise ValueError('Municipality code 45 no longer identifies Gueñes')
    action = official_url(form['action'])
    parts = urlsplit(action)
    query = parse_qs(parts.query, keep_blank_values=True)
    query.update({namespace + 'select-municipios': ['45'],
                  namespace + 'select-figuras': ['-1'], namespace + 'filtro-texto': ['']})
    return urlunsplit(parts._replace(query=urlencode(query, doseq=True)))


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.select_one('.planeamiento-urbanistico')
    if not root:
        raise ValueError('Instrument inventory missing')
    total = re.search(r'\b(\d+) resultados de búsqueda', text(root))
    if not total:
        raise ValueError('Register result total missing')
    rows = {}
    for anchor in root.select('a[href]'):
        query = parse_qs(urlsplit(anchor['href']).query)
        ids = [v[0] for k, v in query.items() if k.endswith('_idInstrumento')]
        if not ids:
            continue
        municipality = [v[0] for k, v in query.items() if k.endswith('_idMunicipio')]
        if municipality != ['45'] or not re.fullmatch(r'\d+', ids[0]):
            raise ValueError('Unexpected instrument identity or municipality')
        count = re.search(r'\b(\d+) Documentos?\b', text(anchor))
        if not count or int(count[1]) == 0:
            raise ValueError('Missing document count')
        # Strip only the volatile navigation-back parameter, retaining registry IDs.
        query = {k: v for k, v in query.items() if not k.endswith('_backURL')}
        parts = urlsplit(official_url(anchor['href']))
        url = urlunsplit(parts._replace(query=urlencode(query, doseq=True)))
        row = {'registry_id': ids[0], 'url': url, 'expected_documents': int(count[1])}
        if ids[0] in rows and rows[ids[0]] != row:
            raise ValueError('Conflicting duplicate instrument')
        rows[ids[0]] = row
    if not rows or len(rows) != int(total[1]):
        raise ValueError('Incomplete inventory / pagination: discovered IDs differ from advertised total')
    return list(rows.values())


def parse_detail(html, entry, inventory_url):
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.select_one('.planeamiento-urbanistico-detalle')
    if not root or not text(root.select_one('h1')):
        raise ValueError('Instrument detail missing')

    def heading_value(label):
        heading = next((p for p in root.select('p[role="heading"]') if text(p) == label), None)
        if not heading or not heading.find_next_sibling('p'):
            raise ValueError('Missing detail field: ' + label)
        return text(heading.find_next_sibling('p'))

    municipality = heading_value('Municipio/s')
    normalized = unicodedata.normalize('NFKD', municipality).encode('ascii', 'ignore').decode().lower()
    if normalized != 'guenes':
        raise ValueError('Detail belongs to another municipality')
    fields = {}
    for item in root.select('.cajaListado li'):
        label = item.select_one('.negrita')
        if label:
            fields[text(label).rstrip(':')] = text(item)[len(text(label)):].strip()
    if not fields.get('Estado') or not fields.get('Figura de planeamiento'):
        raise ValueError('Missing registry status or planning type')
    row = {
        'id': 'guenes-plan-' + entry['registry_id'], 'municipio': 'Güeñes',
        'codigo_ine': '48045', 'provincia': 'Bizkaia', 'titulo': text(root.select_one('h1')),
        'tipo': 'planeamiento_urbanistico', 'figura_planeamiento': fields['Figura de planeamiento'],
        'estado_registro': fields['Estado'], 'expediente': heading_value('Expediente'),
        'url': entry['url'], 'inventory_url': inventory_url, 'source': 'diputacion_bizkaia',
        'organismo_fuente': 'Diputación Foral de Bizkaia', 'origen': 'registro_planeamiento_urbanistico',
        'geometry_status': 'unavailable', 'publication_ready': False,
    }
    approval = root.select_one('.cajaAprobacion')
    if approval:
        row['fase'] = text(approval.select_one('h3'))
        labels = {'Fecha de Resolución': 'fecha_acuerdo',
                  'Fecha de publicación resolución en BOB': 'fecha_publicacion',
                  'Fecha de publicación de Normativa en BOB': 'fecha_publicacion_normativa'}
        for item in approval.select('li'):
            label = text(item.select_one('.negrita'))
            date = text(item.select_one('.textoGrande'))
            if date and label in labels:
                row[labels[label]] = datetime.strptime(date, '%d/%m/%Y').date().isoformat()
    docs = {}
    for anchor in root.select('#bipo_acordeon_feature_docs a.UIB_btn-descarga[href]'):
        url = official_url(anchor['href'])
        docs.setdefault(url, {'titulo': text(anchor), 'url': url, 'procedencia': 'documentacion_instrumento'})
    if len(docs) != entry['expected_documents']:
        raise ValueError('Document count mismatch for ' + entry['registry_id'])
    for anchor in root.select('.cajaAprobacion a[href]'):
        url = official_url(anchor['href'])
        docs.setdefault(url, {'titulo': text(anchor.find_parent('li').select_one('.negrita')),
                              'url': url, 'procedencia': 'publicacion_BOB'})
    row['documentos'] = list(docs.values())
    row['documentos_instrumento_count'] = entry['expected_documents']
    return row


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    temporary.replace(path)


class GuenesAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        capture_dir = self.config.get('capture_dir')
        session = requests.Session()
        session.headers['User-Agent'] = 'municipio-guenes/1.0 (public planning inventory)'
        urls = []

        def fetch(url, name):
            response = session.get(url, timeout=40)
            response.raise_for_status()
            official_url(response.url)
            urls.append(response.url)
            if capture_dir:
                folder = Path(capture_dir)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / name).write_bytes(response.content)
            return response.text

        try:
            inventory_url = discover_inventory(fetch(SOURCE, 'search.html'))
            entries = parse_inventory(fetch(inventory_url, 'inventory.html'))
            rows = []
            for entry in entries:
                time.sleep(.2)
                rows.append(parse_detail(fetch(entry['url'], entry['registry_id'] + '.html'), entry, inventory_url))
            write_jsonl(out_jsonl, rows)
            return {'status': 'ok', 'count': len(rows), 'live_records': len(rows),
                    'source_urls': urls, 'limitations': LIMITATIONS}
        finally:
            session.close()

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        write_jsonl(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
