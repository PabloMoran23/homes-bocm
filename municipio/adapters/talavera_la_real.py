"""Talavera la Real planning inventory from the official Extremadura SITEX."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://sitex.juntaex.es'
LANDING = BASE + '/SITEX/planeamiento'
INVENTORY = BASE + '/SITEX/ptofiguras/listadoresultadossigcat'
LIMITATIONS = [
    'Cobertura del árbol público SITEX para Talavera la Real; no inventario de todas las obras ni licencias.',
    'Incluye figuras vigentes, no vigentes y en trámite según SITEX; no se certifica su vigencia jurídica.',
    'Documentos y boletines enlazados, sin interpretar el contenido de todos los PDF.',
    'Sin geometrías verificadas. La web municipal presentó error de certificado TLS durante la investigación.',
    'Las fechas principales son exclusivamente Fecha AD y Fecha de publicación AD; otros hitos permanecen en tramites.',
    'Referencias raíz sin número (PGM, PDSU, NNSS) pueden quedar pendientes en el clasificador compartido.',
]


def text(node):
    return node.get_text(' ', strip=True) if node else ''


def check_pagination(soup):
    # The observed source is a fully expanded tree, not a paged table. Fail if
    # pagination appears in a future version rather than silently taking page 1.
    if soup.select('.paging, .pagination, .paginator, a[rel="next"], a[rel="last"]'):
        raise ValueError('Unexpected SITEX pagination; extraction would be incomplete')


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    selected = soup.select_one('#PtofiguraMunicipio option[selected][value="176"]')
    if text(selected) != 'Talavera la Real':
        raise ValueError('SITEX did not select Talavera la Real (internal municipality 176)')
    entries = {}
    for a in soup.select('a.unenlaceafiguradeplaneamiento'):
        match = re.search(r"addTab\('(/SITEX/ptofiguras/viewsigcat/(\d+))','Talavera la Real - ([^']+)'\)", a.get('onclick', ''))
        if not match or not a.get('title'):
            raise ValueError('Unrecognized SITEX planning tree entry')
        entry = {'url': urljoin(BASE, match[1]), 'sitex_id': match[2],
                 'referencia': match[3], 'titulo_inventario': ' '.join(a['title'].split())}
        if match[2] in entries and entries[match[2]] != entry:
            raise ValueError('Conflicting SITEX identifiers')
        entries[match[2]] = entry
    if not entries:
        raise ValueError('Empty or changed SITEX planning inventory')
    return list(entries.values())


def iso_date(value):
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat() if value else None


def parse_detail(html, entry):
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    fields = {}
    for tr in soup.select('table.juntaex tr'):
        th, td = tr.find('th', recursive=False), tr.find('td', recursive=False)
        if th and td:
            fields[text(th)] = text(td)
    if fields.get('Ámbito territorial') != 'Talavera la Real':
        raise ValueError('Wrong municipality in SITEX detail')
    if fields.get('Referencia') != entry['referencia'] or not fields.get('Figura urbanística') or not fields.get('Estado'):
        raise ValueError('Missing or conflicting planning identity in SITEX detail')
    events = []
    event_table = soup.select_one('#tablaCalificacionplaneamientostramit')
    if event_table is None:
        raise ValueError('Missing SITEX procedure table')
    documents = {}
    for tr in event_table.select('tr[id^="filatramite"]'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 2:
            raise ValueError('Changed SITEX procedure row')
        event = {'fecha': iso_date(text(cells[0])), 'tramite': text(cells[1]), 'documentos': []}
        for a in cells[1].select('a[href]'):
            url = urljoin(entry['url'], a['href'])
            doc = {'url': url, 'titulo': text(a), 'procedencia': entry['url']}
            documents[url] = doc
            event['documentos'].append(url)
        events.append(event)
    # Document panels are embedded in the detail HTML, including collapsed ones.
    for a in soup.select('a[href*="/ptofiguras/downloaddocumento/"]'):
        url = urljoin(entry['url'], a['href'])
        documents[url] = {'url': url, 'titulo': a.get('download') or text(a.find_parent('tr')),
                          'procedencia': entry['url']}
    title = re.sub(r'\s*-\s*\(fecha publicación A\.D\.\s*:.*\)\s*$', '', entry['titulo_inventario'])
    return {
        'id': 'talavera-la-real-sitex-' + entry['sitex_id'],
        'municipio': 'Talavera la Real', 'codigo_ine': '06128', 'provincia': 'Badajoz',
        'titulo': title + ' [' + entry['referencia'] + ']',
        'tipo': fields['Figura urbanística'], 'referencia': entry['referencia'],
        'expediente': entry['referencia'], 'categoria': 'planeamiento urbanístico',
        'estado_fuente': fields['Estado'], 'sitex_id': entry['sitex_id'],
        'fecha': None, 'fecha_acuerdo': None,
        'fecha_aprob': iso_date(fields.get('Fecha AD', '')),
        'fecha_publicacion': iso_date(fields.get('Fecha de publicación AD', '')),
        'fecha_deposito': iso_date(fields.get('Fecha de depósito', '')),
        'numero_deposito': fields.get('Nº de depósito') or None,
        'diario_publicacion': fields.get('Diario de publicación AD') or None,
        'tramites': events, 'documentos': list(documents.values()),
        'url': entry['url'], 'inventory_url': INVENTORY,
        'inventory_request': {'method': 'POST', 'data': {'municipioseleccionado': '176'}},
        'source': 'junta_extremadura', 'origen': 'SITEX',
        'source_organismo': 'Junta de Extremadura',
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class TalaveraLaRealAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or LANDING)

    def _fetch(self, session, url, name, data=None):
        response = session.post(url, data=data, timeout=45) if data is not None else session.get(url, timeout=45)
        response.raise_for_status()
        if urlparse(response.url).hostname != 'sitex.juntaex.es':
            raise ValueError('Unexpected SITEX redirect')
        response.encoding = 'utf-8'
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / name).write_bytes(response.content)
        return response.text

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-talavera-la-real/1.0 (public planning inventory)'
            landing = BeautifulSoup(self._fetch(session, LANDING, 'landing.html'), 'html.parser')
            if text(landing.select_one('#PtofiguraMunicipio option[value="176"]')) != 'Talavera la Real':
                raise ValueError('SITEX municipality mapping changed')
            entries = parse_inventory(self._fetch(session, INVENTORY, 'inventory.html', {'municipioseleccionado': '176'}))
            rows = [parse_detail(self._fetch(session, entry['url'], 'detail-' + entry['sitex_id'] + '.html'), entry)
                    for entry in entries]
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        # No partial output when a detail request or identity validation fails.
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'live_records': len(rows), 'count': len(rows),
                'source_urls': [LANDING, INVENTORY] + [e['url'] for e in entries],
                'limitations': LIMITATIONS, 'coverage': 'complete_observed_SITEX_municipal_tree',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'count': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
