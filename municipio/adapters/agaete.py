"""Agaete's historical planning instruments in the official SITCAN inventory."""
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

DATASET = 'https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-agaete'
API = 'https://opendata.sitcan.es/api/3/action/package_show?id=planeamiento-urbanistico-de-agaete'
LIMITATIONS = [
    'Inventario histórico sistematizado de SITCAN; no cobertura completa del planeamiento municipal actual.',
    'No acredita vigencia, ejecución de obras ni concesiones de licencias.',
    'Las fechas de publicación proceden de las descripciones; los metadatos CKAN no son acuerdos.',
    'Sin geometrías ni coordenadas; descargas enlazadas, no inspección integral de los PDF/ZIP.',
]


def parse_inventory(payload):
    """package_show returns the complete resource array (not a paginated search)."""
    if payload.get('success') is not True:
        raise ValueError('SITCAN package_show failed')
    package = payload['result']
    if (package.get('name') != 'planeamiento-urbanistico-de-agaete'
            or package.get('title') != 'Planeamiento urbanístico de Agaete'):
        raise ValueError('Unexpected municipality/dataset')
    resources = package.get('resources', [])
    if not resources or package.get('num_resources') != len(resources):
        raise ValueError('Empty or incomplete resource inventory')
    groups = {}
    annulments = []
    for resource in resources:
        title = ' '.join(resource.get('name', '').split())
        if 'Agaete' not in title or not re.search(r'Plan (?:General|Parcial)', title):
            raise ValueError('Unreviewed resource in planning inventory')
        url = resource.get('url', '')
        if urlparse(url).hostname not in {'opendata.sitcan.es', 'www.idecanarias.es', 'geobdp.grafcan.es'}:
            raise ValueError('Unexpected resource host')
        if not resource.get('id') or not url:
            raise ValueError('Resource lacks provenance')
        if 'por la que se anula' in title:
            if 'SUSNO-1 Las Candelarias' not in title:
                raise ValueError('Unreviewed annulment')
            annulments.append(resource)
            continue
        # Publication text varies between resources; it is not an instrument identity.
        key = re.split(r', publicado el ', title)[0]
        groups.setdefault(key, []).append(resource)
    if annulments:
        matches = [k for k in groups if 'Plan Parcial del SUSNO-1 Las Candelarias' in k]
        if len(matches) != 1:
            raise ValueError('Annulment has no unique parent instrument')
        groups[matches[0]].extend(annulments)
    rows = []
    for title, items in groups.items():
        docs = []
        publication_dates = set()
        agreement_dates = set()
        indexes = []
        for item in items:
            desc = item.get('description') or ''
            doc = {'titulo': item['name'], 'url': item['url'], 'resource_id': item['id'],
                   'descripcion': desc, 'formato_catalogo': item.get('format'),
                   'mimetype_catalogo': item.get('mimetype'), 'source_url': API}
            match = re.search(r'publicado el (\d{2}/\d{2}/\d{4})', desc)
            if match:
                date = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
                doc['fecha_publicacion'] = date
                publication_dates.add(date)
            match = re.search(r'por Pleno COTMAC el (\d{2}/\d{2}/\d{4})', item['name'])
            if match:
                agreement_dates.add(datetime.strptime(match[1], '%d/%m/%Y').date().isoformat())
            if urlparse(item['url']).hostname == 'www.idecanarias.es':
                indexes.append(item['url'])
            docs.append(doc)
        if not indexes:
            raise ValueError('Instrument lacks official document index')
        # The original plan index is primary; the judgment remains an attached event.
        primary = next(i['url'] for i in items if urlparse(i['url']).hostname == 'www.idecanarias.es'
                       and 'por la que se anula' not in i['name'])
        row = {'id': 'agaete-plan-' + hashlib.sha256(title.encode()).hexdigest()[:20],
               'titulo': title, 'municipio': 'Agaete', 'codigo_ine': '35001',
               'provincia': 'Las Palmas', 'tipo': 'planeamiento_urbanistico',
               'url': primary, 'inventory_url': DATASET, 'source_url': API,
               'source': 'gobierno_de_canarias_sitcan', 'origen': 'inventario_planeamiento',
               'documentos': docs, 'coverage': 'historical_systematized_inventory',
               'publication_ready': False, 'geometry_status': 'unavailable'}
        if len(publication_dates) == 1:
            row['fecha_publicacion'] = next(iter(publication_dates))
        if len(agreement_dates) == 1:
            row['fecha_acuerdo'] = next(iter(agreement_dates))
        if any('por la que se anula' in i['name'] for i in items):
            row['advertencia_vigencia'] = 'El catálogo adjunta sentencia que anula este plan; registro histórico.'
        rows.append(row)
    if not rows:
        raise ValueError('No planning instruments')
    return rows


def parse_document_index(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('a[rel~=next], .pagination, .pager'):
        raise ValueError('Document index pagination requires review')
    docs = {}
    parent = url.rsplit('/', 1)[0] + '/'
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).lower() in {'siguiente', 'next'}:
            raise ValueError('Document index pagination requires review')
        target = urljoin(url, a['href'])
        if urlparse(target).path.lower().endswith('.pdf'):
            if not target.startswith(parent):
                raise ValueError('Document escapes instrument directory')
            docs.setdefault(target, {'titulo': a.get_text(' ', strip=True), 'url': target,
                                     'source_url': url, 'formato': 'PDF'})
    if not docs:
        raise ValueError('Official index has no PDF documents')
    return list(docs.values())


class AgaeteAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=45, headers={'User-Agent': 'municipio-agaete-inventory/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(url).hostname:
            raise ValueError('Unexpected source redirect')
        # Optional local evidence; no credentials or services beyond public sources.
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            suffix = '.json' if url == API else '.html'
            (path / (hashlib.sha256(url.encode()).hexdigest() + suffix)).write_bytes(response.content)
        return response

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = parse_inventory(self._fetch(API).json())
        source_urls = [API]
        for row in rows:
            indexes = list(dict.fromkeys(d['url'] for d in row['documentos']
                                        if urlparse(d['url']).hostname == 'www.idecanarias.es'))
            for url in indexes:
                response = self._fetch(url)
                row['documentos'].extend(parse_document_index(response.content, url))
                source_urls.append(url)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh; retain all resources and fail before replacing output on errors.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
