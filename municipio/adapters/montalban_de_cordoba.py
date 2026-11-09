"""Document inventory of the municipal Urbanismo page; no inferred approvals."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://montalbandecordoba.es/ayuntamiento/'
          'ayuntamiento-informacion_municipal/ayuntamiento-informacion_municipal-urbanismo/')


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                   if not unicodedata.combining(c)).strip()


def parse_inventory(html, source_url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href]'):
        if ('next' in a.get('rel', []) or
                norm(a.get_text(' ', strip=True)) in {'siguiente', 'next', '»'} or
                re.search(r'(?:/page/\d|[?&](?:page|paged)=\d)', a['href'])):
            raise ValueError('Pagination detected: review inventory before extracting')
    if soup.select('.page-links a, .pagination a, .wp-pagenavi a'):
        raise ValueError('Paginated inventory is unsupported')
    groups = {}

    def add(title, kind, links):
        key = norm(title)
        row = groups.setdefault(key, {
            'id': 'montalban-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Montalbán de Córdoba', 'codigo_ine': '14040',
            'provincia': 'Córdoba', 'titulo': title, 'tipo': kind,
            'url': source_url, 'inventory_url': source_url,
            'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
            'publication_ready': False, 'geometry_status': 'unavailable',
            'documentos': [],
        })
        for a in links:
            url = urljoin(source_url, a['href'])
            parsed = urlparse(url)
            if (parsed.scheme != 'https' or parsed.hostname != 'montalbandecordoba.es'
                    or not parsed.path.startswith('/wp-content/uploads/')
                    or not parsed.path.lower().endswith('.pdf')):
                raise ValueError('Unexpected inventory document: ' + url)
            label = a.get_text(' ', strip=True)
            existing = next((d for d in row['documentos'] if d['url'] == url), None)
            if existing:
                if label not in existing['etiquetas']:
                    existing['etiquetas'].append(label)
            else:
                row['documentos'].append({'titulo': label, 'etiquetas': [label],
                                         'url': url, 'source_url': source_url})

    for block in soup.select('.carpetas_doc'):
        heading = block.select_one('.et_pb_toggle_title')
        if heading is None:
            heading = block.find_previous_sibling()
        if heading is None:
            raise ValueError('Inventory section lacks heading')
        title = heading.get_text(' ', strip=True)
        section = norm(title)
        links = block.select('a[href]')
        if section in {'casco urbano', 'infraestructuras', 'termino municipal'}:
            continue  # Base maps are not individual works or planning instruments.
        if not links:
            raise ValueError('Empty document section: ' + title)
        if section == 'normas subsidiarias':
            base = []
            for a in links:
                if norm(a.get_text(' ', strip=True)).startswith('innovacion-modificacion'):
                    add(a.get_text(' ', strip=True), 'modificacion_planeamiento', [a])
                else:
                    base.append(a)
            if not base:
                raise ValueError('Missing subsidiary planning documents')
            add('Normas subsidiarias de planeamiento', 'planeamiento_urbanistico', base)
        elif section.startswith('plan parcial '):
            add(title, 'plan_parcial', links)
        elif section == 'proyectos':
            for a in links:
                label = a.get_text(' ', strip=True)
                if not re.match(r'^PFEA \d{4}\. ', label):
                    raise ValueError('Unreviewed project label: ' + label)
                # Two parts of the same Calle Empedrada project, including its plans.
                instrument = re.sub(r'\s+(?:Primera|Segunda) Parte(?: Planos)?$', '', label,
                                    flags=re.I)
                add(instrument, 'proyecto_obra_publica', [a])
        else:
            raise ValueError('Unreviewed inventory section: ' + title)
    if not groups:
        raise ValueError('No planning/project inventory found')
    return list(groups.values())


class MontalbanDeCordobaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                        encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=45, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE.rstrip('/'):
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text)
        self.source_capture = response.text
        return {**self._write(out_jsonl, rows), 'source_urls': [SOURCE],
                'coverage': 'current_document_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot: no date-based cutoff or hidden pagination truncation.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
