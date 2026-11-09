"""San Clemente (Cuenca): current municipal POM document inventory.

One record per numbered modification, not per map or downloadable document.
Document availability and legal currency are not implied by an inventory link.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.sanclemente.es/plan-de-ordenacion-municipal/'


def _normal(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn')


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    inventories = soup.select('ul.accordion-items')
    if len(inventories) != 1:
        raise ValueError('Expected one municipal planning accordion')
    inventory = inventories[0]
    # This source is a single page. Fail visibly if pagination appears.
    if soup.select('a[rel~=next], .pagination, .page-links, .nav-links'):
        raise ValueError('Pagination detected; review crawler before extracting')
    for a in inventory.select('a[href]'):
        if _normal(a.get_text(' ', strip=True)) in {'siguiente', 'next', 'ver mas', 'cargar mas'}:
            raise ValueError('Continuation link detected')
    records = {}
    for block in inventory.find_all('li', recursive=False):
        heading = block.select_one('h4.accordion-title')
        content = block.select_one('.accordion-content')
        if heading is None or content is None:
            raise ValueError('Planning section markup changed')
        title = heading.get_text(' ', strip=True)
        normalized = _normal(title)
        match = re.fullmatch(r'modificacion puntual n[º°o.]?\s*(\d+)\s+pom\s*-\s*(.+)', normalized)
        if not match:
            # Original POM sections only refer the reader to modification 1;
            # they have no documents and must not become duplicate records.
            if normalized.startswith('plan de ordenacion municipal -') and not content.select('a[href]'):
                continue
            raise ValueError(f'Unreviewed planning section: {title}')
        number = str(int(match[1]))
        docs = []
        for a in content.select('a[href]'):
            target = urljoin(source_url, a['href'])
            parsed = urlparse(target)
            if parsed.scheme != 'https' or parsed.hostname not in {
                'www.sanclemente.es', 'sanclemente.es', 'www.dipucuenca.es', 'mega.nz'
            }:
                raise ValueError(f'Unreviewed document host: {target}')
            label = a.get_text(' ', strip=True)
            if not label or target.rstrip('/') == source_url.rstrip('/'):
                raise ValueError('Invalid instrument document link')
            docs.append({'titulo': label, 'url': target, 'seccion': title,
                         'inventory_url': source_url,
                         'alojamiento': 'municipal' if parsed.hostname in {
                             'www.sanclemente.es', 'sanclemente.es'} else 'externo_enlazado_por_ayuntamiento'})
        if not docs:
            raise ValueError(f'No document links for {title}')
        row = records.setdefault(number, {
            'id': f'san-clemente-pom-mp-{number}',
            'municipio': 'San Clemente', 'provincia': 'Cuenca', 'codigo_ine': '16190',
            'titulo': f'Modificación puntual nº {number} del Plan de Ordenación Municipal de San Clemente',
            'tipo': 'modificacion_planeamiento', 'source': 'ayuntamiento',
            'origen': 'inventario_municipal_planeamiento',
            'url': source_url, 'inventory_url': source_url,
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'documentos': [], 'secciones_fuente': [],
            'coverage': 'Inventario documental actual del POM; no acredita vigencia ni ejecución de obras.',
        })
        row['secciones_fuente'].append(title)
        known = {doc['url'] for doc in row['documentos']}
        for doc in docs:
            if doc['url'] not in known:
                row['documentos'].append(doc)
                known.add(doc['url'])
    if not records:
        raise ValueError('No municipal planning instruments with documents')
    return list(records.values())


def _write(out_jsonl, rows):
    output = Path(out_jsonl)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    temporary.replace(output)


class SanClementeAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'municipio-san-clemente/1.0 (public planning inventory)'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in {'www.sanclemente.es', 'sanclemente.es'} or urlparse(response.url).path != urlparse(SOURCE).path:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        if self.config.get('capture_dir'):
            captures = Path(self.config['capture_dir'])
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'planeamiento-live.html').write_text(response.text, encoding='utf-8')
        _write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [response.url],
                'coverage': 'current_pom_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        _write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
