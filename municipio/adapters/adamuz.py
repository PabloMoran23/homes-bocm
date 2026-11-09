"""Adamuz: official SITUA approved general-planning inventory (partial coverage)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://ws132.juntadeandalucia.es/situadifusion/pages/'
SOURCE = ROOT + 'search.jsf'
LIMITATIONS = [
    'Solo consulta SITUA de planeamiento general aprobado de Adamuz; no inventario completo de modificaciones, desarrollo ni obras.',
    'Web municipal y transparencia devolvieron HTTP 403 durante la investigación.',
    'Fechas de aprobación según SITUA; sin fecha de publicación ni geometría verificadas.',
    'Documentos agrupados por código de instrumento; no se afirma concesión de licencia ni ejecución de obras.',
    'Descargas SITUA requieren sesión anónima tras abrir la ficha; el enlace aislado puede devolver una página de error HTTP 200.',
]


def parse_page(payload):
    """Validate a server-side DataTables page before advancing its offset."""
    total = payload['iTotalDisplayRecords']
    if not isinstance(total, int) or total < 0 or payload['iTotalRecords'] != total:
        raise ValueError('Unexpected filtered SITUA inventory')
    rows = []
    for cells in payload['aaData']:
        if len(cells) != 8 or cells[:2] != ['CÓRDOBA', 'ADAMUZ']:
            raise ValueError('Unexpected municipality or inventory schema')
        anchor = BeautifulSoup(cells[6], 'html.parser').select_one('a.docuPlan[name]')
        if not anchor or not re.fullmatch(r'\d+', anchor['name']):
            raise ValueError('Missing instrument identifier')
        rows.append({'situa_id': anchor['name'], 'figura': cells[2],
                     'fecha_aprob_raw': cells[3], 'conforme_a': cells[4]})
    return total, rows


def parse_documents(html, instrument):
    soup = BeautifulSoup(html, 'html.parser')
    code = soup.select_one('input[name="codFigura"]')
    muni = soup.select_one('input[name="codigosMunicipios"]')
    if not code or code.get('value') != instrument['situa_id'] or not muni or muni.get('value') != '14001':
        raise ValueError('Document response belongs to another instrument or municipality')
    fields = {}
    for label in soup.select('table.area-filters .area-filter-label'):
        cell = label.find_parent('td').find_next_sibling('td')
        if cell:
            fields[label.get_text(' ', strip=True).rstrip(':')] = cell.get_text(' ', strip=True)
    if ('ADAMUZ' not in fields.get('Ámbito Territorial', '') or
            not fields.get('Figura', '').startswith(instrument['figura'] + ' - ') or
            not fields.get('Objeto') or fields.get('Fecha de Aprobación') != instrument['fecha_aprob_raw']):
        raise ValueError('Instrument metadata missing or inconsistent')
    scripts = '\n'.join(s.get_text() for s in soup.select('script:not([src])'))
    match = re.search(r'\bvar\s+mapa\s*=\s*', scripts)
    if not match:
        raise ValueError('Missing complete document inventory')
    entries, _ = json.JSONDecoder().raw_decode(scripts[match.end():])
    docs = {}
    for entry in entries:
        a = BeautifulSoup(entry['enlace'], 'html.parser').select_one('a.descargaDoc[href]')
        if not a or not re.fullmatch(r'descargaDocumentos\.jsf\?doc=\d+', a['href']):
            raise ValueError('Unexpected document URL')
        url = urljoin(ROOT, a['href'])
        document = docs.setdefault(url, {'titulo': entry['nombre'], 'url': url, 'grupos_fuente': []})
        if entry['clave'] not in document['grupos_fuente']:
            document['grupos_fuente'].append(entry['clave'])
    # This hidden export contains ALL documents, not merely the selected tree node.
    export = soup.select_one('table[id$="tablaExporResult_table"]')
    if not docs or not export or len(export.select('tbody tr')) != len(docs):
        raise ValueError('Incomplete document inventory; review markup')
    approval = datetime.strptime(instrument['fecha_aprob_raw'], '%d/%m/%y').date().isoformat()
    return {
        'id': 'adamuz-situa-' + instrument['situa_id'], 'situa_id': instrument['situa_id'],
        'municipio': 'Adamuz', 'provincia': 'Córdoba', 'codigo_ine': '14001',
        'titulo': fields['Figura'] + ': ' + fields['Objeto'] + ' — Adamuz',
        'tipo': 'planeamiento_urbanistico', 'figura': instrument['figura'],
        'descripcion': fields['Objeto'], 'estado_fuente': fields.get('Estado'),
        'fecha_aprob': approval, 'fecha_publicacion': None,
        'fecha_aprob_provenance': 'SITUA: Fecha de Aprobación (listado y ficha coincidentes)',
        'url': SOURCE, 'inventory_url': SOURCE,
        'document_access': 'Abrir consulta anónima para 14001, seleccionar Documentos del Plan del codFigura y descargar en la misma sesión.',
        'source': 'junta_andalucia', 'origen': 'situa_planeamiento_general_aprobado',
        'source_request': {'municipiosseleccionados': '14001', 'radioButton': 'aprobado',
                           'codFigura': instrument['situa_id']},
        'documentos': list(docs.values()), 'coverage': LIMITATIONS[0],
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class AdamuzAyuntamientoAdapter(AyuntamientoAdapter):
    def _request(self, session, method, url, capture, **kwargs):
        if urlparse(url).hostname != urlparse(SOURCE).hostname:
            raise ValueError('Unexpected source host')
        r = session.request(method, url, timeout=40, **kwargs)
        r.raise_for_status()
        if urlparse(r.url).hostname != urlparse(SOURCE).hostname:
            raise ValueError('Unexpected source redirect')
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / capture).write_bytes(r.content)
        return r

    def _submit(self, session, html, page_url, changes, capture):
        soup = BeautifulSoup(html, 'html.parser')
        form = soup.select_one('form')
        if not form or not soup.select_one('input[name="javax.faces.ViewState"]'):
            raise ValueError('SITUA search form unavailable')
        data = {x['name']: x.get('value', '') for x in form.select('input[type="hidden"][name]')}
        data.update(changes)
        return self._request(session, 'POST', urljoin(page_url, form['action']), capture, data=data)

    def _search(self, session):
        page = self._request(session, 'GET', SOURCE, 'search.html')
        return self._submit(session, page.text, page.url, {
            'municipiosseleccionados': '14001',
            'munNomCod': json.dumps([{'id': '14001', 'nombre': 'Adamuz'}]),
            'radioButton': 'aprobado',
            'formulariomapa:commandRedirige': 'formulariomapa:commandRedirige',
        }, 'result.html')

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-adamuz/1.0 (public planning inventory)'
            self._search(session)
            instruments, seen, offset, expected = [], set(), 0, None
            while True:
                response = self._request(session, 'POST', ROOT + 'figuras.jsf', f'figuras-{offset}.json',
                    data={'codigos': '14001', 'iDisplayStart': offset, 'iDisplayLength': 10, 'sEcho': offset + 1})
                total, page = parse_page(response.json())
                if expected is not None and total != expected:
                    raise ValueError('Inventory changed during pagination')
                expected = total
                if not page or offset + len(page) > total:
                    raise ValueError('Empty or inconsistent inventory page')
                for item in page:
                    if item['situa_id'] in seen:
                        raise ValueError('Repeated instrument across pages')
                    seen.add(item['situa_id'])
                    instruments.append(item)
                offset += len(page)
                if offset == total:
                    break
            rows = []
            for item in instruments:
                result = self._search(session)
                soup = BeautifulSoup(result.text, 'html.parser')
                command = soup.find('a', id=re.compile(r':tipoPlaneamiento$'))
                if not command:
                    raise ValueError('Missing document navigation')
                detail = self._submit(session, result.text, result.url,
                    {'codFigura': item['situa_id'], command['id']: command['id']},
                    'instrument-' + item['situa_id'] + '.html')
                rows.append(parse_documents(detail.text, item))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'source_urls': [SOURCE, ROOT + 'figuras.jsf'], 'limitations': LIMITATIONS,
                'coverage': 'SITUA approved general planning', 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
