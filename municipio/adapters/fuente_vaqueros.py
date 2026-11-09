"""Current municipal planning library; documents grouped by verified instrument."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.fuente-vaqueros.com/normativa/'
# Grouping verified against the PDF covers, not inferred from CMS dates.
SECTIONS = {
    'memoria-de-adaptacion': ('Memoria de adaptación', 'adaptacion'),
    'planos-adaptacion': ('Planos de adaptación', 'adaptacion'),
    'planos-informativos': ('Planos informativos', 'adaptacion'),
    'anexo-memoria': ('Anexo memoria', 'revision-nnss'),
    'planos-nnss': ('Planos NNSS', 'revision-nnss'),
    'planos-infraestructura': ('Planos infraestructura', 'adaptacion'),
}
TITLES = {
    'adaptacion': 'PGOU de Fuente Vaqueros — Adaptación parcial a la LOUA de las NNSS',
    'revision-nnss': 'Normas Subsidiarias de Planeamiento de Fuente Vaqueros — Revisión',
}


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # This library is unpaginated. Fail on new pagination rather than truncate.
    if soup.select('[rel~=next], .pagination, .nav-links, .page-numbers, .elementor-pagination'):
        raise ValueError('Pagination detected: library traversal needs review')
    return soup


def _official(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.netloc == urlparse(SOURCE).netloc


def parse_inventory(html, url=SOURCE):
    soup = _soup(html)
    if not any(h.get_text(' ', strip=True) == 'Documentación urbanística de Fuente Vaqueros'
               for h in soup.select('h2')):
        raise ValueError('Missing municipal planning inventory heading')
    sections = {}
    for a in soup.select('h4.elementor-icon-box-title a[href]'):
        target = urljoin(url, a['href'])
        key = urlparse(target).path.rstrip('/').split('/')[-1]
        if not _official(target) or key not in SECTIONS or urlparse(target).path != f'/normativa/{key}/':
            raise ValueError(f'Unrecognised inventory section: {target}')
        label = a.get_text(' ', strip=True)
        if label != SECTIONS[key][0]:
            raise ValueError(f'Changed section label: {label}')
        sections[key] = {'titulo': label, 'url': target}
    if set(sections) != set(SECTIONS):
        raise ValueError('Incomplete planning library')
    return sections


def parse_documents(html, section):
    soup = _soup(html)
    titles = {section['titulo']}
    if section['titulo'] == 'Planos de adaptación':
        titles.add('Planos adaptación')  # Actual child heading differs from card.
    if not any(h.get_text(' ', strip=True) in titles for h in soup.select('h1')):
        raise ValueError('Missing document section title')
    documents = {}
    for a in soup.select('a[href]'):
        target = urljoin(section['url'], a['href'])
        if not urlparse(target).path.lower().endswith('.pdf'):
            continue
        if not _official(target) or not urlparse(target).path.startswith('/wp-content/uploads/'):
            raise ValueError(f'Unexpected document origin: {target}')
        documents[target] = {'titulo': section['titulo'], 'url': target,
                             'source_page': section['url']}
    if not documents:
        raise ValueError(f'No PDF documents in {section["url"]}')
    return list(documents.values())


def parse_projects(inventory_html, section_html):
    sections = parse_inventory(inventory_html)
    grouped = {key: [] for key in TITLES}
    for key, section in sections.items():
        grouped[SECTIONS[key][1]].extend(parse_documents(section_html[key], section))
    rows = []
    for key, documents in grouped.items():
        rows.append({
            'id': f'fuente-vaqueros-plan-{key}', 'municipio': 'Fuente Vaqueros',
            'codigo_ine': '18079', 'provincia': 'Granada', 'titulo': TITLES[key],
            'tipo': 'instrumento de planeamiento', 'url': documents[0]['source_page'],
            'inventory_url': SOURCE,
            'url_documento': documents[0]['url'], 'documentos': documents,
            'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
            'descripcion': 'Documentación publicada en la biblioteca urbanística municipal. '
                           'No se acredita vigencia ni acuerdo de aprobación con este inventario.',
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    return rows


class FuenteVaquerosAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=45, headers={
            'User-Agent': 'municipio-fuente-vaqueros/1.0'})
        response.raise_for_status()
        if response.url != url:
            raise ValueError(f'Unexpected source redirect: {response.url}')
        if 'text/html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML planning library')
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        inventory = self._fetch(SOURCE)
        sections = parse_inventory(inventory)
        pages = {key: self._fetch(section['url']) for key, section in sections.items()}
        rows = parse_projects(inventory, pages)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                   for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'coverage': 'current_planning_library',
                'source_urls': [SOURCE] + [s['url'] for s in sections.values()],
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Complete current snapshot; no historical completeness/incremental claim.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
