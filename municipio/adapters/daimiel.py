"""Daimiel: current municipal POM document inventories, grouped by instrument."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.daimiel.es'
SOURCES = (
    BASE + '/es/transparencia-normativa-sobre-urbanismo-y-medio-ambiente',
    BASE + '/es/transparencia-normativa-y-documentos-en-tramitacion',
)
LIMITATIONS = [
    'Cobertura parcial: inventarios documentales del POM; no registro exhaustivo de expedientes u obras.',
    'Las categorías del portal pueden conservar documentos históricos en tramitación; no se infiere vigencia ni fase.',
    'Sin fechas de publicación/acuerdo verificadas ni geometría; las rutas del CMS no son fechas del instrumento.',
    'Licencias desactivadas; no se extraen formularios, contratación, noticias ni planes de emergencia.',
]
MODIFICATION = re.compile(r'^Modificaci[oó]n\s*(?:/\s*innovaci[oó]n\s*)?puntual\s*(?:n[º°o.]\s*)?(\d+)\b', re.I)


def parse_inventory(html: str, source_url: str) -> list[dict]:
    """Read Drupal text/file paragraph pairs; never treat each plan sheet as a project."""
    if source_url not in SOURCES:
        raise ValueError('Unsupported municipal inventory')
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('.pager, a[rel~=next], .pagination'):
        raise ValueError('Inventory pagination detected: review traversal before extraction')
    paragraphs = soup.select('.field--name-field-paragraphs > .field__item > .paragraph')
    if not paragraphs:
        raise ValueError('Missing Drupal inventory paragraphs')
    section = ''
    rows = {}
    for paragraph in paragraphs:
        if 'paragraph--type--text' in paragraph.get('class', []):
            section = paragraph.get_text(' ', strip=True)
            continue
        if 'paragraph--type--archivos-asociados' not in paragraph.get('class', []):
            continue
        for anchor in paragraph.select('.file a[href]'):
            title = anchor.get_text(' ', strip=True)
            match = MODIFICATION.match(title)
            if source_url == SOURCES[0] and section == 'Plan de Ordenación Municipal 2009':
                key = 'pom-2009'
            elif match and (section.startswith('Modificaciones al Plan de Ordenación Municipal')
                            or source_url == SOURCES[1]):
                key = 'pom-2009-mod-' + str(int(match.group(1)))
            elif (section.startswith('Modificaciones al Plan de Ordenación Municipal')
                  and title == 'Modificaciones al Plan de Ordenación Municipal'):
                # This is a summary document, not another instrument.
                key = 'pom-2009'
            else:
                continue
            url = urljoin(source_url, anchor['href'])
            parsed = urlparse(url)
            if (parsed.scheme != 'https' or parsed.hostname != 'www.daimiel.es'
                    or not parsed.path.startswith('/sites/default/files/')
                    or not parsed.path.lower().endswith('.pdf')):
                raise ValueError('Unexpected planning document URL: ' + url)
            row = rows.setdefault(key, {
                'id': 'daimiel-' + key, 'municipio': 'Daimiel', 'codigo_ine': '13039',
                'provincia': 'Ciudad Real',
                'titulo': ('Plan de Ordenación Municipal 2009' if key == 'pom-2009' else
                           'Modificación puntual nº ' + key.rsplit('-', 1)[1] + ' al POM Daimiel 2009'),
                'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
                'origen': 'inventario_documental_pom', 'url': source_url,
                'source_urls': [source_url], 'documentos': [],
                'publication_ready': False, 'geometry_status': 'unavailable',
            })
            row['documentos'].append({'titulo': title, 'url': url,
                                     'source_url': source_url, 'seccion': section})
    if not rows:
        raise ValueError('No POM instruments found in municipal inventory')
    return list(rows.values())


def merge_instruments(groups: list[list[dict]]) -> list[dict]:
    merged = {}
    for rows in groups:
        for row in rows:
            if row['id'] not in merged:
                merged[row['id']] = row
                continue
            target = merged[row['id']]
            for url in row['source_urls']:
                if url not in target['source_urls']:
                    target['source_urls'].append(url)
            for doc in row['documentos']:
                if doc not in target['documentos']:
                    target['documentos'].append(doc)
    return sorted(merged.values(), key=lambda row: row['id'])


class DaimielAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        groups = []
        capture_dir = self.config.get('capture_dir')
        for index, url in enumerate(SOURCES):
            response = requests.get(url, timeout=45, headers={
                'User-Agent': 'municipio-daimiel-inventory/1.0'})
            response.raise_for_status()
            if response.url.rstrip('/') != url:
                raise ValueError('Unexpected inventory redirect: ' + response.url)
            if capture_dir:
                capture = Path(capture_dir)
                capture.mkdir(parents=True, exist_ok=True)
                (capture / f'inventory-{index + 1}.html').write_text(response.text, encoding='utf-8')
            groups.append(parse_inventory(response.text, url))
        rows = merge_instruments(groups)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(output)
        return {'count': len(rows), 'live_records': len(rows), 'source_urls': list(SOURCES),
                'coverage': 'partial_current_pom_document_inventories', 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        raise NotImplementedError('Licencias disabled: no verified public grant inventory')

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
