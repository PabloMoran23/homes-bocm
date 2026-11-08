"""Arico planning instruments from the Canary Islands official CKAN catalogue."""
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

DATASET = 'planeamiento-urbanistico-de-arico'
CATALOGUE = 'https://datos.canarias.es/catalogos/general/dataset/' + DATASET
API = 'https://datos.canarias.es/catalogos/general/api/3/action/package_show?id=' + DATASET
INDEX_PATH = '/resources/PLA_ENP_URB/URB_PLA/TF/Aric/'
LIMITATIONS = [
    'Inventario regional sistematizado de planeamiento; no registro de licencias ni de obras en ejecución.',
    'Cobertura parcial: no garantiza totalidad ni vigencia jurídica actual. El archivo regional consultado indica 23 instrumentos frente a 22 grupos del catálogo observado.',
    'Fechas de acuerdos y boletines transcritas de metadatos del catálogo, no verificadas contra todos los acuerdos originales.',
    'Dos instrumentos comparten el índice 510 (encabezado Las Eras); se conservan enlaces del catálogo sin expandir sus PDF ambiguos.',
    'Sin geometrías ni coordenadas; los ZIP se enlazan sin descargar y los PDF se enumeran desde sus índices.',
]


def _date(text, pattern):
    match = re.search(pattern, text, re.I)
    return datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None


def parse_catalogue(payload):
    """package_show returns the entire resource array, without paginated search."""
    if payload.get('success') is not True:
        raise ValueError('CKAN did not return success')
    package = payload['result']
    if package.get('name') != DATASET or package.get('title') != 'Planeamiento urbanístico de Arico':
        raise ValueError('Unexpected municipality/dataset')
    resources = package.get('resources', [])
    if not resources or package.get('num_resources') != len(resources):
        raise ValueError('Empty or incomplete CKAN resource array')
    groups = {}
    seen = set()
    for resource in resources:
        title = ' '.join(resource.get('name', '').split())
        if not re.match(r'^Aprobación Definitiva de (?:Modificación Puntual|Estudio (?:de )?Detalle|Plan (?:Parcial|Especial)|Texto Refundido|Normas Subsidiarias)\b', title):
            raise ValueError('Unreviewed resource type: ' + title)
        rid, url = resource.get('id'), resource.get('url', '')
        if not rid or rid in seen:
            raise ValueError('Missing/duplicate resource identifier')
        seen.add(rid)
        parsed = urlparse(url)
        if parsed.scheme not in {'http', 'https'} or parsed.hostname not in {'www.idecanarias.es', 'opendata.sitcan.es', 'geobdp.grafcan.es'}:
            raise ValueError('Unexpected document origin')
        groups.setdefault(title, []).append(resource)
    rows = []
    for title, members in groups.items():
        indices = [r for r in members if urlparse(r['url']).hostname == 'www.idecanarias.es'
                   and urlparse(r['url']).path.startswith(INDEX_PATH) and r['url'].endswith('/indice.html')]
        if len(indices) != 1:
            raise ValueError('Instrument must have one Arico document index: ' + title)
        index = indices[0]
        row = {
            'id': 'arico-plan-' + hashlib.sha256(title.encode()).hexdigest()[:20],
            'municipio': 'Arico', 'codigo_ine': '38005', 'provincia': 'Santa Cruz de Tenerife',
            'titulo': title, 'tipo': 'planeamiento_urbanistico', 'fase': 'aprobacion_definitiva',
            'url': index['url'], 'inventory_url': CATALOGUE, 'source_api': API,
            'source_entity_type': 'documento',
            'source': 'gobierno_de_canarias', 'origen': 'catalogo_oficial_planeamiento',
            'publication_ready': False, 'geometry_status': 'unavailable',
            'documentos': [
                {'id': r['id'], 'titulo': r['name'], 'descripcion': r.get('description', ''),
                 'url': r['url'], 'formato': r.get('format', ''),
                 'catalogue_resource_url': CATALOGUE + '/resource/' + r['id']}
                for r in members
            ],
            'date_provenance': 'Metadatos de recursos del catálogo; publicación en boletín, no actualización CKAN.',
        }
        # Dates must agree across resource descriptions; CMS timestamps are ignored.
        for field, pattern in [('fecha_acuerdo', r'\bpor [^,]*?\b(\d{2}/\d{2}/\d{4})'),
                               ('fecha_publicacion', r'publicado el (\d{2}/\d{2}/\d{4})')]:
            dates = {_date(r.get('description', ''), pattern) for r in members}
            dates.discard(None)
            if len(dates) > 1:
                raise ValueError('Conflicting source dates: ' + title)
            if dates:
                row[field] = dates.pop()
        rows.append(row)
    for row in rows:
        if sum(other['url'] == row['url'] for other in rows) > 1:
            row['source_warnings'] = ['El catálogo asigna el mismo índice a instrumentos distintos; asociación documental ambigua. PDF no expandidos.']
    return rows


def parse_document_index(html, index_url):
    """Resolve only PDFs inside this instrument's directory, retaining labels."""
    prefix = index_url.rsplit('/', 1)[0] + '/'
    docs = {}
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href]'):
        url = urljoin(index_url, a['href'].replace('\\', '/'))
        if urlparse(url).path.lower().endswith('.pdf'):
            if not url.startswith(prefix) or '/../' in url:
                raise ValueError('PDF outside instrument directory')
            docs[url] = {'titulo': ' '.join(a.get_text(' ', strip=True).split()), 'url': url,
                         'formato': 'PDF', 'index_url': index_url}
    if not docs:
        raise ValueError('Document index contains no PDFs: ' + index_url)
    return list(docs.values())


class AricoAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, capture_name):
        response = session.get(url, timeout=45)
        response.raise_for_status()
        if response.url != url:
            raise ValueError('Unexpected source redirect: ' + response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / capture_name).write_bytes(response.content)
        return response

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'MunicipalPlanningInventory/1.0'
            response = self._fetch(session, API, 'catalogo.json')
            rows = parse_catalogue(response.json())
            for row in rows:
                url = row['url']
                response = self._fetch(session, url, 'indice-' + url.split('/')[-2] + '.html')
                # Original Word HTML explicitly declares this encoding.
                docs = parse_document_index(response.content, url)
                if row.get('source_warnings'):
                    row['document_index_status'] = 'ambiguous_catalogue_association'
                else:
                    row['documentos'].extend(docs)
                    row['document_index_status'] = 'pdf_links_enumerated'
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'coverage': 'regional_planning_catalogue',
                'source_urls': [API, CATALOGUE] + [r['url'] for r in rows], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh: retains all instruments, no date cutoff or pagination cap.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
