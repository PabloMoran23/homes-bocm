"""Valsequillo planning inventory published by the Canary Islands Government."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

DATASET = 'planeamiento-urbanistico-de-valsequillo-de-gran-canaria'
INVENTORY = 'https://opendata.sitcan.es/dataset/' + DATASET
API = 'https://opendata.sitcan.es/api/3/action/package_show?id=' + DATASET


def iso_date(value):
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


def parse_inventory(payload):
    """package_show returns all resources, not a paginated search result."""
    if payload.get('success') is not True:
        raise ValueError('SITCAN package request failed')
    package = payload['result']
    resources = package['resources']
    if (package['name'] != DATASET or package.get('private') is not False
            or package.get('state') != 'active'
            or package['num_resources'] != len(resources) or not resources):
        raise ValueError('Wrong, empty or incomplete SITCAN inventory')
    groups = {}
    for resource in resources:
        name = ' '.join(resource['name'].split())
        if (not name.startswith('Aprobación Definitiva de ')
                or 'de Valsequillo' not in name
                or resource.get('state') != 'active'):
            raise ValueError('Unreviewed planning resource')
        title = re.split(r'\s+(?:publicado el|por Pleno COTMAC el)\b', name)[0].rstrip(',')
        groups.setdefault(title, []).append(resource)
    rows = []
    for title, items in groups.items():
        consultations = [r for r in items if r['format'] == 'HTML']
        if len(consultations) != 1:
            raise ValueError('Instrument must have one stable GRAFCAN consultation')
        consultation = consultations[0]['url']
        parsed = urlparse(consultation)
        match = re.fullmatch(r'/core/documentos/(\d+)/', parsed.path)
        if parsed.hostname != 'geobdp.grafcan.es' or not match:
            raise ValueError('Unexpected consultation URL')
        publications, agreements, documents = {}, set(), {}
        for resource in items:
            url = resource['url']
            target = urlparse(url)
            if target.scheme not in {'http', 'https'} or target.hostname not in {
                'opendata.sitcan.es', 'www.idecanarias.es', 'geobdp.grafcan.es'
            }:
                raise ValueError('Unexpected document host')
            text = resource['description']
            for day, bulletin, number in re.findall(
                    r'(\d{2}/\d{2}/\d{4}) en el (BOC|BOP)\s+(\d+/\d+)', text):
                key = (bulletin, number, iso_date(day))
                publications[key] = {'boletin': bulletin, 'numero': number,
                                     'fecha': iso_date(day), 'fuente': API}
            for day in re.findall(r'por Pleno COTMAC el (\d{2}/\d{2}/\d{4})', text):
                agreements.add(iso_date(day))
            documents[url] = {
                'titulo': resource['name'], 'url': url,
                'formato_catalogo': resource['format'],
                'mimetype_catalogo': resource.get('mimetype'),
                'resource_id': resource['id'], 'descripcion': text,
                'procedencia': API,
            }
        if len(agreements) > 1 or not any(r['format'] == 'PDF' for r in items):
            raise ValueError('Ambiguous agreement or missing document index')
        rows.append({
            'id': 'valsequillo-plan-' + match[1],
            'municipio': 'Valsequillo de Gran Canaria', 'codigo_ine': '35031',
            'provincia': 'Las Palmas', 'titulo': title,
            'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación definitiva',
            'url': consultation, 'inventory_url': INVENTORY,
            'source': 'gobierno_de_canarias', 'origen': 'inventario_sitcan',
            'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': next(iter(agreements), None),
            'publicaciones': list(publications.values()),
            'documentos': list(documents.values()),
            'catalogo_actualizado': package.get('metadata_modified'),
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('One consultation identifies multiple instruments')
    return rows


def parse_document_index(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('a[rel~=next], .pagination, .pager') or any(
        a.get_text(' ', strip=True).lower() in {'siguiente', 'next'}
        for a in soup.select('a[href]')
    ):
        raise ValueError('Document index now paginated; traversal requires review')
    documents = {}
    for a in soup.select('a[href]'):
        target = urljoin(url, a['href'])
        if not urlparse(target).path.lower().endswith('.pdf'):
            if not a['href'].startswith('#'):
                raise ValueError('Unreviewed non-PDF document index link')
            continue
        if urlparse(target).hostname != 'www.idecanarias.es':
            raise ValueError('Unexpected PDF host')
        documents[target] = {'titulo': ' '.join(a.get_text(' ', strip=True).split()),
                             'url': target, 'formato': 'PDF', 'procedencia': url}
    if not documents:
        raise ValueError('Empty document index')
    return list(documents.values())


class ValsequilloDeGranCanariaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, capture_name):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-valsequillo/1.0 (public planning inventory)'
        })
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(url).hostname:
            raise ValueError('Unexpected source redirect')
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture_name).write_bytes(response.content)
        return response

    @staticmethod
    def _write(out_jsonl, rows):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(output)

    def backfill_proyectos(self, out_jsonl):
        rows = parse_inventory(self._fetch(API, 'sitcan-package.json').json())
        source_urls = [API]
        for row in rows:
            indices = [d for d in row['documentos'] if d['formato_catalogo'] == 'PDF']
            for index in indices:
                url = index['url']
                if (urlparse(url).hostname != 'www.idecanarias.es'
                        or not urlparse(url).path.endswith('/indice.html')):
                    raise ValueError('Expected IDECanarias document index')
                response = self._fetch(url, row['id'] + '-index.html')
                row['documentos'].extend(parse_document_index(response.content, url))
                source_urls.append(url)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': source_urls,
                'coverage': 'SITCAN municipal planning package; complete resource list, partial municipal coverage'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
