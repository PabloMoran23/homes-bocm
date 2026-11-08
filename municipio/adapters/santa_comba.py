"""Physical works in the official POS+ inventory linked by Santa Comba."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE_URL = 'https://plan-unico.dacoruna.gal/santa-comba/'
MUNICIPAL_URL = 'https://www.santacomba.es/'
LIMITATIONS = [
    'Partial municipal coverage: only the published POS+ approved-investment inventory.',
    'Equipment supplies excluded; no licences, procurement notices or unrelated news.',
    'Exercicio is a budget year, not a publication or agreement date; neither date is supplied.',
    'Approval is reported by the inventory, without evidence of execution or completion.',
    'No project identifiers, technical documents or verified geometries are supplied by the table.',
    'IDs use budget year and normalized title; source title changes can change an ID.',
]


def normalize(text):
    return ' '.join(unicodedata.normalize('NFC', text).split())


def amount(text):
    value = text.replace('\xa0', '').replace(' ', '').replace('€', '')
    if not re.fullmatch(r'(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}', value):
        raise ValueError(f'Invalid source amount: {text!r}')
    return str(Decimal(value.replace('.', '').replace(',', '.')))


def parse_inventory(html, source_url=SOURCE_URL):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1')
    if not heading or normalize(heading.get_text(' ', strip=True)) != 'PLAN ÚNICO Santa Comba':
        raise ValueError('Unexpected municipality or inventory heading')
    # Full SSR table covers all years; never use the duplicate card presentation.
    selected = soup.select_one('#selector-exercicio option[selected]')
    if not selected or selected.get('value') != 'todos':
        raise ValueError('Inventory is filtered; all budget years are required')
    for link in soup.select('a[href], button'):
        label = normalize(link.get_text(' ', strip=True)).lower()
        rel = link.get('rel', [])
        if ('next' in rel or label in {'next', 'siguiente', 'seguinte', 'cargar máis', 'ver máis'}
                or link.get('aria-label', '').lower() in {'next', 'siguiente', 'seguinte'}):
            if not link.has_attr('disabled'):
                raise ValueError('Unexpected pagination; review crawler before extracting')
    tables = soup.select('table[aria-label="Lista de obras e investimentos"]')
    if len(tables) != 1:
        raise ValueError('Missing or ambiguous works table')
    table = tables[0]
    if [normalize(t.get_text(' ', strip=True)) for t in table.select('thead th')] != [
        'Exercicio', 'Obxecto', 'Orzamento', 'Aportación'
    ]:
        raise ValueError('Inventory schema changed')
    counter = soup.find('span', string=lambda t: t and t.strip() == 'Obras aprobadas')
    total = counter.find_parent('li').select_one('div.grow') if counter else None
    raw_rows = table.select('tbody tr')
    if not total or not total.get_text(strip=True).isdigit() or int(total.get_text(strip=True)) != len(raw_rows):
        raise ValueError('Incomplete inventory: table differs from published works count')
    rows = {}
    excluded = []
    for tr in raw_rows:
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 4:
            raise ValueError('Malformed investment row')
        year, title, budget, contribution = [normalize(c.get_text(' ', strip=True)) for c in cells]
        if not re.fullmatch(r'20\d{2}', year) or not title:
            raise ValueError('Invalid budget year or empty title')
        budget, contribution = amount(budget), amount(contribution)
        if re.match(r'^Subministración\b', title, re.I):
            excluded.append({'titulo': title, 'ejercicio': int(year), 'reason': 'equipment_supply'})
            continue
        if not re.match(r'^(?:Mell\.?|Mellora\b|Pav\.|Pavim\.|Pavimentación\b|Reforma\b|'
                        r'Reposición\b|Capa\b|Intervención\b|Nova rede\b|Reurbaniz|Depósito\b|'
                        r'Beirarrúas\b|Reparac|Afirmado\b|Reforzo\b|Abastec|Remodelación\b|'
                        r'Mant\.|Mantemento\b|Adecua\.)', title, re.I):
            raise ValueError(f'Unreviewed investment category: {title}')
        key = hashlib.sha256(f'{year}|{title.casefold()}'.encode()).hexdigest()[:20]
        documents = []
        for a in cells[1].select('a[href]'):
            doc = {'titulo': normalize(a.get_text(' ', strip=True)), 'url': urljoin(source_url, a['href'])}
            if doc not in documents:
                documents.append(doc)
        row = {
            'id': f'santa-comba-pos-{key}', 'municipio': 'Santa Comba', 'codigo_ine': '15077',
            'provincia': 'A Coruña', 'titulo': title, 'tipo': 'obra_publica',
            'ejercicio': int(year), 'presupuesto_eur': budget, 'aportacion_eur': contribution,
            'url': source_url, 'source': 'ayuntamiento', 'origen': 'inventario_oficial_pos_plus',
            'organismo_fuente': 'Deputación Provincial da Coruña',
            'estado_segun_fuente': 'Obras aprobadas', 'inventory_url': source_url,
            'documentos': documents, 'geometry_status': 'unavailable', 'publication_ready': False,
        }
        if key in rows and rows[key] != row:
            raise ValueError('Conflicting rows for the same budget year and title')
        rows[key] = row
    if not rows:
        raise ValueError('No physical works found')
    return list(rows.values()), {'inventory_rows': len(raw_rows), 'excluded': excluded}


class SantaCombaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE_URL, timeout=40, headers={
            'User-Agent': 'municipal-inventory-santa-comba/1.0'
        })
        response.raise_for_status()
        if response.url != SOURCE_URL:
            raise ValueError(f'Unexpected inventory redirect: {response.url}')
        rows, coverage = parse_inventory(response.text, response.url)
        self._write(out_jsonl, rows)
        if self.config.get('evidence_dir'):
            evidence = Path(self.config['evidence_dir'])
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / 'pos-live.html').write_text(response.text, encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE_URL],
                'limitations': LIMITATIONS, **coverage}

    def update_proyectos(self, out_jsonl, state_path):
        # The source has no change feed: refresh the complete current snapshot.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
