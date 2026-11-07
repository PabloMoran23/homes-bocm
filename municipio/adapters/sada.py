"""Sada's municipal planning document inventories; one row per instrument."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.sada.gal'
INVENTORY_URL = BASE + '/alcaldia'
# Explicit coverage: current document packages linked from the Urbanismo area.
PACKAGES = {
    '/plan-xeral-de-ordenacion-municipal': '/archivos/secciones/pxom/',
    '/plan-especial-de-veigue': '/archivos/pev/',
    '/peri-a-lagoa': '/archivos/urbanismo/peri_lagoa/',
    '/peri-a-canota': '/archivos/urbanismo/peri_canota/',
}
LIMITATIONS = [
    'Partial coverage: four document packages linked from Alcaldía y Urbanismo; '
    'not a complete municipal project, works or planning register.',
    'No granted licence register extracted. No coordinates or geocoding.',
    'Document filenames and AI/AD codes are not agreement dates or proof of current legal status.',
    'Document links are retained, not all PDF contents or link availability verified.',
    'PXOM publication date refers to the DOG order, not publication of the municipal web page.',
    'A Lagoa links a Cañota document: assigned by document path with page provenance retained.',
]


def official_url(href: str, page_url: str) -> str:
    url = urljoin(page_url, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'www.sada.gal':
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def check_pagination(soup):
    # These are single-page packages. Fail explicitly if that contract changes.
    if soup.select('[rel~=next], .pagination, .paginacion, .pager, [data-next-page]'):
        raise ValueError('Pagination detected; extraction would be incomplete')


def parse_inventory(html: str, page_url: str = INVENTORY_URL) -> list[str]:
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    found = set()
    for a in soup.select('a[href]'):
        url = urljoin(page_url, a['href'])
        if urlparse(url).path.rstrip('/') in PACKAGES:
            found.add(official_url(url, page_url).rstrip('/'))
    expected = {BASE + path for path in PACKAGES}
    if found != expected:
        raise ValueError('Urbanismo inventory missing expected planning packages')
    return sorted(found)


def parse_package(html: str, page_url: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    title = soup.find('h1')
    contents = soup.select('div.pagina')
    if title is None or len(contents) != 1:
        raise ValueError('Planning package title/content missing')
    path = urlparse(page_url).path.rstrip('/')
    if path not in PACKAGES:
        raise ValueError('Unsupported planning package')
    documents = []
    for a in contents[0].select('a[href]'):
        url = urljoin(page_url, a['href'])
        if not urlparse(url).path.lower().endswith('.pdf'):
            continue
        url = official_url(url, page_url)
        owners = [p for p, prefix in PACKAGES.items() if urlparse(url).path.startswith(prefix)]
        if len(owners) != 1:
            raise ValueError(f'Unclassified planning document: {url}')
        documents.append({'instrument_path': owners[0], 'titulo': a.get_text(' ', strip=True),
                          'url': url, 'source_urls': [page_url]})
    if not any(doc['instrument_path'] == path for doc in documents):
        raise ValueError('No instrument documents found')
    record = {
        'id': 'sada-' + path.lstrip('/'), 'municipio': 'Sada', 'codigo_ine': '15075',
        'provincia': 'A Coruña', 'titulo': title.get_text(' ', strip=True),
        'tipo': 'instrumento de planeamiento urbanístico', 'url': page_url,
        'inventory_url': INVENTORY_URL, 'source': 'ayuntamiento',
        'origen': 'inventario_documental_planeamiento', 'publication_ready': False,
        'geometry_status': 'unavailable', 'coverage': 'partial_document_inventory',
        'limitations': list(LIMITATIONS), 'documentos': documents,
    }
    if path == '/plan-xeral-de-ordenacion-municipal':
        heading = contents[0].find('h2')
        match = re.fullmatch(r'PXOM Aprobación definitiva \((\d{2}/\d{2}/\d{4})\)',
                             heading.get_text(' ', strip=True) if heading else '')
        if match:
            record['fecha_aprob'] = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
            record['fecha_aprob_fuente'] = page_url
            record['alcance_aprobacion'] = 'parcial; la página incluye separatas y condiciones'
        for doc in documents:
            match = re.match(r'(\d{2}/\d{2}/\d{4}) - Publicación no D\.O\.G\.', doc['titulo'])
            if match:
                record['fecha_publicacion'] = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
                record['fecha_publicacion_fuente'] = doc['url']
                record['fecha_publicacion_alcance'] = 'Publicación en DOG de la orden del PXOM'
    return record


def group_packages(packages: list[dict]) -> list[dict]:
    by_path = {urlparse(row['url']).path: row for row in packages}
    documents = {}
    for row in packages:
        for doc in row['documentos']:
            owner = doc['instrument_path']
            if owner not in by_path:
                raise ValueError('Document owner not fetched')
            key = (owner, doc['url'])
            if key not in documents:
                documents[key] = {k: v for k, v in doc.items() if k != 'instrument_path'}
            else:
                documents[key]['source_urls'] = sorted(set(documents[key]['source_urls'] + doc['source_urls']))
    return [{**row, 'documentos': [doc for (owner, _), doc in documents.items() if owner == path]}
            for path, row in sorted(by_path.items())]


class SadaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        captures = self.config.get('capture_dir')
        source_urls = []

        def fetch(url):
            response = requests.get(url, timeout=45, headers={
                'User-Agent': 'municipio-sada/1.0 (public planning inventory)'})
            response.raise_for_status()
            if response.url.rstrip('/') != url.rstrip('/'):
                raise ValueError(f'Unexpected redirect: {response.url}')
            source_urls.append(url)
            if captures:
                folder = Path(captures)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (urlparse(url).path.strip('/') + '.html')).write_text(response.text, encoding='utf-8')
            return response.text

        urls = parse_inventory(fetch(INVENTORY_URL))
        rows = group_packages([parse_package(fetch(url), url) for url in urls])
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': source_urls,
                'limitations': list(LIMITATIONS), 'coverage': 'partial_document_inventory',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        raise NotImplementedError('Licencias disabled: no verified public grants register')

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
