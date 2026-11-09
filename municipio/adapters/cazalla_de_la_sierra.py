"""Two official document inventories; one record per named planning instrument."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

PBOM_URL = 'https://www.cazalladelasierra.es/pbom/'
PGOU_URL = ('https://transparencia.cazalladelasierra.es/es/transparencia/'
            'indicadores-de-transparencia/indicador/50.-Esta-publicado-el-Plan-General-'
            'de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00016/')
LIMITATIONS = [
    'Cobertura parcial: PBOM y adaptación parcial a la LOUA de las NNSS; no es un histórico completo.',
    'No incluye modificaciones sin identificación individual, PEPCH, obras ni licencias concedidas.',
    'La fase del PBOM es el texto de la web; no acredita aprobación ni vigencia legal.',
    'Sin fechas de publicación, acuerdo o aprobación verificadas; sin coordenadas.',
    'Los enlaces documentales se inventarían desde HTML; no se valida cada PDF en cada ejecución.',
]


def checked_soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # These inventories are single-page. Fail explicitly if their navigation changes.
    if soup.select('[rel~=next], .pagination a[href], .page-numbers, .load-more, [data-next-page]'):
        raise ValueError('Paginated inventory detected; refusing partial coverage')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', 'cargar más', 'ver más'} and a['href'] not in {'', '#'}:
            raise ValueError('Additional inventory page detected')
    return soup


def documents(container, url, path_prefix):
    docs = {}
    for a in container.select('a[href]'):
        target = urldefrag(urljoin(url, a['href']))[0]
        parsed = urlparse(target)
        if (parsed.scheme != 'https' or parsed.hostname not in {
                'www.cazalladelasierra.es', 'cazalladelasierra.es',
                'transparencia.cazalladelasierra.es'}
                or not parsed.path.startswith(path_prefix)
                or not parsed.path.lower().endswith('.pdf')):
            continue
        label = a.get_text(' ', strip=True)
        panel = a.find_parent(class_='vc_tta-panel') or a.find_parent('section', class_='gallery')
        heading = panel.select_one('.vc_tta-panel-title, .gallery-title') if panel else None
        reference = {'titulo': label, 'seccion': heading.get_text(' ', strip=True) if heading else None}
        doc = docs.setdefault(target, {'titulo': label, 'url': target, 'inventory_url': url, 'referencias': []})
        if reference not in doc['referencias']:
            doc['referencias'].append(reference)
    if not docs:
        raise ValueError('Inventory has no supported source documents')
    return list(docs.values())


def record(key, title, url, docs):
    return {'id': 'cazalla-de-la-sierra-plan-' + key,
            'municipio': 'Cazalla de la Sierra', 'codigo_ine': '41032', 'provincia': 'Sevilla',
            'titulo': title, 'tipo': 'planeamiento_urbanistico', 'url': url,
            'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
            'documentos': docs, 'publication_ready': False, 'geometry_status': 'unavailable'}


def parse_pgou(html, url=PGOU_URL):
    soup = checked_soup(html)
    content = soup.select_one('.contentblock1 .galleries')
    if content is None:
        raise ValueError('Missing PGOU galleries')
    heading = content.select_one('.gallery-title')
    title = heading.get_text(' ', strip=True) if heading else ''
    if not re.search(r'ADAPTACIÓN PARCIAL.*LOUA.*NNSS', title, re.I):
        raise ValueError('Unrecognized planning instrument')
    return record('adaptacion-nnss-loua', title, url,
                  documents(content, url, '/export/sites/cazalla/es/transparencia/.galleries/IMG-50-/'))


def pbom_document_url(html, url=PBOM_URL):
    soup = checked_soup(html)
    for a in soup.select('#main a[href]'):
        target = urldefrag(urljoin(url, a['href']))[0]
        if urlparse(target).hostname == 'www.cazalladelasierra.es' and urlparse(target).path == '/pbom-documentos/':
            return target
    raise ValueError('PBOM documentation inventory link missing')


def parse_pbom(html, documents_html, documents_url, url=PBOM_URL):
    main = checked_soup(html).select_one('#main')
    inventory = checked_soup(documents_html).select_one('#main')
    if main is None or inventory is None or not inventory.select('.vc_tta-panel'):
        raise ValueError('Missing PBOM content/panels')
    text = main.get_text(' ', strip=True)
    if 'PBOM' not in text or 'Cazalla' not in text:
        raise ValueError('Unrecognized PBOM page')
    row = record('pbom', 'Plan Básico de Ordenación Municipal (PBOM) de Cazalla de la Sierra', url,
                 documents(inventory, documents_url, '/wp-content/uploads/'))
    row['inventory_url'] = documents_url
    phase = re.search(r'Estamos en la\s+FASE\s+\d+', text, re.I)
    if phase:
        row['fase'] = phase.group(0)
        row['fase_source_url'] = url
    return row


class CazallaDeLaSierraAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-inventory/1.0'})
        response.raise_for_status()
        if urldefrag(response.url)[0] != url:
            raise ValueError('Unexpected source redirect: ' + response.url)
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected HTML inventory')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            name = 'pgou' if url == PGOU_URL else ('pbom' if url == PBOM_URL else 'pbom-documentos')
            (path / (name + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        pgou = parse_pgou(self._fetch(PGOU_URL))
        pbom_html = self._fetch(PBOM_URL)
        doc_url = pbom_document_url(pbom_html)
        pbom = parse_pbom(pbom_html, self._fetch(doc_url), doc_url)
        result = self._write(out_jsonl, [pgou, pbom])
        return {**result, 'source_urls': [PGOU_URL, PBOM_URL, doc_url],
                'coverage': 'partial_current_planning_document_inventories', 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Rebuild the complete current snapshot, including document changes/removals.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
