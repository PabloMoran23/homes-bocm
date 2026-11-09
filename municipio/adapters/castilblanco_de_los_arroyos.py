"""Current municipal planning document inventories, grouped by instrument."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Comment

from municipio.adapters.portal import AyuntamientoAdapter

SLUG = 'castilblanco-de-los-arroyos'
MUNICIPAL = 'https://www.castilblancodelosarroyos.es'
TRANSPARENCY = 'https://transparencia.castilblancodelosarroyos.es'
INDICATORS = TRANSPARENCY + '/es/transparencia/indicadores-de-transparencia/indicador/'
SOURCES = {
    'consulta': MUNICIPAL + '/es/obrasyurbanismo/nuevo-plan-basico-de-ordenacion-municipal/',
    'avance': INDICATORS + 'Avance-del-Plan-Basico-de-Ordenacion-Municipal./',
    'pgou': INDICATORS + 'Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00065/',
}
HOSTS = {urlparse(MUNICIPAL).hostname, urlparse(TRANSPARENCY).hostname}


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _check_pagination(soup):
    # These are document pages, not news searches. A new pager must not produce
    # a successful but incomplete snapshot. OpenCMS also exposes collector totals.
    if soup.select('.pagination a[href], [rel="next"], .pager a[href]'):
        raise ValueError('Unexpected pagination: document inventory requires review')
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        match = re.search(r'resultSize:\s*(\d+)', str(comment))
        if match:
            gallery = comment.find_parent(class_='sg-download-gallery')
            if gallery is None or int(match[1]) > len(gallery.select('tbody tr')):
                raise ValueError('Incomplete OpenCMS document collector')


def _documents(container, source):
    docs = {}
    for a in container.select('a[href]'):
        url = urljoin(source, a['href'])
        parsed = urlparse(url)
        if not parsed.path.lower().endswith('.pdf'):
            continue
        if parsed.scheme != 'https' or parsed.hostname not in HOSTS:
            raise ValueError('Unexpected document origin')
        title = _text(a)
        # The council's adaptation gallery contains an unrelated tax bulletin.
        if re.search(r'TASAS.VEHICULOS|PRECIOS.PISCINA|SOLICITUD|MODELO.DE', title, re.I):
            continue
        if not title:
            raise ValueError('Untitled planning document')
        docs.setdefault(url, {'titulo': title, 'url': url, 'source_url': source})
    if not docs:
        raise ValueError('No usable planning documents in expected inventory')
    return list(docs.values())


def parse_inventory(html: str, kind: str) -> list[dict]:
    """Parse only the verified document containers; never navigation or news."""
    source = SOURCES[kind]
    soup = BeautifulSoup(html, 'html.parser')
    _check_pagination(soup)
    if kind == 'consulta':
        heading = soup.select_one('h1')
        if not heading or 'Nuevo Plan Básico de Ordenación Municipal' not in _text(heading):
            raise ValueError('Missing municipal PBOM page')
        table = soup.select_one('table.table')
        if table is None:
            raise ValueError('Missing PBOM consultation documents')
        return [{'key': 'pbom', 'titulo': 'Plan Básico de Ordenación Municipal de Castilblanco de los Arroyos',
                 'documentos': _documents(table, source)}]
    article = soup.select_one('article.sg-indicador-trans')
    heading = article.select_one('h2.title') if article else None
    expected = 'Avance del Plan Basico' if kind == 'avance' else 'Plan General de Ordenación Urbana'
    if not heading or expected not in _text(heading):
        raise ValueError('Missing official planning indicator')
    if kind == 'avance':
        blocks = article.select('.contentblock')
        if not blocks:
            raise ValueError('Missing PBOM document blocks')
        # All the memories, maps, catalogue and procedural documents are one PBOM.
        docs = {}
        for block in blocks:
            for doc in _documents(block, source):
                docs.setdefault(doc['url'], doc)
        return [{'key': 'pbom', 'titulo': 'Plan Básico de Ordenación Municipal de Castilblanco de los Arroyos',
                 'documentos': list(docs.values())}]
    groups = []
    for gallery in article.select('section.gallery'):
        title = gallery.select_one('h4.gallery-title')
        if not title:
            continue
        label = _text(title)
        if label == 'ADAPTACION PARCIAL A LA LOUA DE NORMAS SUBSIDIARIAS':
            key = 'pgou-adaptacion-loua'
        elif 'Modificación nº1 Del PGOU' in label and 'Cementerio' in label:
            key = 'pgou-modificacion-1-cementerio'
        else:
            raise ValueError('Unrecognized planning gallery: ' + label)
        groups.append({'key': key, 'titulo': label, 'documentos': _documents(gallery, source)})
    if {g['key'] for g in groups} != {'pgou-adaptacion-loua', 'pgou-modificacion-1-cementerio'}:
        raise ValueError('Missing or changed PGOU instrument galleries')
    return groups


def build_records(inventories: dict[str, str]) -> list[dict]:
    grouped = {}
    for kind in SOURCES:
        for group in parse_inventory(inventories[kind], kind):
            key = group['key']
            if key not in grouped:
                grouped[key] = {
                    'id': SLUG + '-' + key, 'titulo': group['titulo'],
                    'municipio': 'Castilblanco de los Arroyos', 'codigo_ine': '41027',
                    'provincia': 'Sevilla', 'tipo': 'instrumento de planeamiento urbanístico',
                    'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
                    'url': SOURCES[kind], 'source_urls': [], 'documentos': [],
                    'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'geometry': None, 'lat': None, 'lon': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                    'coverage': 'Inventario documental parcial; no acredita vigencia ni aprobación definitiva del instrumento.',
                }
            row = grouped[key]
            if SOURCES[kind] not in row['source_urls']:
                row['source_urls'].append(SOURCES[kind])
            known = {d['url'] for d in row['documentos']}
            row['documentos'].extend(d for d in group['documentos'] if d['url'] not in known)
    return list(grouped.values())


class CastilblancoDeLosArroyosAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        inventories = {}
        captures = self.config.get('capture_dir')
        for kind, url in SOURCES.items():
            response = requests.get(url, timeout=45, headers={'User-Agent': 'municipal-planning-inventory/1.0'})
            response.raise_for_status()
            if response.url != url or 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Unexpected planning inventory response: ' + response.url)
            inventories[kind] = response.text
            if captures:
                directory = Path(captures)
                directory.mkdir(parents=True, exist_ok=True)
                (directory / (kind + '.html')).write_bytes(response.content)
        rows = build_records(inventories)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': list(SOURCES.values()),
                'coverage': 'current_partial_planning_document_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full snapshot of these finite inventories; never append duplicate plans.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
