"""Cortegana: SITUA's current approved general-planning inventory (partial scope)."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://ws132.juntadeandalucia.es/situadifusion/pages/'
INVENTORY = BASE + 'figuras.jsf'


def instrument_url(code):
    query = ('municipiosseleccionados=21025&codigosMunicipios=21025&codFigura='
             + str(code) + '&checkBoxSel=aprobado')
    return BASE + 'documentosCompartir.jsf?' + base64.b64encode(query.encode()).decode()


def parse_inventory(payload):
    """Validate one server-side DataTables page, without guessing its contents."""
    total = int(payload['iTotalDisplayRecords'])
    if total != int(payload['iTotalRecords']) or total < 0:
        raise ValueError('Unexpected filtered inventory totals')
    rows = []
    for cells in payload['aaData']:
        if len(cells) != 8 or cells[0].strip().upper() != 'HUELVA' or cells[1].strip().upper() != 'CORTEGANA':
            raise ValueError('Unexpected municipality or inventory schema')
        link = BeautifulSoup(cells[6], 'html.parser').select_one('a[name]')
        if not link or not re.fullmatch(r'\d+', link['name']):
            raise ValueError('Missing instrument identifier')
        rows.append({'codigo_fuente': link['name'], 'figura_fuente': cells[2],
                     'fecha_aprobacion_fuente': cells[3], 'conforme_a_fuente': cells[4]})
    return total, rows


def parse_instrument(html, code):
    soup = BeautifulSoup(html, 'html.parser')
    fields = {}
    for label in soup.select('.area-filter-label'):
        cell = label.find_parent('td')
        value = cell.find_next_sibling('td') if cell else None
        if value:
            fields[label.get_text(' ', strip=True).rstrip(':')] = value.get_text(' ', strip=True)
    if fields.get('Ámbito Territorial') != 'MUNICIPAL - Municipal CORTEGANA':
        raise ValueError('Detail page is not a Cortegana municipal instrument')
    if not fields.get('Figura') or not fields.get('Objeto'):
        raise ValueError('Missing instrument metadata')
    # All tree branches are embedded in mapa, including documents hidden by the UI.
    scripts = '\n'.join(s.get_text() for s in soup.select('script:not([src])'))
    match = re.search(r'\bvar\s+mapa\s*=\s*', scripts)
    if not match:
        raise ValueError('Missing complete document map')
    entries, _ = json.JSONDecoder().raw_decode(scripts[match.end():])
    documents = {}
    for entry in entries:
        a = BeautifulSoup(entry['enlace'], 'html.parser').select_one('a[href]')
        if not a:
            raise ValueError('Document without link')
        url = urljoin(BASE, a['href'])
        if urlparse(url).hostname != urlparse(BASE).hostname or not re.fullmatch(
            r'/situadifusion/pages/descargaDocumentos\.jsf\?doc=\d+',
            urlparse(url).path + '?' + urlparse(url).query,
        ):
            raise ValueError('Unexpected document URL')
        doc = documents.setdefault(url, {'titulo': entry['nombre'], 'url': url, 'grupos_fuente': []})
        if entry['clave'] not in doc['grupos_fuente']:
            doc['grupos_fuente'].append(entry['clave'])
    if not documents:
        raise ValueError('Instrument has no source documents')
    return {'id': 'cortegana-situa-' + str(code), 'codigo_ine': '21025',
            'municipio': 'Cortegana', 'provincia': 'Huelva',
            'titulo': fields['Figura'] + ' — ' + fields['Objeto'],
            'tipo': 'planeamiento_urbanistico', 'url': instrument_url(code),
            'source': 'junta_de_andalucia', 'origen': 'situa_planeamiento_general_aprobado',
            'inventory_url': INVENTORY, 'inventory_query': {'codigos': '21025'},
            'metadatos_fuente': fields, 'documentos': list(documents.values()),
            'document_access': 'Open instrument URL in the same HTTP session before downloading documents',
            'publication_ready': False, 'geometry_status': 'unavailable'}


class CorteganaAyuntamientoAdapter(AyuntamientoAdapter):
    def _request(self, session, method, url, capture, **kwargs):
        response = session.request(method, url, timeout=45, **kwargs)
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(BASE).hostname:
            raise ValueError('Unexpected source redirect')
        if self.config.get('capture_dir'):
            target = Path(self.config['capture_dir']) / capture
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
        return response

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-cortegana/1.0 (public planning inventory)'
            inventory, total, start, seen = [], None, 0, set()
            while total is None or start < total:
                response = self._request(session, 'POST', INVENTORY, f'inventory-{start}.json', data={
                    'codigos': '21025', 'iDisplayStart': start, 'iDisplayLength': 8,
                    'sEcho': start + 1, 'iColumns': 8,
                })
                page_total, page = parse_inventory(response.json())
                if total is not None and page_total != total:
                    raise ValueError('Inventory changed during pagination')
                total = page_total
                if not page or start + len(page) > total:
                    raise ValueError('Empty or inconsistent inventory page')
                for item in page:
                    code = item['codigo_fuente']
                    if code in seen:
                        raise ValueError('Repeated instrument during pagination')
                    seen.add(code)
                    inventory.append(item)
                start += len(page)
            rows = []
            for item in inventory:
                code = item['codigo_fuente']
                response = self._request(session, 'GET', instrument_url(code), f'instrument-{code}.html')
                row = parse_instrument(response.text, code)
                row.update(item)
                rows.append(row)
        return self._write(out_jsonl, rows)

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)
        return {'count': len(rows), 'written': len(rows), 'coverage': 'approved_general_planning_only'}

    def update_proyectos(self, out_jsonl, state_path):
        # Full current snapshot; no date cursor that could omit older instruments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
