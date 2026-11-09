"""Breña Alta planning instruments from the official Canary Islands inventory.

A snapshot of one CKAN package, not a register of licences or all municipal works.
Each instrument owns its distributions and the PDF links in its document index.
"""
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

DATASET = 'planeamiento-urbanistico-de-brena-alta'
CATALOG = 'https://datos.canarias.es/catalogos/general/dataset/' + DATASET
API = 'https://datos.canarias.es/catalogos/general/api/3/action/package_show?id=' + DATASET
INDEX_ROOT = 'https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LP/BreA/'
LIMITATIONS = [
    'Cobertura parcial: únicamente instrumentos del paquete oficial de planeamiento; no todas las obras o expedientes municipales.',
    'La clasificación de aprobación del catálogo no acredita vigencia íntegra: el portal municipal describe la aprobación del PGO de 2010 como parcial.',
    'Fechas de boletines separadas de acuerdos; metadatos de alta/modificación del catálogo no son fechas de aprobación.',
    'Sin licencias concedidas, geometría verificada ni geocodificación. Los PDF se enlazan, no se interpreta su contenido.',
]


def clean(text):
    return ' '.join(str(text or '').split())


def iso_date(text):
    return datetime.strptime(text, '%d/%m/%Y').date().isoformat()


def official_url(url):
    parsed = urlparse(url)
    if (parsed.scheme not in ('https', 'http') or parsed.username or parsed.password
            or parsed.hostname not in {'www.idecanarias.es', 'geobdp.grafcan.es', 'opendata.sitcan.es'}):
        raise ValueError('Unexpected resource URL in official inventory')
    return url


def parse_inventory(payload):
    """Validate a complete package_show response and group all distributions."""
    if not payload.get('success'):
        raise ValueError('CKAN request failed')
    package = payload['result']
    if (package.get('name') != DATASET or package.get('state') != 'active'
            or clean(package.get('title')) != 'Planeamiento urbanístico de Breña Alta'):
        raise ValueError('Wrong municipality or inactive dataset')
    resources = package.get('resources', [])
    if not resources or len(resources) != package.get('num_resources'):
        raise ValueError('Empty or incomplete resource inventory')
    grouped = {}
    seen = set()
    for resource in resources:
        title = clean(resource.get('name'))
        # Keep the source title; only remove a publication suffix for grouping.
        title = re.split(r',\s*publicado el\b', title, flags=re.I)[0].strip()
        if not re.match(r'^Aprobación definitiva de (?:Plan General|Modificación Puntual)\b', title, re.I) or 'de Breña Alta' not in title:
            raise ValueError('Unexpected non-planning resource; review changed inventory')
        rid = resource.get('id')
        if not rid or rid in seen:
            raise ValueError('Missing or duplicated CKAN resource identity')
        seen.add(rid)
        url = official_url(resource['url'])
        group = grouped.setdefault(title.casefold(), {'titulo': title, 'distributions': []})
        group['distributions'].append({
            'id': rid, 'titulo': clean(resource.get('name')), 'url': url,
            'formato': resource.get('format'), 'descripcion': clean(resource.get('description')),
            'source_url': CATALOG + '/resource/' + rid,
        })
    rows = []
    for group in grouped.values():
        distributions = sorted(group['distributions'], key=lambda d: d['id'])
        indexes = {d['url'] for d in distributions if d['url'].startswith(INDEX_ROOT) and d['url'].endswith('/indice.html')}
        if len(indexes) != 1:
            raise ValueError('Instrument must have exactly one official document index')
        index = indexes.pop()
        publications = {}
        agreements = set()
        for d in distributions:
            # Dates here are explicit bulletin publication dates, not CKAN timestamps.
            for match in re.finditer(r'(\d{2}/\d{2}/\d{4}) en el (BOC|BOP)\s+([^\s,;]+)', d['descripcion']):
                item = {'fecha': iso_date(match[1]), 'boletin': match[2], 'referencia': match[3]}
                publications[(item['fecha'], item['boletin'], item['referencia'])] = item
            for match in re.finditer(r'por pleno COTMAC\s+(\d{2}/\d{2}/\d{4})', d['titulo'], re.I):
                agreements.add(iso_date(match[1]))
        if len(agreements) > 1:
            raise ValueError('Conflicting explicit agreement dates')
        row = {
            'id': 'brena-alta-plan-' + hashlib.sha256(index.encode()).hexdigest()[:16],
            'municipio': 'Breña Alta', 'codigo_ine': '38008', 'provincia': 'Santa Cruz de Tenerife',
            'titulo': group['titulo'], 'tipo': 'instrumento de planeamiento urbanístico',
            'url': index, 'inventory_url': CATALOG, 'source_url': API,
            'source': 'gobierno_canarias', 'origen': 'catalogo_oficial_planeamiento',
            'organismo_fuente': 'Gobierno de Canarias / GRAFCAN',
            'distributions': distributions, 'publicaciones': sorted(publications.values(), key=lambda p: (p['fecha'], p['boletin'])),
            'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'partial_official_planning_inventory',
        }
        if agreements:
            row['fecha_acuerdo'] = next(iter(agreements))
            row['fecha_acuerdo_procedencia'] = 'Título del catálogo: por pleno COTMAC'
        rows.append(row)
    return sorted(rows, key=lambda r: r['url'])


def parse_documents(html, index_url):
    if not index_url.startswith(INDEX_ROOT) or not index_url.endswith('/indice.html'):
        raise ValueError('Unexpected document index')
    soup = BeautifulSoup(html, 'html.parser')
    # These indexes are single static lists. Fail if pagination appears.
    if soup.select('[rel~=next], .pagination, .pager'):
        raise ValueError('Document pagination appeared; traversal requires review')
    documents = {}
    root = index_url.rsplit('/', 1)[0] + '/'
    for a in soup.select('a[href]'):
        url = urljoin(index_url, a['href'])
        if urlparse(url).path.lower().endswith('.pdf'):
            if not url.startswith(root):
                raise ValueError('Document escaped its instrument directory')
            documents[url] = {'titulo': clean(a.get_text(' ', strip=True)), 'url': url,
                              'formato': 'PDF', 'source_url': index_url}
    if not documents:
        raise ValueError('No instrument documents found')
    return sorted(documents.values(), key=lambda d: d['url'])


class BrenaAltaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, url):
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-brena-alta/1.0'}) as response:
            response.raise_for_status()
            if response.url != url:
                raise ValueError('Unexpected source redirect')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 8_000_000:
                    raise ValueError('Source exceeds size bound; refusing truncated extraction')
            body = bytes(content)
            if self.config.get('capture_dir'):
                directory = Path(self.config['capture_dir'])
                directory.mkdir(parents=True, exist_ok=True)
                stem = hashlib.sha256(url.encode()).hexdigest()[:16]
                (directory / (stem + '.body')).write_bytes(body)
                (directory / (stem + '.meta.json')).write_text(json.dumps({
                    'url': url, 'status': response.status_code,
                    'content_type': response.headers.get('Content-Type'),
                    'sha256': hashlib.sha256(body).hexdigest(),
                }, ensure_ascii=False, indent=2), encoding='utf-8')
            return body

    def backfill_proyectos(self, out_jsonl: Path):
        rows = parse_inventory(json.loads(self._get(API)))
        source_urls = [API]
        for row in rows:
            row['documentos'] = parse_documents(self._get(row['url']), row['url'])
            source_urls.append(row['url'])
        # Write only after every instrument succeeds, avoiding partial snapshots.
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        """Refresh the complete current snapshot; no date cursor or deletion claims."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence register; forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
