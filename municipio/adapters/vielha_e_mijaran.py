"""Municipal planning document inventory; dates and legal status are not inferred."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'http://www.vielha-mijaran.org'
SOURCE = BASE + '/ar/menu/er-ajuntament-/14/gestion-municipau-/23/urbanisme/28/'
LIMITATIONS = [
    'Partial coverage: municipal Urbanisme document inventory only, not all RPUC dossiers or public works.',
    'Inventory gives no verified agreement, approval or publication dates; all remain null.',
    'Document labels preserve procedural references but do not establish current legal status.',
    'No verified project geometry; coordinates remain null and publication_ready is false.',
    'No granted-licence register extracted. Acoustic and consolidated urban fabric maps excluded.',
    'Municipal HTTPS certificate failed verification; official inventory is available over HTTP.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # The current source is unpaginated. Fail explicitly if pagination appears;
    # never report a complete snapshot after reading only its first page.
    if soup.select('[rel~=next], .pagination, .paginacion, .paginador'):
        raise ValueError('Pagination appeared: inventory traversal must be reviewed')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).lower() in ('següent', 'siguiente', 'next', 'seguent'):
            raise ValueError('Unrecognised next-page control')
    return soup


def _official(url, prefix):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or parsed.hostname != 'www.vielha-mijaran.org' or not parsed.path.startswith(prefix):
        raise ValueError('Unexpected municipal source URL: ' + url)
    return url


def parse_inventory(html, url=SOURCE):
    soup = _soup(html)
    groups = []
    for block in soup.select('.contenidoFichas'):
        links = block.select('a[href*="fitxaUrbanisme/"]')
        if not links:
            continue
        heading = block.select_one('h1')
        if not heading:
            raise ValueError('Planning package without title')
        title = heading.get_text(' ', strip=True)
        # Explicit planning instruments only, not every urbanism download.
        if not re.match(r'^(Modificacion|Modificacions|Expedient \d+.*Modificacion|Definició del polígon|Actuacion urbanistica|Projecte de reparcel)', title, re.I):
            continue
        fichas = list(dict.fromkeys(_official(urljoin(url, a['href']), '/fitxaUrbanisme/') for a in links))
        groups.append({'titulo': title, 'fichas': fichas})
    if not groups:
        raise ValueError('No named municipal planning instruments found')
    return groups


def parse_documents(html, url):
    soup = _soup(html)
    documents = []
    for row in soup.select('table tbody tr'):
        cells = row.find_all('td', recursive=False)
        if len(cells) < 2:
            continue
        label = cells[0].get_text(' ', strip=True)
        for a in cells[1].select('a[href]'):
            target = _official(urljoin(url, a['href']), '/public/vielha/ftp/urbanismoarchivos/')
            if not urlsplit(target).path.lower().endswith('.pdf') or not label:
                raise ValueError('Unexpected document format or missing title')
            document = {'titulo': label, 'url': target, 'source_url': url}
            if document not in documents:
                documents.append(document)
    if not documents:
        raise ValueError('Municipal detail page has no labelled planning documents: ' + url)
    return documents


def build_records(groups, fetch):
    records = []
    identities = set()
    for group in groups:
        docs = [doc for ficha in group['fichas'] for doc in parse_documents(fetch(ficha), ficha)]
        packages = [(group['titulo'], '', docs)]
        # The municipality puts two distinct modifications in one heading.
        # Split using explicit document labels, not guessed PDF filenames.
        if re.fullmatch(r'Modificacions des NNSS nombre 71\s*-\s*72', group['titulo']):
            packages = []
            for number in ('71', '72'):
                subset = [d for d in docs if re.search(r'\b' + number + r'\b', d['titulo'])]
                if not subset:
                    raise ValueError('Missing documents for bundled NNSS modification ' + number)
                packages.append(('Modificacion des NNSS nombre ' + number, '-' + number, subset))
            if sum(len(p[2]) for p in packages) != len(docs):
                raise ValueError('Ambiguous document membership in bundled NNSS modifications')
        for title, suffix, documents in packages:
            identity = group['fichas'][0] + suffix
            if identity in identities:
                raise ValueError('Repeated planning package in inventory')
            identities.add(identity)
            records.append({
                'id': 'vielha-e-mijaran-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
                'municipio': 'Vielha e Mijaran', 'codigo_ine': '25243', 'provincia': 'Lleida',
                'titulo': title, 'tipo': 'instrumento urbanístico', 'fase': None,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': group['fichas'][0], 'inventory_url': SOURCE,
                'source_urls': group['fichas'], 'documentos': documents,
                'url_documento': documents[0]['url'],
                'source': 'ayuntamiento', 'origen': 'inventario_urbanisme_municipal',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'geometry_status': 'No verified project geometry in inventory',
            })
    return records


class VielhaEMijaranAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def backfill_proyectos(self, out_jsonl: Path):
        sources = []

        def fetch(url):
            with requests.get(url, timeout=30, stream=True, headers={
                'User-Agent': self.config.get('user_agent', 'municipio-vielha-e-mijaran/1.0'),
            }) as response:
                response.raise_for_status()
                _official(response.url, '/')
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > 4_000_000:
                        raise ValueError('Municipal HTML exceeds response size limit')
                html = content.decode('utf-8')
            sources.append(url)
            capture_dir = self.config.get('capture_dir')
            if capture_dir:
                capture = Path(capture_dir)
                capture.mkdir(parents=True, exist_ok=True)
                name = 'inventory' if url == SOURCE else 'ficha-' + url.rstrip('/').rsplit('/', 1)[-1]
                (capture / (name + '.html')).write_text(html, encoding='utf-8')
            return html

        rows = build_records(parse_inventory(fetch(SOURCE)), fetch)
        if not rows:
            raise ValueError('Empty municipal inventory')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources,
                'coverage': 'municipal_planning_document_inventory',
                'publication_ready': False, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Refresh the entire inventory; no date filter or implicit pagination cap.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
