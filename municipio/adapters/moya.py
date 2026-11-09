"""Moya (Las Palmas): complete SITCAN package, grouped by planning instrument."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

DATASET = 'https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-moya'
API = 'https://opendata.sitcan.es/api/3/action/package_show?id=planeamiento-urbanistico-de-moya'
PACKAGE_ID = '5e5b27a4-0c5e-49de-9886-ce68ff3732ef'


def parse_package(payload):
    if payload.get('success') is not True:
        raise ValueError('SITCAN API did not return a successful package')
    package = payload['result']
    resources = package.get('resources', [])
    if (package.get('id') != PACKAGE_ID or package.get('name') != 'planeamiento-urbanistico-de-moya'
            or not resources or package.get('num_resources') != len(resources)
            or payload.get('next') or package.get('next')):
        raise ValueError('Wrong, empty or incomplete Moya inventory')
    groups = {}
    seen = set()
    for resource in resources:
        rid = resource['id']
        if rid in seen:
            raise ValueError('Duplicate resource identity in inventory')
        seen.add(rid)
        name = ' '.join(resource['name'].split())
        title = name.split(', publicado el ')[0]
        if not re.fullmatch(r'Aprobación Definitiva de (?:Modificación Puntual Nº\d+ de Normas Subsidiarias|Normas Subsidiarias|Estudio de Detalle .+) de Moya', title):
            raise ValueError('Unreviewed planning instrument: ' + name)
        url = resource['url']
        if urlparse(url).hostname not in {'opendata.sitcan.es', 'www.idecanarias.es', 'geobdp.grafcan.es'}:
            raise ValueError('Unreviewed resource host: ' + url)
        key = title.casefold()
        row = groups.setdefault(key, {
            'id': 'moya-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Moya', 'provincia': 'Las Palmas', 'codigo_ine': '35013',
            'titulo': title, 'tipo': 'planeamiento_urbanistico',
            'fase': 'aprobación definitiva', 'fecha': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'fecha_publicacion': None, 'publicaciones': [],
            'url': DATASET, 'source': 'sitcan', 'source_dataset': DATASET,
            'origen': 'inventario_oficial_planeamiento', 'documentos': [],
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'not_extracted', 'publication_ready': False,
        })
        description = resource.get('description') or ''
        # These are bulletin publication dates, never agreement/approval dates.
        for match in re.finditer(r'(\d{2}/\d{2}/\d{4}) en el (BOC|BOP)\s*(\d+/\d+)', name + ' ' + description):
            date = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
            publication = {'fecha_publicacion': date, 'boletin': match[2], 'numero': match[3]}
            if publication not in row['publicaciones']:
                row['publicaciones'].append(publication)
        row['documentos'].append({
            'id_origen': rid, 'titulo': name, 'descripcion': description,
            'formato_fuente': resource.get('format'), 'url': url,
            'provenance_url': API,
        })
    for row in groups.values():
        row['publicaciones'].sort(key=lambda p: p['fecha_publicacion'])
        if row['publicaciones']:
            row['fecha_publicacion'] = row['publicaciones'][0]['fecha_publicacion']
        indexes = [d['url'] for d in row['documentos'] if urlparse(d['url']).hostname == 'www.idecanarias.es']
        if len(indexes) != 1:
            raise ValueError('Expected one documentation index per instrument')
        row['url'] = indexes[0]
        row['id_origen'] = indexes[0]
    return sorted(groups.values(), key=lambda r: r['id'])


def parse_index(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    docs = {}
    for a in soup.select('a[href]'):
        href = urljoin(url, a['href'])
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'next'} or a.get('rel') == ['next']:
            raise ValueError('Documentation index is now paginated')
        if urlparse(href).path.lower().endswith('.pdf'):
            if not href.startswith(url.rsplit('/', 1)[0] + '/'):
                raise ValueError('PDF outside reviewed instrument directory')
            docs[href] = {'titulo': a.get_text(' ', strip=True), 'url': href,
                          'formato_fuente': 'PDF', 'provenance_url': url}
    if not docs:
        raise ValueError('Documentation index has no source PDFs')
    return list(docs.values())


class MoyaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, capture_name):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-moya/1.0'})
        response.raise_for_status()
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / capture_name).write_bytes(response.content)
        return response

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        # CKAN package_show returns ALL distributions; num_resources is checked.
        rows = parse_package(self._fetch(API, 'package-live.json').json())
        for row in rows:
            html = self._fetch(row['url'], row['id'] + '.html').content
            row['documentos'].extend(parse_index(html, row['url']))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [API] + [r['url'] for r in rows]}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current snapshot; state is deliberately not a date cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
