"""Municipal planning instruments from the official Junta de Extremadura inventory."""
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
INVENTORY = BASE + '/SITEX/ptofiguras/listadoresultadossigcat'
NAME = 'Quintana de la Serena'
LIMITATIONS = [
    'Only municipal instruments marked Vigente or En trámite in SITEX; historical and territorial plans excluded.',
    'Not a complete inventory of public works, projects or granted licences.',
    'SITEX metadata is informational; linked official publications retain documentary provenance.',
    'No inferred agreement dates, coordinates or geometry; document contents are not parsed.',
]


def checked_soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('.paging, .pagination, a[rel~=next]') or any(
        re.search(r'\b(siguiente|next)\b', a.get_text(' ', strip=True), re.I)
        for a in soup.select('a[href]') if a['href'] not in ('', '#')
    ):
        raise ValueError('Unexpected pagination: review crawler before extracting')
    return soup


def parse_inventory(html):
    soup = checked_soup(html)
    selected = soup.select_one('select option[selected]:not([value=""])')
    if not selected or selected.get('value') != '154' or selected.get_text(strip=True) != NAME:
        raise ValueError('Inventory municipality mismatch')
    links = soup.select('a.unenlaceafiguradeplaneamiento')
    if not links:
        raise ValueError('Missing planning inventory')
    ids = []
    for a in links:
        action = a.get('onclick', '')
        # The site also includes regional plans in this municipal tree.
        if not re.search(r"Quintana de la Serena - (?:PGM|NNSS|PDSU)(?:[.'\s])", action):
            continue
        image = a.find('img')
        state = image.get('alt') if image else None
        if state == 'No vigente':
            continue
        if state not in ('Vigente', 'En trámite'):
            raise ValueError('Unknown planning status')
        match = re.search(r"addTab\('/SITEX/ptofiguras/viewsigcat/(\d+)'", action)
        if not match:
            raise ValueError('Unrecognized instrument link')
        if match[1] not in ids:
            ids.append(match[1])
    if not ids:
        raise ValueError('No active municipal instruments')
    return ids


def parse_detail(html, instrument_id):
    soup = checked_soup(html)
    info = soup.select_one('#infoplaneamiento' + instrument_id)
    if info is None:
        raise ValueError('Missing instrument detail')
    fields = {}
    for tr in info.select('tr'):
        label, value = tr.find('th'), tr.find('td')
        if label and value:
            fields[label.get_text(' ', strip=True)] = value.get_text(' ', strip=True)
    if fields.get('Ámbito territorial') != NAME:
        raise ValueError('Detail municipality mismatch')
    if fields.get('Estado') not in ('Vigente', 'En trámite'):
        raise ValueError('Instrument no longer active; refresh inventory')
    if not fields.get('Figura urbanística') or not fields.get('Referencia'):
        raise ValueError('Missing instrument identity')
    url = BASE + '/SITEX/ptofiguras/viewsigcat/' + instrument_id
    row = {
        'id': 'quintana-de-la-serena-plan-' + instrument_id,
        'municipio': NAME, 'codigo_ine': '06109', 'provincia': 'Badajoz',
        'titulo': fields['Figura urbanística'], 'referencia': fields['Referencia'],
        'tipo': 'planeamiento_urbanistico', 'estado_fuente': fields['Estado'],
        'url': url, 'inventory_url': INVENTORY,
        'source': 'ayuntamiento', 'organismo_fuente': 'Junta de Extremadura — SITEX',
        'origen': 'inventario_oficial_planeamiento_municipal',
        'publication_ready': False, 'geometry_status': 'unavailable',
    }
    for label, key in [('Fecha AD', 'fecha_aprob'), ('Fecha de publicación AD', 'fecha_publicacion')]:
        if fields.get(label):
            row[key] = datetime.strptime(fields[label], '%d/%m/%Y').date().isoformat()
    row['metadatos_fuente'] = fields
    docs = {}
    for container, kind in [(info, 'publicacion_tramite'),
                            (soup.select_one('#archivosplaneamiento' + instrument_id), 'documento_planeamiento')]:
        if container is None:
            continue
        for a in container.select('a[href]'):
            target = urljoin(url, a['href'])
            if urlparse(target).scheme not in ('http', 'https') or a['href'].startswith('#'):
                continue
            title = a.get('download') or a.get_text(' ', strip=True)
            if not title:
                raise ValueError('Untitled source document')
            docs.setdefault(target, {'titulo': title, 'url': target, 'tipo': kind, 'source_url': url})
    row['documentos'] = list(docs.values())
    return row


class QuintanaDeLaSerenaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, capture, *, data=None):
        response = session.request('POST' if data else 'GET', url, data=data, timeout=45)
        response.raise_for_status()
        if urlparse(response.url).hostname != 'sitex.juntaex.es':
            raise ValueError('Unexpected source redirect')
        if self.config.get('evidence_dir'):
            folder = Path(self.config['evidence_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / capture).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'rows': len(rows), 'count': len(rows), 'status': 'ok'}

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'municipal-planning-inventory/1.0',
                                    'X-Requested-With': 'XMLHttpRequest'})
            ids = parse_inventory(self._fetch(session, INVENTORY, 'inventory.html',
                                              data={'municipioseleccionado': '154'}))
            rows = [parse_detail(self._fetch(session, BASE + '/SITEX/ptofiguras/viewsigcat/' + i,
                                            'instrument-' + i + '.html'), i) for i in ids]
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [INVENTORY] + [r['url'] for r in rows],
                'limitations': LIMITATIONS, 'coverage': 'active_municipal_planning_inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        # Refresh the whole current inventory; do not mistake changed status for a new licence.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
