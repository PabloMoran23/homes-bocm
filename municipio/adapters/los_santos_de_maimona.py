"""Los Santos de Maimona: current planning instruments in the official SITEX registry.

Only instruments explicitly marked Vigente are included. This is a snapshot of
regional registry metadata, not a licence register or a public works feed.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://sitex.juntaex.es'
DISCOVERY_URL = ROOT + '/SITEX/planeamiento'
INVENTORY_URL = ROOT + '/SITEX/ptofiguras/listadoresultadossigcat'
MUNICIPALITY = 'Santos de Maimona, Los'
LIMITATIONS = [
    'Only instruments marked Vigente in SITEX; excludes En trámite and No vigente.',
    'Regional planning registry snapshot; no municipal works or granted licences.',
    'Dates and document labels are registry metadata, not independently inferred from PDFs.',
    'Some approval dates are absent; registry publication fields can differ from linked DOE events.',
    'Document links retained; full technical documents and real instrument geometries are not extracted.',
]


def _no_pagination(soup):
    for a in soup.select('a'):
        label = a.get_text(' ', strip=True).lower()
        if ('next' in a.get('rel', []) or label in {'siguiente', 'next', '>', '»', 'mostrar más'}
                or any(c in a.get('class', []) for c in ('next', 'nextLink'))):
            raise ValueError('Pagination appeared: inventory must be reviewed before extraction')
    if soup.select('.paging, .pagination, .paginator'):
        raise ValueError('Unexpected pagination controls')


def parse_municipality(html):
    soup = BeautifulSoup(html, 'html.parser')
    choices = [o for o in soup.select('#PtofiguraMunicipio option')
               if o.get_text(' ', strip=True) == MUNICIPALITY]
    if len(choices) != 1 or not str(choices[0].get('value', '')).isdigit():
        raise ValueError('Municipality selector missing or ambiguous')
    return choices[0]['value']


def parse_inventory(html, municipality_id):
    soup = BeautifulSoup(html, 'html.parser')
    _no_pagination(soup)
    # SITEX also marks its empty placeholder selected; validate the nonempty choice.
    selected = [o for o in soup.select('#PtofiguraMunicipio option[selected]') if o.get('value')]
    if (len(selected) != 1 or selected[0].get('value') != municipality_id
            or selected[0].get_text(' ', strip=True) != MUNICIPALITY):
        raise ValueError('Inventory is not scoped to Los Santos de Maimona')
    entries = soup.select('a.unenlaceafiguradeplaneamiento')
    if not entries:
        raise ValueError('Planning inventory empty or structure changed')
    ids = {}
    for a in entries:
        image = a.find('img')
        status = image.get('alt') if image else None
        if status not in {'Vigente', 'No vigente', 'En trámite', 'En contratación'}:
            raise ValueError('Unknown instrument status')
        if status != 'Vigente':
            continue
        match = re.search(r"addTab\('(/SITEX/ptofiguras/viewsigcat/(\d+))','Santos de Maimona, Los - ", a.get('onclick', ''))
        if not match:
            raise ValueError('Unrecognized current instrument link')
        ids[match[2]] = ROOT + match[1]
    if not ids:
        raise ValueError('No current planning instruments; manual review required')
    return ids


def _date(value):
    if not value:
        return None
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


def parse_detail(html, key, url, municipality_id):
    soup = BeautifulSoup(html, 'html.parser')
    area = soup.select_one('#divplaneamiento' + key)
    info = soup.select_one('#infoplaneamiento' + key)
    if not area or not info:
        raise ValueError('Missing instrument detail ' + key)
    _no_pagination(area)
    fields = {}
    for tr in info.select('tr'):
        th = tr.find('th', recursive=False)
        td = tr.find('td', recursive=False)
        if th and td:
            fields[th.get_text(' ', strip=True)] = td.get_text(' ', strip=True)
    scope_ids = info.select_one('.campoconidsdemunicipiosparamapa')
    if (fields.get('Ámbito territorial') != MUNICIPALITY or not scope_ids
            or scope_ids.get_text(strip=True) != municipality_id or fields.get('Estado') != 'Vigente'):
        raise ValueError('Instrument municipality or status mismatch ' + key)
    title = fields.get('Figura urbanística', '')
    reference = fields.get('Referencia', '')
    if not title or not reference:
        raise ValueError('Missing instrument identity ' + key)
    events = []
    for tr in info.select('[id^=listadotramitesplaneamiento] tr[id^=filatramite]'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 2:
            raise ValueError('Unexpected event row')
        events.append({'fecha': _date(cells[0].get_text(strip=True)),
                       'tramite': cells[1].get_text(' ', strip=True)})
    documents = {}
    for a in area.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        technical = parsed.hostname == 'sitex.juntaex.es' and re.fullmatch(r'/SITEX/ptofiguras/downloaddocumento/\d+', parsed.path)
        bulletin = parsed.hostname == 'doe.juntaex.es' and parsed.path.lower().endswith('.pdf')
        if not (technical or bulletin):
            continue
        title_doc = a.get('download') or a.get_text(' ', strip=True)
        if not title_doc:
            raise ValueError('Document without source label')
        documents[target] = {'titulo': title_doc, 'url': target, 'provenance_url': url,
                             'tipo': 'documento_tecnico' if technical else 'publicacion_doe'}
    if not documents:
        raise ValueError('Instrument has no linked source documents ' + key)
    return {
        'id': 'los-santos-de-maimona-sitex-' + key,
        'id_origen': key, 'municipio': 'Los Santos de Maimona', 'codigo_ine': '06122',
        'provincia': 'Badajoz', 'titulo': title, 'expediente': reference,
        'tipo': 'planeamiento_urbanistico', 'estado': fields['Estado'],
        'fecha_aprob': _date(fields.get('Fecha AD')),
        'fecha_publicacion': _date(fields.get('Fecha de publicación AD')),
        'diario_publicacion': fields.get('Diario de publicación AD'),
        'fecha_deposito': _date(fields.get('Fecha de depósito')),
        'url': url, 'inventory_url': INVENTORY_URL, 'source': 'sitex_junta_extremadura',
        'origen': 'registro_autonomico_planeamiento_vigente',
        'source_metadata': fields, 'tramites': events,
        'documentos': list(documents.values()), 'coverage': 'sitex_vigente_only',
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


def _write(out_jsonl, rows):
    path = Path(out_jsonl)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    tmp.replace(path)
    return {'count': len(rows), 'written': len(rows)}


class LosSantosDeMaimonaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, capture, data=None):
        headers = {'User-Agent': 'municipio-planning-inventory/1.0'}
        if data is not None:
            headers['X-Requested-With'] = 'XMLHttpRequest'
            response = session.post(url, data=data, headers=headers, timeout=40)
        else:
            response = session.get(url, headers=headers, timeout=40)
        response.raise_for_status()
        if urlparse(response.url).hostname != 'sitex.juntaex.es':
            raise ValueError('Unexpected source redirect')
        if self.config.get('evidence_dir'):
            folder = Path(self.config['evidence_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / capture).write_text(response.text, encoding='utf-8')
        return response.text

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            municipality_id = parse_municipality(self._fetch(session, DISCOVERY_URL, 'sitex-discovery.html'))
            html = self._fetch(session, INVENTORY_URL, 'sitex-inventory.html',
                               data={'municipioseleccionado': municipality_id})
            inventory = parse_inventory(html, municipality_id)
            rows = []
            for key, url in inventory.items():
                time.sleep(.25)
                html = self._fetch(session, url, 'sitex-detail-' + key + '.html')
                rows.append(parse_detail(html, key, url, municipality_id))
        result = _write(out_jsonl, rows)
        return {**result, 'coverage': 'sitex_vigente_only', 'limitations': LIMITATIONS,
                'source_urls': [DISCOVERY_URL, INVENTORY_URL, *inventory.values()]}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot: registry metadata/documents may change without a new date.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**_write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
