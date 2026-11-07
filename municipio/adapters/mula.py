"""Snapshot of named instruments and works in Mula's official urbanism inventory."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://mula.es/web/'
INDEX = ROOT + 'urbanismo-y-patrimonio/'
PGMO = INDEX + 'plan-general-municipal-de-ordenacion/'
MODS = INDEX + 'modificaciones-pgmo/'
SINGLES = {
    ROOT + 'urbanismo-y-patrimonio/plan-especial-proteccion-revitalizacion-conjunto/':
        'Plan Especial de Protección y Revitalización del Conjunto Histórico',
    ROOT + 'urbanismo-y-patrimonio/modificacion-puntual-del-plan-parcial-el-arreaque/':
        'Modificación Puntual del Plan Parcial El Arreaque',
    ROOT + 'urbanismo-y-patrimonio/plan-director-mula/':
        'Plan Director del Castillo de Mula',
}
SOURCES = (INDEX, PGMO, MODS, *SINGLES)
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
LIMITATIONS = [
    'Partial snapshot of six municipal inventory pages; not a complete works or planning register.',
    'No granted-licence register extracted; forms, procurement and general news excluded.',
    'Document URLs and labels are municipal provenance, not verification of PDF contents or legal validity. External Drive files are not downloaded.',
    'PGMO map index retained as a link; individual map sheets and GIS geometry not extracted.',
    'Dates only from explicit document labels; no dates inferred from upload paths, BORM URL years or page timestamps.',
    'No verified geometry or coordinates; publication_ready is false.',
]


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('.post-content')
    if body is None:
        raise ValueError('Missing municipal inventory content')
    # These are static inventories. A new pagination mechanism needs review,
    # never an unnoticed first-page-only extraction.
    if soup.select('a[rel~="next"], .pagination, .page-numbers, .nav-next'):
        raise ValueError('Unexpected pagination: inventory traversal needs review')
    return body


def documents(anchors, source):
    docs = {}
    for a in anchors:
        href = a.get('href', '')
        if not href or href.startswith('#'):
            continue
        url = urljoin(source, href)
        parsed = urlparse(url)
        allowed = parsed.hostname in {'mula.es', 'borm.es', 'www.borm.es', 'drive.google.com',
                                     'visoriderm.carm.es', 'mapas-gis-inter.carm.es'}
        label = a.get_text(' ', strip=True)
        if not allowed or parsed.scheme != 'https' or not label:
            raise ValueError('Unexpected document link in inventory')
        key = (url, label)
        doc = {'titulo': label, 'url': url, 'source_url': source,
               'verification': 'municipal_link_only'}
        match = re.search(r'Aprobado por el Pleno en sesión (\d{1,2}) de (\w+) de (\d{4})', label, re.I)
        if match and match[2].lower() in MONTHS:
            doc['fecha_acuerdo'] = date(int(match[3]), MONTHS.index(match[2].lower()) + 1, int(match[1])).isoformat()
        docs[key] = doc
    if not docs:
        raise ValueError('Named instrument has no document links')
    return list(docs.values())


def record(key, title, source, docs, tipo='instrumento de planeamiento'):
    return {
        'id': 'mula-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
        'municipio': 'Mula', 'codigo_ine': '30029', 'provincia': 'Murcia',
        'titulo': title, 'tipo': tipo, 'url': source, 'inventory_url': INDEX,
        'source': 'ayuntamiento', 'origen': 'inventario_urbanismo_municipal',
        'documentos': docs, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


def parse_page(html, source):
    body = content(html)
    if source == MODS:
        rows = []
        for panel in body.select('.fusion-panel'):
            heading = panel.select_one('.fusion-toggle-heading')
            links = panel.select('.panel-body a[href]')
            title = heading.get_text(' ', strip=True) if heading else ''
            match = re.match(r'Modificación nº\s*(\d+)\b', title)
            if not match:
                raise ValueError('Unrecognized PGMO modification group')
            rows.append(record('pgmo-mod-' + match[1], title, source, documents(links, source)))
        if not rows or len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Missing or duplicate modification groups')
        return rows
    if source == PGMO:
        if 'PGMO actualmente en vigor' not in body.get_text(' ', strip=True):
            raise ValueError('Missing current PGMO inventory')
        # This page also repeats the special plan, extracted from its own page.
        anchors = []
        special = False
        for el in body.find_all(['h2', 'a']):
            if el.name == 'h2' and el.get_text(strip=True):
                special = 'Plan Especial de Protección' in el.get_text()
            elif el.name == 'a' and not special:
                anchors.append(el)
        return [record('pgmo', 'Plan General Municipal de Ordenación de Mula', source,
                       documents(anchors, source))]
    if source in SINGLES:
        # Each dedicated page describes exactly one instrument with its annexes.
        if source.endswith('plan-director-mula/') and 'Plan Director' not in body.get_text():
            raise ValueError('Missing Plan Director inventory')
        if 'el-arreaque' in source and 'Acuerdo pleno modificación puntual plan parcial El Arreaque' not in body.get_text():
            raise ValueError('Missing Arreaque instrument evidence')
        if 'plan-especial-' in source and 'Normativa (Plan Especial' not in body.get_text():
            raise ValueError('Missing special-plan inventory')
        return [record(source, SINGLES[source], source, documents(body.select('a[href]'), source))]
    if source == INDEX:
        links = [a for a in body.select('a[href]') if
                 a.get_text(' ', strip=True).startswith('Proyecto obras de excavación y protección de acceso al Castillo de Mula')]
        docs = documents(links, source)
        if len(docs) != 1 or urlparse(docs[0]['url']).hostname != 'drive.google.com':
            raise ValueError('Missing or ambiguous castle works project')
        return [record('castillo-excavacion-acceso', docs[0]['titulo'], source, docs, 'proyecto de obras')]
    raise ValueError('Unsupported inventory source')


class MulaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='mula', config=None, base_url=''):
        super().__init__(slug, config, base_url or INDEX)

    def backfill_proyectos(self, out_jsonl: Path):
        rows = []
        captures = self.config.get('capture_dir')
        for index, source in enumerate(SOURCES):
            response = requests.get(source, timeout=40, headers={
                'User-Agent': 'municipio-mula-inventory/1.0'})
            response.raise_for_status()
            if response.url.rstrip('/') != source.rstrip('/'):
                raise ValueError('Unexpected source redirect')
            if 'html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Expected HTML inventory')
            # Municipal pages declare UTF-8; avoid requests' ISO-8859-1 fallback.
            html = response.content.decode('utf-8-sig')
            if captures:
                target = Path(captures)
                target.mkdir(parents=True, exist_ok=True)
                (target / f'inventory-{index}.html').write_text(html, encoding='utf-8')
            rows.extend(parse_page(html, source))
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate instruments across inventories')
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'source_urls': list(SOURCES),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
