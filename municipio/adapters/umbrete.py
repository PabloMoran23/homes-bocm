"""Documented instruments from Umbrete's official transparency inventories."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://transparencia.umbrete.es'
PREFIX = ROOT + '/es/transparencia/indicadores-de-transparencia/indicador/'
SOURCES = {
    '50': PREFIX + 'Plan-General-de-Ordenacion-Municipal-PGOM/',
    '53': PREFIX + 'Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00022/',
    '55': PREFIX + 'Usos-y-destinos-del-suelo-00022/',
}
CATEGORIES = {'MODIFICACIONES DE LAS NNSS APROBADAS.', 'PLANES PARCIALES APROBADOS',
              'OTROS INSTRUMENTOS DE PLANEAMIENTO APROBADOS'}
LIMITATIONS = [
    'Partial municipal coverage: indicators 50, 53 and 55 only; indicator 54, works, news and procurement are outside this adapter.',
    'Current published document inventory, not a complete historical register or a legal determination of validity.',
    'Instrument headings without usable PDF documents are omitted and reported; pending referrals to indicator 54 are not imported.',
    'No structured publication, agreement or approval dates inferred from titles, filenames or CMS metadata.',
    'Document links retained; PDF contents are not parsed. No coordinates or granted licences extracted.',
]


def clean(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def parse_inventory(html: str, source_url: str, indicator: str):
    """Return grouped instruments and explicitly reported documentless headings."""
    if source_url != SOURCES[indicator]:
        raise ValueError('Unexpected source URL')
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href]'):
        if (a.get('rel') and 'next' in a['rel']) or clean(a).lower() in {
            'siguiente', 'siguiente página', 'next', '›', '»'
        } or a.find_parent(class_=re.compile(r'pag(?:ination|inacion|er)', re.I)):
            if a['href'] not in {'', '#'}:
                raise ValueError('Pagination detected; refusing incomplete inventory')
    article = soup.select_one('article.sg-indicador-trans')
    if article is None:
        raise ValueError('Missing municipal indicator article')
    groups = []
    current = None
    for node in article.select('h3, h4.gallery-title, a[href]'):
        title = clean(node)
        if node.name == 'h3':
            current = None
            if title.upper() in CATEGORIES:
                continue
            if not re.match(r'^(ADAPTACIÓN PARCIAL|PLAN GENERAL DE ORDENACIÓN MUNICIPAL|PLAN MUNICIPAL DE VIVIENDA Y SUELO)\b', title, re.I):
                raise ValueError('Unreviewed instrument section: ' + title)
            current = {'titulo': title, 'documentos': {}, 'referencia': title}
            groups.append(current)
        elif node.name == 'h4':
            if indicator == '53' and re.match(r'^(EXPTE\.|PLAN PARCIAL)\s', title, re.I):
                current = {'titulo': title, 'documentos': {}, 'referencia': title}
                groups.append(current)
            elif indicator == '55' and current and title.upper().startswith('EXPTE.'):
                current['referencia'] = title
        elif urlparse(node['href']).path.lower().endswith('.pdf'):
            target = urljoin(source_url, node['href'])
            if current is None:
                raise ValueError('PDF outside an instrument group')
            if urlparse(target).hostname != urlparse(ROOT).hostname or not urlparse(target).path.startswith('/export/sites/umbrete/'):
                raise ValueError('Unexpected document provenance: ' + target)
            if not title:
                raise ValueError('Document without label')
            media = node.find_parent(class_='media')
            current['documentos'].setdefault(target, {
                'titulo': title, 'url': target, 'source_url': source_url,
                'texto_fuente': clean(media) if media else title,
            })
    rows, omitted = [], []
    for group in groups:
        if not group['documentos']:
            omitted.append(group['titulo'])
            continue
        ref = re.search(r'EXPTE\.?\s*([0-9][A-Z0-9_/]*)', group['referencia'], re.I)
        identity = ref.group(1) if ref else group['referencia']
        rows.append({
            'id': 'umbrete-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:20],
            'municipio': 'Umbrete', 'provincia': 'Sevilla', 'codigo_ine': '41094',
            'titulo': group['titulo'], 'tipo': 'instrumento o proyecto urbanístico',
            'url': source_url, 'inventory_url': source_url, 'indicador': indicator,
            'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
            'documentos': list(group['documentos'].values()),
            'publication_ready': False, 'geometry_status': 'unavailable',
            'source_entity_type': 'expediente' if ref else 'documento',
            **({'expediente': ref.group(1)} if ref else {}),
        })
    if not rows:
        raise ValueError('No documented instruments found')
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate instrument identity')
    return rows, omitted


class UmbreteAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        rows, omitted = [], {}
        capture = self.config.get('capture_dir')
        for indicator, url in SOURCES.items():
            response = requests.get(url, timeout=45, headers={
                'User-Agent': 'MunicipalDocumentInventory/1.0 (public planning research)',
            })
            response.raise_for_status()
            if response.url != url:
                raise ValueError('Unexpected source redirect: ' + response.url)
            if capture:
                folder = Path(capture)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / ('indicador-' + indicator + '.html')).write_text(response.text, encoding='utf-8')
            parsed, missing = parse_inventory(response.text, url, indicator)
            rows.extend(parsed)
            omitted[indicator] = missing
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate instruments across inventories')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(output)
        return {'count': len(rows), 'source_urls': list(SOURCES.values()),
                'omitted_without_documents': omitted, 'limitations': LIMITATIONS,
                'coverage': 'current_document_inventory_indicators_50_53_55'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        raise NotImplementedError('Licences disabled: no verified public grant register')

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
