"""Mollina PBOM snapshot from the Diputación's public IDEMAP inventory."""
from __future__ import annotations

import json
import math
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://www.idemap.es/pbom/'
INDEX = ROOT + 'php/api/municipios_obtener.php'
SOURCE = ROOT + 'php/municipio/municipio.php?cod_mun=29072'
DOCUMENTS = ROOT + 'php/documentos/documentos.php?cod_mun=29072'
LIMITATIONS = [
    'Partial coverage: only the current PBOM dossier in the provincial inventory; not all municipal works or historical planning.',
    'PBOM in preparation, not an approved plan or granted licence. Questionnaires are supporting documents only.',
    'No verified publication/agreement/approval dates or project geometry; these fields remain null.',
    'Technical-document tabs currently empty; participation documents are published on the municipal dossier page.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split()) if node else ''


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # These are complete HTML inventories, not crawls of the first page.
    if soup.select('.pagination, a[rel~="next"], button[data-pag]'):
        raise ValueError('Unexpected HTML pagination; refusing partial extraction')
    return soup


def _links(scope, base, provenance, stage):
    docs = []
    for anchor in scope.select('a[href]'):
        target = urljoin(base, anchor['href'])
        parsed = urlparse(target)
        if parsed.path.lower().endswith('.pdf'):
            if (parsed.scheme != 'https' or parsed.hostname != 'www.idemap.es'
                    or not parsed.path.startswith('/pbom/docs/29072/')):
                raise ValueError('Unexpected document origin or municipality')
            docs.append({'titulo': _text(anchor) or parsed.path.rsplit('/', 1)[-1],
                         'url': target, 'source_url': provenance, 'seccion': stage})
        elif '/docs/' in parsed.path:
            raise ValueError('Unrecognized document format; review inventory')
    return docs


def parse_projects(html: str, documents_html: str) -> list[dict]:
    """One instrument, all its linked documents; no dates from FAQs or footer."""
    soup = _soup(html)
    header = soup.select_one('h1.titulo-pbom')
    if (_text(header) != 'PBOM' or 'Ayuntamiento de MOLLINA' not in _text(soup)
            or _text(soup.title) != 'MOLLINA - PBOM'):
        raise ValueError('Missing municipality-specific PBOM identity')
    info = soup.select_one('#informacion .texto-una-columna')
    phase = soup.select_one('section.fase-actual strong')
    narrative = soup.select_one('section.fase-actual .descripcion-tramitacion')
    if not info or not phase or not narrative or 'PBOM' not in _text(info):
        raise ValueError('Missing current planning narrative or phase')
    base_tag = soup.find('base', href=True)
    base = urljoin(SOURCE, base_tag['href']) if base_tag else SOURCE
    docs = _links(soup, base, SOURCE, 'participación')
    if not any('PLAN DE PARTICIPACIÓN' in d['titulo'].upper() for d in docs):
        raise ValueError('Missing participation plan evidence')
    inventories = [urljoin(base, a['href']) for a in soup.select('a[href]')
                   if 'ACCESO A DOCUMENTOS' in _text(a)]
    if inventories != [DOCUMENTS]:
        raise ValueError('Changed or ambiguous technical-document inventory')

    technical = _soup(documents_html)
    if _text(technical.select_one('h2.titulo-documentos-municipio')) != 'Documentos del PBOM de MOLLINA':
        raise ValueError('Missing Mollina technical-document inventory')
    panes = technical.select('#faseTabsContent .tab-pane')
    tabs = technical.select('#fases-tab [data-bs-target]')
    if not panes or {p.get('id') for p in panes} != {t['data-bs-target'].lstrip('#') for t in tabs}:
        raise ValueError('Incomplete technical-document tabs')
    base_tag = technical.find('base', href=True)
    doc_base = urljoin(DOCUMENTS, base_tag['href']) if base_tag else DOCUMENTS
    sections = []
    for pane in panes:
        stage = _text(pane.select_one('h3'))
        linked = _links(pane, doc_base, DOCUMENTS, stage)
        if not stage or (not linked and 'Esta fase aún no dispone de documentos.' not in _text(pane)):
            raise ValueError('Unrecognized technical-document section')
        docs.extend(linked)
        sections.append({'titulo': stage, 'documentos': len(linked)})
    # A repeated link is one attachment, even if several parts of the page link it.
    grouped = {}
    for doc in docs:
        grouped.setdefault(doc['url'], doc)
    return [{
        'id': 'mollina-pbom-29072', 'municipio': 'Mollina', 'codigo_ine': '29072',
        'provincia': 'Málaga', 'titulo': 'Plan Básico de Ordenación Municipal de Mollina (PBOM)',
        'tipo': 'instrumento de planeamiento urbanístico', 'fase': _text(phase),
        'descripcion': _text(info), 'estado_tramitacion_descripcion': _text(narrative),
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': SOURCE, 'inventory_url': DOCUMENTS, 'source': 'ayuntamiento',
        'source_organismo': 'Diputación Provincial de Málaga — IDEMAP',
        'origen': 'inventario_provincial_pbom', 'documentos': list(grouped.values()),
        'secciones_documentales': sections,
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False,
    }]


def municipality_pages(fetch):
    """Follow every result page of the public municipality search, checking totals."""
    page, total, limit, municipalities = 1, None, None, []
    while True:
        data = fetch(page)
        if (not isinstance(data, dict) or type(data.get('total')) is not int
                or type(data.get('limit')) is not int or data['total'] < 0
                or data['limit'] <= 0 or data.get('page') != page
                or not isinstance(data.get('municipios'), list)):
            raise ValueError('Invalid municipality inventory pagination')
        if total is None:
            total, limit = data['total'], data['limit']
        if (total, limit) != (data['total'], data['limit']):
            raise ValueError('Municipality inventory changed during pagination')
        expected = max(0, min(limit, total - (page - 1) * limit))
        if len(data['municipios']) != expected:
            raise ValueError('Incomplete municipality inventory page')
        municipalities.extend(data['municipios'])
        if page >= max(1, math.ceil(total / limit)):
            break
        page += 1
        if page > 100:
            raise ValueError('Municipality pagination exceeds safety limit; no output written')
    matches = [m for m in municipalities if m.get('cod_mun') == '29072']
    if len(matches) != 1 or matches[0].get('nombre', '').upper() != 'MOLLINA':
        raise ValueError('Exact Mollina INE identity absent or duplicated in inventory')
    return municipalities


class MollinaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        source_urls = []
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            Path(capture_dir).mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-mollina/1.0 (public planning inventory)'

            def fetch(url, name):
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if (response.status_code != 200 or response.url != url
                        or len(response.content) > 4_000_000):
                    raise ValueError('Unexpected redirect, response status or oversized source')
                source_urls.append(response.url)
                if capture_dir:
                    (Path(capture_dir) / name).write_bytes(response.content)
                response.encoding = 'utf-8'
                return response

            municipality_pages(lambda page: fetch(
                f'{INDEX}?page={page}&search=Mollina', f'live-inventory-{page}.json').json())
            html = fetch(SOURCE, 'live-mollina.html').text
            documents_html = fetch(DOCUMENTS, 'live-documentos.html').text
            rows = parse_projects(html, documents_html)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'source_urls': source_urls, 'limitations': LIMITATIONS,
                'coverage': 'current_pbom_dossier', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full current dossier snapshot, not a chronological event feed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
