"""Santaella: live SITUA approved-plan inventory, one record per instrument.

The regional catalogue is partial municipal coverage. Its approval date describes
its catalogue entry, not necessarily the last resolution in the document bundle.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://ws132.juntadeandalucia.es/situadifusion/pages/'
SEARCH = BASE + 'search.jsf'
INVENTORY = BASE + 'figuras.jsf'
LIMITATIONS = [
    'Sólo consulta SITUA de planes aprobados para INE 14060; no inventario completo municipal ni licencias u obras.',
    'Fecha de aprobación del catálogo: puede corresponder a aprobación parcial y no al último acuerdo de los documentos.',
    'Documentos históricos incluyen La Guijarrosa; no se crean actuaciones independientes ni se atribuyen al término actual.',
    'Enlaces de descarga SITUA conservados tal como se publican; pueden necesitar sesión o fallar. No se verifica todo el contenido binario.',
    'Sin fechas de publicación inferidas, coordenadas o geometrías; actualización por nueva captura completa.',
]


def hidden_fields(html):
    soup = BeautifulSoup(html, 'html.parser')
    form = soup.find('form')
    if not form or not form.select_one('input[name="javax.faces.ViewState"]'):
        raise ValueError('SITUA form/ViewState missing')
    return form, {x['name']: x.get('value', '') for x in form.select('input[type=hidden][name]')}


def parse_page(payload):
    """Validate DataTables totals; caller must visit every server-side page."""
    total = int(payload['iTotalDisplayRecords'])
    rows = payload['aaData']
    if total < 0 or not isinstance(rows, list):
        raise ValueError('Invalid inventory page')
    parsed = []
    for cells in rows:
        if len(cells) != 8 or cells[0].strip() != 'CÓRDOBA' or cells[1].strip() != 'SANTAELLA':
            raise ValueError('Unexpected municipality or inventory schema')
        anchor = BeautifulSoup(cells[6], 'html.parser').select_one('a.docuPlan[name]')
        if not anchor or not re.fullmatch(r'\d+', anchor['name']):
            raise ValueError('Missing instrument identifier')
        parsed.append({'source_id': anchor['name'], 'figura': cells[2].strip(),
                       'fecha_aprob': datetime.strptime(cells[3], '%d/%m/%y').date().isoformat(),
                       'conforme_a': cells[4].strip()})
    return total, parsed


def parse_detail(html, instrument):
    soup = BeautifulSoup(html, 'html.parser')
    code = soup.select_one('input[name="codFigura"]')
    if not code or code.get('value') != instrument['source_id']:
        raise ValueError('Wrong instrument detail')
    fields = {}
    for label in soup.select('.area-filter-label'):
        value = label.find_parent('td').find_next_sibling('td')
        if value:
            fields[label.get_text(' ', strip=True).rstrip(':')] = value.get_text(' ', strip=True)
    if fields.get('Ámbito Territorial') != 'MUNICIPAL - Municipal SANTAELLA':
        raise ValueError('Detail territory mismatch')
    figure = fields.get('Figura', '')
    if not figure.startswith(instrument['figura'] + ' - '):
        raise ValueError('Detail figure mismatch')
    if fields.get('Fecha de Aprobación') != datetime.fromisoformat(instrument['fecha_aprob']).strftime('%d/%m/%y'):
        raise ValueError('Detail approval date mismatch')
    # mapa is a JSON literal supplied by SITUA, never executable JavaScript.
    script = next((s.get_text() for s in soup.select('script') if re.search(r'\bvar\s+mapa\s*=', s.get_text())), '')
    match = re.search(r'\bvar\s+mapa\s*=\s*', script)
    if not match:
        raise ValueError('Missing complete document map')
    entries, _ = json.JSONDecoder().raw_decode(script[match.end():].lstrip())
    docs = {}
    for entry in entries:
        a = BeautifulSoup(entry['enlace'], 'html.parser').select_one('a.descargaDoc[href]')
        if not a or not re.fullmatch(r'descargaDocumentos\.jsf\?doc=\d+', a['href']):
            raise ValueError('Unexpected document link')
        url = urljoin(BASE, a['href'])
        doc = docs.setdefault(url, {'titulo': entry['nombre'].strip(), 'url': url, 'grupos_fuente': []})
        if entry['clave'] not in doc['grupos_fuente']:
            doc['grupos_fuente'].append(entry['clave'])
    if not docs:
        raise ValueError('Instrument without source documents')
    return {
        'id': 'santaella-situa-' + instrument['source_id'],
        'municipio': 'Santaella', 'provincia': 'Córdoba', 'codigo_ine': '14060',
        'titulo': figure + ' — Santaella' + (' — ' + fields['Objeto'] if fields.get('Objeto') else ''),
        'tipo': 'planeamiento_urbanistico', 'fecha_aprob': instrument['fecha_aprob'],
        'fecha_aprob_alcance': 'fecha de la ficha SITUA, no último acuerdo ni vigencia consolidada',
        'estado_fuente': fields.get('Estado'), 'conforme_a': instrument['conforme_a'],
        'url': SEARCH, 'inventory_url': INVENTORY, 'source_id': instrument['source_id'],
        'source': 'junta_de_andalucia', 'origen': 'situa_planes_aprobados',
        'source_request': {'method': 'POST', 'url': INVENTORY, 'codigos': '14060'},
        'documentos': list(docs.values()), 'publication_ready': False,
        'geometry_status': 'unavailable', 'limitations': LIMITATIONS,
    }


class SantaellaAyuntamientoAdapter(AyuntamientoAdapter):
    def _open_inventory(self, session):
        initial = self._request(session, 'GET', SEARCH, 'situa-search.html')
        form, data = hidden_fields(initial.text)
        data.update({'municipiosseleccionados': '14060',
                     'munNomCod': json.dumps([{'id': '14060', 'nombre': 'Santaella'}]),
                     'radioButton': 'aprobado'})
        button = form.select_one('a[id$=":commandRedirige"]')
        if not button:
            raise ValueError('Missing search command')
        data[button['id']] = button['id']
        result = self._request(session, 'POST', urljoin(SEARCH, form['action']), 'situa-approved.html', data=data)
        _, fields = hidden_fields(result.text)
        if fields.get('codigosMunicipios') != '14060':
            raise ValueError('Search lost municipality filter')
        return result

    def _request(self, session, method, url, capture, **kwargs):
        if urlparse(url).hostname != urlparse(BASE).hostname:
            raise ValueError('Unexpected source host')
        r = session.request(method, url, timeout=40, **kwargs)
        r.raise_for_status()
        if urlparse(r.url).hostname != urlparse(BASE).hostname:
            raise ValueError('Unexpected redirect')
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir']) / capture
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
        return r

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-santaella-inventory/1.0'
            result = self._open_inventory(session)
            instruments = []
            expected = None
            while expected is None or len(instruments) < expected:
                offset = len(instruments)
                response = self._request(session, 'POST', INVENTORY, f'inventory-{offset}.json',
                                         data={'codigos': '14060', 'iDisplayStart': offset,
                                               'iDisplayLength': 8, 'sEcho': offset + 1})
                total, page = parse_page(response.json())
                if expected is not None and total != expected:
                    raise ValueError('Inventory changed during pagination')
                expected = total
                known = {p['source_id'] for p in instruments}
                if not page or any(p['source_id'] in known for p in page):
                    raise ValueError('Empty/repeated inventory page; refusing partial output')
                instruments.extend(page)
                if len({p['source_id'] for p in instruments}) != len(instruments) or len(instruments) > total:
                    raise ValueError('Inconsistent inventory totals/identifiers')
            rows = []
            for instrument in instruments:
                # Refresh JSF ViewState for each instrument, avoiding stale view reuse.
                if rows:
                    result = self._open_inventory(session)
                form, data = hidden_fields(result.text)
                button = form.select_one('a[id$=":tipoPlaneamiento"]')
                if not button:
                    raise ValueError('Missing document command')
                data.update({'codFigura': instrument['source_id'], button['id']: button['id']})
                detail = self._request(session, 'POST', urljoin(BASE, form['action']),
                                       f"instrument-{instrument['source_id']}.html", data=data)
                rows.append(parse_detail(detail.text, instrument))
        return self._write(out_jsonl, rows)

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SEARCH, INVENTORY],
                'coverage': 'situa_approved_plan_inventory', 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
