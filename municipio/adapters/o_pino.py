"""O Pino: complete approved-works inventory from Deputación da Coruña POS+."""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://plan-unico.dacoruna.gal/o-pino/'
LIMITATIONS = [
    'Only approved works in the provincial POS+ inventory; not all municipal works or planning.',
    'Exercise is a budget year, not a publication, agreement or completion date.',
    'No individual project files, approval dates, execution status or coordinates supplied.',
    'Source has no work identifiers: IDs use exercise and normalized title; title changes change IDs.',
]


def _text(value):
    return ' '.join(value.split())


def _astro(value):
    """Decode only the plain object/array/string subset used by the inventory."""
    tag, payload = value
    if tag == 0:
        if isinstance(payload, dict):
            return {key: _astro(item) for key, item in payload.items()}
        return payload
    if tag == 1:
        return [_astro(item) for item in payload]
    raise ValueError('Unsupported inventory serialization')


def _money(value, localized=False):
    if localized:
        value = re.sub(r'[\s€]', '', value).replace('.', '').replace(',', '.')
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('Invalid inventory amount') from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError('Invalid inventory amount')
    return format(amount.quantize(Decimal('.01')), 'f')


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1')
    if not heading or _text(heading.get_text(' ', strip=True)) != 'PLAN ÚNICO O Pino':
        raise ValueError('Wrong municipality inventory heading')
    # A future pagination change must fail instead of accepting only the first page.
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        rel = a.get('rel', [])
        if ('next' in rel or re.search(r'\b(next|siguiente|seguinte|páxina|página)\b', label)
                or re.search(r'(?:[?&](?:page|paged)=|/page/)', a['href'])):
            raise ValueError('Inventory pagination requires review')
    islands = soup.select('astro-island[component-url*="CmpObrasEjercicio"]')
    if len(islands) != 1:
        raise ValueError('Missing complete works data')
    municipality = _astro(json.loads(islands[0]['props'])['municipio'])
    if municipality['dir3'] != 'L01150660' or municipality['nombreOficial'] != 'O Pino':
        raise ValueError('Wrong inventory municipality identity')
    expected = []
    for year, exercise in municipality['ejercicios'].items():
        if year == 'todos' and not exercise.get('obras'):
            continue  # Financial totals across exercises, not another works page.
        if not re.fullmatch(r'20\d{2}', year):
            raise ValueError('Invalid budget exercise')
        for work in exercise['obras']:
            expected.append((year, _text(work['denominacion']),
                             _money(work['presupuesto']), _money(work['importeAprobado'])))
    tables = soup.select('table[aria-label="Lista de obras e investimentos"]')
    if len(tables) != 1:
        raise ValueError('Missing works table')
    actual = []
    for tr in tables[0].select('tbody tr'):
        cells = [td.get_text(' ', strip=True) for td in tr.select('td')]
        if len(cells) != 4 or not cells[1]:
            raise ValueError('Malformed work row')
        actual.append((cells[0], _text(cells[1]), _money(cells[2], True), _money(cells[3], True)))
    if not expected or Counter(expected) != Counter(actual):
        raise ValueError('Incomplete or inconsistent works inventory')
    selector = soup.select_one('#selector-exercicio')
    if selector is None:
        raise ValueError('Missing exercise selector')
    years = {o.get('value') for o in selector.select('option')} - {'todos'}
    if years != set(municipality['ejercicios']) - {'todos'}:
        raise ValueError('Incomplete exercise coverage')
    rows = {}
    for year, title, budget, contribution in actual:
        key = hashlib.sha256(f'{year}|{title.casefold()}'.encode()).hexdigest()[:20]
        row = {
            'id': 'o-pino-pos-' + key, 'municipio': 'O Pino', 'codigo_ine': '15066',
            'provincia': 'A Coruña', 'titulo': title, 'tipo': 'obra_publica',
            'ejercicio': int(year), 'presupuesto_eur': budget,
            'aportacion_deputacion_eur': contribution, 'moneda': 'EUR',
            'url': SOURCE, 'inventory_url': SOURCE, 'source': 'diputacion',
            'organismo_fuente': 'Deputación Provincial da Coruña',
            'origen': 'plan_unico_pos_obras_aprobadas',
            'estado_fuente': 'Obras aprobadas',
            'documentos': [{'titulo': 'Plan Único O Pino — inventario de obras aprobadas',
                            'url': SOURCE, 'tipo': 'inventario_html'}],
            'geometry_status': 'unavailable', 'publication_ready': False,
        }
        if key in rows and rows[key] != row:
            raise ValueError('Conflicting works with the same exercise and title')
        rows[key] = row
    return list(rows.values())


class OPinoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'MunicipalInventory/1.0 (O Pino public works research)'})
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(SOURCE).hostname or urlparse(response.url).path != '/o-pino/':
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text)
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'pos-live.html').write_text(response.text, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'live_records': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'coverage': 'all works and exercises in current POS+ inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
