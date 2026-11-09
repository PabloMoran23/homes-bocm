"""Almogía: live SITU@ approved general planning inventory and its documents.

The manifest's ayuntamiento source selects the portal pipeline; the actual
publisher is explicitly the Junta de Andalucía in each output record.
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

SOURCE = 'https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf'
INVENTORY = urljoin(SOURCE, 'figuras.jsf')
LIMITATIONS = [
    'Solo planeamiento general municipal aprobado devuelto por SITU@ para INE 29011; '
    'no cubre todas las modificaciones, planeamiento de desarrollo ni obras públicas.',
    'Estado Vigente según el inventario, sin certificación independiente de vigencia legal.',
    'Las fechas de publicación y de las correcciones no se infieren de la fecha de aprobación '
    'del instrumento ni de la actualización del portal.',
    'Sin licencias concedidas ni geometrías verificadas. Los enlaces de descarga pueden '
    'requerir abrir primero la ficha compartida en una sesión anónima.',
]


def official_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != urlparse(SOURCE).hostname:
        raise ValueError('Unexpected SITU@ URL')
    return url


def text(html):
    return BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)


def parse_inventory_page(payload):
    """Parse every row of a server-side DataTables page; never filter silently."""
    total = int(payload['iTotalDisplayRecords'])
    if total != int(payload['iTotalRecords']) or total < 1:
        raise ValueError('Empty or unexpectedly filtered planning inventory')
    rows = []
    for cells in payload['aaData']:
        if len(cells) != 8 or text(cells[0]) != 'MÁLAGA' or text(cells[1]) != 'ALMOGÍA':
            raise ValueError('Unexpected inventory schema or municipality')
        if text(cells[2]) != 'NNSS':
            raise ValueError('New planning figure requires semantic review')
        link = BeautifulSoup(cells[6], 'html.parser').select_one('a[name]')
        if not link or not re.fullmatch(r'\d+', link['name']):
            raise ValueError('Missing instrument identifier')
        rows.append({'situadifusion_id': link['name'], 'figura': text(cells[2]),
                     'fecha_aprob': datetime.strptime(text(cells[3]), '%d/%m/%y').date().isoformat()})
    return rows, total


def parse_documents(html, instrument):
    soup = BeautifulSoup(html, 'html.parser')
    identity = soup.select_one('input[name="codFigura"]')
    if not identity or identity.get('value') != instrument['situadifusion_id']:
        raise ValueError('Instrument identity missing or mismatched')
    metadata = {}
    for label in soup.select('.area-filters .area-filter-label'):
        value = label.parent.find_next_sibling('td')
        if value:
            metadata[label.get_text(' ', strip=True).rstrip(':')] = value.get_text(' ', strip=True)
    if metadata.get('Ámbito Territorial') != 'MUNICIPAL - Municipal ALMOGÍA':
        raise ValueError('Document page is not municipal Almogía planning')
    if metadata.get('Figura') != 'NNSS - Normas Subsidiarias Municipales':
        raise ValueError('Unexpected planning figure')
    approved = datetime.strptime(metadata['Fecha de Aprobación'], '%d/%m/%y').date().isoformat()
    if approved != instrument['fecha_aprob']:
        raise ValueError('Conflicting approval dates')
    # This JSON array feeds all client-side document pages/tree nodes. Parsing
    # only the visible HTML table would silently lose most attachments.
    scripts = '\n'.join(s.get_text() for s in soup.select('script:not([src])'))
    match = re.search(r'\bvar\s+mapa\s*=\s*', scripts)
    if not match:
        raise ValueError('Missing complete document inventory')
    entries, _ = json.JSONDecoder().raw_decode(scripts[match.end():])
    documents = {}
    for entry in entries:
        a = BeautifulSoup(entry['enlace'], 'html.parser').select_one('a[href]')
        if not a or not re.fullmatch(r'descargaDocumentos\.jsf\?doc=\d+', a['href']):
            raise ValueError('Unexpected document link')
        url = official_url(urljoin(SOURCE, a['href']))
        doc = documents.setdefault(url, {'titulo': entry['nombre'].strip(), 'url': url,
                                         'clasificaciones_fuente': []})
        if entry['clave'] not in doc['clasificaciones_fuente']:
            doc['clasificaciones_fuente'].append(entry['clave'])
    if not documents:
        raise ValueError('Instrument has no source documents')
    return {
        'id': 'almogia-situa-' + instrument['situadifusion_id'],
        'situadifusion_id': instrument['situadifusion_id'],
        'municipio': 'Almogía', 'codigo_ine': '29011', 'provincia': 'Málaga',
        'titulo': metadata['Figura'] + ' de Almogía — ' + metadata.get('Objeto', ''),
        'tipo': 'planeamiento_general', 'fecha_aprob': approved,
        'estado_fuente': metadata.get('Estado'), 'metadatos_fuente': metadata,
        'inventory_url': INVENTORY, 'inventory_params': {'codigos': '29011'},
        'source': 'junta_de_andalucia', 'organismo_publicador': 'Junta de Andalucía',
        'origen': 'situadifusion_planeamiento_general_aprobado',
        'documentos': list(documents.values()),
        'publication_ready': False, 'geometry_status': 'unavailable',
        'limitaciones': LIMITATIONS,
    }


class AlmogiaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, method, url, **kwargs):
        response = session.request(method, official_url(url), timeout=45, **kwargs)
        response.raise_for_status()
        official_url(response.url)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            self._capture_index += 1
            (directory / f'live-{self._capture_index:03d}.txt').write_text(response.text, encoding='utf-8')
        return response

    def _submit(self, session, response, extra):
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.select_one('form')
        if not form:
            raise ValueError('Missing JSF form')
        fields = {i['name']: i.get('value', '') for i in form.select('input[type=hidden][name]')}
        fields.update(extra)
        return self._fetch(session, 'POST', urljoin(response.url, form['action']), data=fields)

    @staticmethod
    def _command(html, selector):
        link = BeautifulSoup(html, 'html.parser').select_one(selector)
        if not link:
            raise ValueError('SITU@ navigation command missing')
        match = re.search(r"\{'([^']+)':'[^']+'\}", link.get('onclick', ''))
        if not match:
            raise ValueError('SITU@ navigation command changed')
        return {match[1]: match[1]}

    def backfill_proyectos(self, out_jsonl):
        self._capture_index = 0
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-almogia-inventory/1.0'
            response = self._fetch(session, 'GET', SOURCE)
            command = self._command(response.text, 'a[id$=":commandRedirige"]')
            listing = self._submit(session, response, {
                **command, 'municipiosseleccionados': '29011',
                'munNomCod': json.dumps([{'id': '29011', 'nombre': 'Almogía'}]),
                'radioButton': 'aprobado',
            })
            instruments, expected, start = [], None, 0
            seen = set()
            while True:
                page = self._fetch(session, 'POST', INVENTORY, data={
                    'codigos': '29011', 'iDisplayStart': str(start),
                    'iDisplayLength': '8', 'sEcho': str(start + 1), 'iColumns': '8',
                })
                batch, total = parse_inventory_page(page.json())
                if expected is not None and total != expected:
                    raise ValueError('Inventory changed during pagination; retry snapshot')
                expected = total
                if not batch or any(r['situadifusion_id'] in seen for r in batch):
                    raise ValueError('Empty or repeated inventory page before completion')
                for row in batch:
                    if row['situadifusion_id'] in seen:
                        raise ValueError('Duplicate instrument within page')
                    seen.add(row['situadifusion_id'])
                instruments.extend(batch)
                start += len(batch)
                if start == expected:
                    break
                if start > expected:
                    raise ValueError('Inventory exceeds declared total')
            records = []
            for instrument in instruments:
                command = self._command(listing.text, 'a[id$=":tipoPlaneamiento"]')
                detail = self._submit(session, listing, {**command, 'codFigura': instrument['situadifusion_id']})
                row = parse_documents(detail.text, instrument)
                # Obtain the site's own public share link (not a session URL).
                soup = BeautifulSoup(detail.text, 'html.parser')
                button = soup.select_one('img[title="Compartir url"]')
                if not button:
                    raise ValueError('Missing public instrument share command')
                command = self._command(str(button.parent), 'a')
                shared = self._submit(session, detail, command)
                share = BeautifulSoup(shared.text, 'html.parser').select_one('input[name="urlACompartir"]')
                if not share or not share.get('value'):
                    raise ValueError('Missing public instrument URL')
                row['url'] = official_url(''.join(share['value'].split()))
                records.append(row)
        result = self._write(out_jsonl, records)
        return {**result, 'live_records': len(records), 'source_urls': [SOURCE, INVENTORY],
                'coverage': 'approved_general_planning_inventory', 'limitations': LIMITATIONS}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
