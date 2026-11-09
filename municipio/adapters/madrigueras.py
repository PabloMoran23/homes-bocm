"""Named physical FEDER operations in the municipal announcements inventory.

Coverage is intentionally limited to structured operation disclosures, not the
licence register or a complete inventory of municipal works.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://madrigueras.es/anuncios/'
LIMITATIONS = [
    'Partial coverage: only structured physical FEDER operations on Anuncios.',
    'No verified granted-licence register; licences disabled.',
    'No publication/agreement/approval dates, geometry or current execution status verified.',
    'Funding programme years and operation-code years are not event dates.',
    'The live operation has an HTML disclosure, without a linked technical project PDF.',
]


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    # This inventory is currently a single accordion, not a paginated news feed.
    # Fail rather than silently produce partial data if navigation is introduced.
    for a in soup.select('a[href]'):
        rel = a.get('rel', [])
        label = a.get_text(' ', strip=True).casefold()
        if ('next' in rel or label in {'siguiente', 'next', '»', '›'}
                or a.find_parent(class_=re.compile(r'pagination|nav-links'))):
            if a['href'] not in {'', '#'}:
                raise ValueError('Inventory pagination detected; crawler needs review')
    blocks = soup.select('.elementor-accordion-item .elementor-tab-content')
    if not blocks:
        raise ValueError('Municipal announcement accordion missing')
    rows = {}
    for block in blocks:
        lines = [' '.join(line.split()) for line in block.get_text('\n', strip=True).splitlines()]
        text = '\n'.join(lines)
        if not re.search(r'^OPERACIÓN\s*:', text, re.M | re.I):
            continue
        # Do not turn grants, services, generic notices or procurement into works.
        if not ('FEDER' in text.upper() and re.search(r'\bobras\b', text, re.I)):
            continue
        def field(label):
            matches = re.findall(r'^' + label + r'\s*:\s*(.+)$', text, re.M | re.I)
            if len(matches) != 1:
                raise ValueError('Missing or ambiguous operation field: ' + label)
            return matches[0]
        title = field('OPERACIÓN')
        if not (re.search(r'\bMADRIGUERAS\b', title, re.I)
                and re.search(r'INFRAESTRUCTURAS|CONSTRUCCIÓN|REHABILITACIÓN|URBANIZACIÓN', title, re.I)):
            continue
        code = field('CÓDIGO DE LA OPERACIÓN')
        if not re.fullmatch(r'[A-Z0-9]+(?:/[A-Z0-9]+)+', code):
            raise ValueError('Unexpected operation identifier')
        cost = field('COSTE TOTAL DE LA OPERACIÓN')
        if not re.fullmatch(r'[\d.]+,\d{2}\s*€', cost):
            raise ValueError('Unexpected operation cost')
        section_url = url + ('#' + block['id'] if block.get('id') else '')
        documents = [{'titulo': 'Ficha municipal de la operación', 'url': section_url,
                      'formato': 'text/html', 'source_url': url}]
        for a in block.select('a[href]'):
            target = urljoin(url, a['href'])
            if urlparse(target).scheme in {'http', 'https'} and not a['href'].startswith('#'):
                documents.append({'titulo': a.get_text(' ', strip=True) or 'Documento enlazado',
                                  'url': target, 'source_url': section_url})
        row = {
            'id': 'madrigueras-obra-' + hashlib.sha256(code.encode()).hexdigest()[:16],
            'municipio': 'Madrigueras', 'codigo_ine': '02045', 'provincia': 'Albacete',
            'titulo': title, 'tipo': 'obra_publica', 'codigo_operacion': code,
            'url': section_url, 'inventory_url': url, 'source': 'ayuntamiento',
            'origen': 'publicidad_operaciones_feder',
            'coste_total_operacion_eur': cost.replace('€', '').strip(),
            'cofinanciacion': field('COFINANCIACIÓN'), 'documentos': documents,
            'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'partial_structured_feder_operations',
        }
        if code in rows:
            previous = rows[code]
            if any(previous[k] != row[k] for k in ('titulo', 'coste_total_operacion_eur', 'cofinanciacion')):
                raise ValueError('Conflicting disclosures for operation ' + code)
            for doc in documents:
                if doc not in previous['documentos']:
                    previous['documentos'].append(doc)
        else:
            rows[code] = row
    if not rows:
        raise ValueError('No supported named physical operations; source needs review')
    return list(rows.values())


class MadriguerasAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(out_jsonl, rows):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(output)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl: Path):
        response = requests.get(SOURCE, timeout=40, headers={'User-Agent': 'municipio-madrigueras/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != 'madrigueras.es':
            raise ValueError('Unexpected inventory redirect')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected municipal HTML inventory')
        rows = parse_inventory(response.text, response.url)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'anuncios-live.html').write_bytes(response.content)
        return {**self._write(out_jsonl, rows), 'source_urls': [response.url],
                'limitations': LIMITATIONS, 'coverage': 'partial_structured_feder_operations'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full refresh of the small current inventory. No date watermark or truncation.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {**self._write(out_jsonl, []), 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
