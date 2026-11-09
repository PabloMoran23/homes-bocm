"""Municipal planning instruments from the official Canary Islands catalogue.

Catalogue distributions and their document indexes are grouped, never treated
as separate projects. Catalogue timestamps do not establish approval dates.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SLUG = 'la-aldea-de-san-nicolas'
DATASET = 'planeamiento-urbanistico-de-' + SLUG
CATALOG = 'https://datos.canarias.es/catalogos/general/dataset/' + DATASET
API = 'https://datos.canarias.es/catalogos/general/api/3/action/package_show?id=' + DATASET
HOSTS = {'opendata.sitcan.es', 'geobdp.grafcan.es', 'www.idecanarias.es'}


def parse_inventory(payload):
    if payload.get('success') is not True:
        raise ValueError('Catalogue API did not succeed')
    data = payload['result']
    if data.get('name') != DATASET or data.get('state') != 'active':
        raise ValueError('Wrong municipality or inactive dataset')
    resources = data.get('resources', [])
    if not resources or data.get('num_resources') != len(resources):
        raise ValueError('Incomplete resource inventory; pagination/schema must be reviewed')
    groups = {}
    for resource in resources:
        if resource.get('state', 'active') != 'active':
            continue
        title = ' '.join(str(resource.get('name') or '').split())
        if not (re.match(r'^Aprobación Definitiva\b', title, re.I)
                and re.search(r'\bPlan (General|Especial)\b', title, re.I)
                and 'La Aldea de San Nicolás' in title):
            continue
        target = resource.get('url', '')
        if urlparse(target).scheme not in {'https', 'http'} or urlparse(target).hostname not in HOSTS:
            raise ValueError('Unexpected planning distribution URL')
        # Names are shared across SIPU, FIP, consultation and document versions.
        identity = re.split(r',\s*publicado\b', title, flags=re.I)[0]
        key = identity.casefold()
        if key not in groups:
            groups[key] = {
                'id': SLUG + '-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'La Aldea de San Nicolás', 'codigo_ine': '35020',
                'provincia': 'Las Palmas', 'titulo': identity,
                'tipo': 'instrumento de planeamiento urbanístico',
                'source': 'gobierno_de_canarias', 'origen': 'catalogo_planeamiento_municipal',
                'source_dataset': CATALOG, 'inventory_url': API,
                'url': CATALOG, 'distribuciones': [], 'documentos': [],
                'publication_ready': False, 'geometry_status': 'unavailable',
                'cobertura': 'Inventario documental; no acredita vigencia actual ni ejecución de obras',
            }
        groups[key]['distribuciones'].append({
            'id': resource['id'], 'titulo': title, 'url': target,
            'formato': resource.get('format'),
            'descripcion': resource.get('description'),
        })
    if not groups:
        raise ValueError('No supported municipal planning instruments')
    for row in groups.values():
        indexes = [d['url'] for d in row['distribuciones'] if is_document_index(d['url'])]
        if len(set(indexes)) != 1:
            raise ValueError('Expected one document index per instrument')
        row['url'] = indexes[0]
    return sorted(groups.values(), key=lambda row: row['id'])


def is_document_index(url):
    parsed = urlparse(url)
    return (parsed.hostname == 'www.idecanarias.es'
            and parsed.path.startswith('/resources/PLA_ENP_URB/URB_PLA/GC/LAld/')
            and parsed.path.endswith('/indice.html'))


def parse_documents(html, index_url):
    soup = BeautifulSoup(html, 'html.parser')
    documents = {}
    for a in soup.select('a[href]'):
        text = ' '.join(a.get_text(' ', strip=True).split())
        if (a.get('rel') and 'next' in a['rel']) or text.casefold() in {'siguiente', 'next'}:
            raise ValueError('Document index pagination requires review')
        target = urljoin(index_url, a['href'])
        if not urlparse(target).path.lower().endswith('.pdf'):
            continue
        if not target.startswith(index_url.rsplit('/', 1)[0] + '/'):
            raise ValueError('Document outside its instrument directory')
        documents.setdefault(target, {'titulo': text, 'url': target, 'source_index': index_url})
    if not documents:
        raise ValueError('Planning document index contains no PDF links')
    return list(documents.values())


class LaAldeaDeSanNicolasAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, capture_name):
        response = requests.get(url, timeout=(10, 40), headers={
            'User-Agent': 'municipal-planning-inventory/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(url).hostname:
            raise ValueError('Unexpected source redirect')
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture_name).write_bytes(response.content)
        return response

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        rows = parse_inventory(self._fetch(API, 'regional-inventory.json').json())
        for row in rows:
            index = row['url']
            name = urlparse(index).path.split('/')[-2] + '-index.html'
            response = self._fetch(index, name)
            row['documentos'] = parse_documents(response.content, index)
        result = self._write(out_jsonl, rows)
        return {**result, 'coverage': 'official_municipal_planning_document_inventory',
                'distributions': sum(len(r['distribuciones']) for r in rows),
                'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': [API] + [r['url'] for r in rows]}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh: catalogue changes are not a reliable event chronology.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
