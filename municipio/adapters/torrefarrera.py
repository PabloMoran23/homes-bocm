"""Current municipal planning/public-information snapshot, not a licence register."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.torrefarrera.cat'
PLANNING = BASE + '/ajuntament/urbanisme-1/planejament'
PUBLIC = BASE + '/ajuntament/informacio-publica-ajuntament'


def official(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'www.torrefarrera.cat':
        raise ValueError('Unexpected municipal source URL: ' + url)
    return url


def content(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    core = soup.select_one('#content-core')
    if core is None:
        raise ValueError('Missing municipal content; possible error/login page')
    # Fail explicitly if Plone introduces pagination, including folder detail pages.
    # The reviewed inventories are complete single pages, not a capped first page.
    if soup.select('.batching, .listingBar, .pagination, a[rel~=next]'):
        raise ValueError('Pagination detected; extend traversal before extracting')
    for a in core.select('a[href]'):
        if any(k in parse_qs(urlparse(a['href']).query) for k in ('b_start', 'b_start:int', 'page')):
            raise ValueError('Pagination detected in municipal content')
    return core


def entries(html: str, source_url: str) -> list[dict[str, str]]:
    core = content(html)
    links = core.select('table.listing a.url[href], .entries .summary a.url[href]')
    found = {}
    for a in links:
        title = a.get_text(' ', strip=True)
        if not title:
            continue  # duplicate icon anchor
        url = official(urljoin(source_url, a['href']))
        kind = 'file' if 'contenttype-file' in a.get('class', []) else 'folder' if 'contenttype-folder' in a.get('class', []) else 'link'
        found.setdefault(url, {'titulo': title, 'url': url, 'kind': kind})
    if not found:
        raise ValueError('Empty or changed municipal inventory: ' + source_url)
    return list(found.values())


def project_kind(title: str) -> str | None:
    if re.match(r'^Modificaci[óo] de les (?:NNSS|Normes Subsidiàries|normes subsidiàries)', title):
        return 'modificacion_planeamiento'
    if re.match(r'^Modifica(?:ci[óo]|icó) del Pla Parcial', title):
        return 'modificacion_planeamiento'
    if title.startswith('Projecte d’actuació específica per a la implantació d’una aula rural'):
        return 'proyecto_actuacion_especifica'
    if title.startswith('Aprovació de projecte tècnic') and 'escola La Creu' in title and 'panells solars' in title:
        return 'obra_publica'
    return None


def record(title: str, url: str, kind: str, docs: list[dict], inventory: str) -> dict[str, Any]:
    return {
        'id': 'torrefarrera-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Torrefarrera', 'codigo_ine': '25228', 'provincia': 'Lleida',
        'titulo': title, 'tipo': kind, 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': url, 'url_documento': docs[0]['url'], 'documentos': docs,
        'source': 'ayuntamiento', 'origen': 'inventario_municipal',
        'source_inventory': inventory,
        'date_notes': 'Dates and approval stage are not extracted from linked PDF contents; file/page timestamps are not agreement dates.',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified instrument geometry extracted',
    }


class TorrefarreraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url: str) -> str:
        official(url)
        with requests.get(url, timeout=(10, 45), stream=True, headers={
            'User-Agent': 'municipio-torrefarrera/1.0'
        }) as response:
            response.raise_for_status()
            official(response.url)
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 5_000_000:
                    raise ValueError('Municipal HTML response exceeds 5 MB')
                chunks.append(chunk)
            html = b''.join(chunks).decode('utf-8')
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(html, encoding='utf-8')
        self._source_urls.add(url)
        return html

    def _document(self, entry: dict) -> dict:
        core = content(self._fetch(entry['url']))
        links = {official(urljoin(entry['url'], a['href'])) for a in core.select('a[href]') if '/@@download/file' in a['href']}
        if len(links) != 1:
            raise ValueError('File view lacks a unique download: ' + entry['url'])
        return {'titulo': entry['titulo'], 'url': links.pop(), 'url_ficha': entry['url'], 'provenance': 'municipal_file_view'}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        self._source_urls = set()
        planning = entries(self._fetch(PLANNING), PLANNING)
        files = [e for e in planning if e['kind'] == 'file']
        informative = [e for e in files if e['titulo'].startswith('Text refós de caràcter informatiu')]
        if len(informative) != 1:
            raise ValueError('Missing or ambiguous informative consolidated planning text')
        files = informative + [e for e in files if e not in informative]
        plan = record('Normes Subsidiàries de Planejament de Torrefarrera — text refós informatiu',
                      informative[0]['url'], 'planeamiento_urbanistico',
                      [self._document(e) for e in files], PLANNING)
        plan['document_notes'] = 'Informative consolidation and accompanying municipal maps; not a new approval or a complete RPUC inventory.'
        plan['referencias'] = [e for e in planning if e['kind'] == 'link']
        rows = [plan]
        public = entries(self._fetch(PUBLIC), PUBLIC)
        for entry in public:
            kind = project_kind(entry['titulo'])
            if not kind:
                continue
            if entry['kind'] == 'file':
                docs = [self._document(entry)]
            elif entry['kind'] == 'folder':
                children = entries(self._fetch(entry['url']), entry['url'])
                if any(e['kind'] != 'file' for e in children):
                    raise ValueError('Unsupported nested project folder: ' + entry['url'])
                docs = [self._document(e) for e in children]
            else:
                raise ValueError('Unsupported project entry type')
            rows.append(record(entry['titulo'], entry['url'], kind, docs, PUBLIC))
        if len(rows) == 1:
            raise ValueError('No supported projects in public-information inventory')
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temp = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(self._source_urls),
                'coverage': 'partial current municipal inventories; full snapshot, no licence extraction',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory; forms and applications excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
