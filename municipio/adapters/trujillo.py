"""Trujillo planning instruments from the public Junta de Extremadura SITEX inventory."""
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
LIMITATIONS = [
    'Partial municipal coverage: only planning instruments listed by SITEX; no works or granted licence register.',
    'SITEX status is reported as published, without independently certifying current legal validity.',
    'Documents are grouped per SITEX figure; document contents and geometry are not extracted.',
    'No inferred approval dates, publication dates or coordinates; dates use explicitly labelled SITEX fields.',
]


def text(node):
    return node.get_text(' ', strip=True) if node else ''


def guard_pagination(soup):
    if soup.select('.pagination, .paging, .paginator, a[rel~=next]'):
        raise ValueError('Unexpected pagination: cannot certify a complete SITEX snapshot')


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    guard_pagination(soup)
    # The AJAX response leaves the select blank; its raster link identifies scope.
    scope = soup.select_one('#enlacerasterplaneamiento482')
    if not scope or '/viewrefundido/482' not in scope.get('onclick', ''):
        raise ValueError('Inventory is not scoped to Trujillo (SITEX 482)')
    figures = {}
    for a in soup.select('a.unenlaceafiguradeplaneamiento'):
        match = re.search(r"addTab\('/SITEX/ptofiguras/viewsigcat/(\d+)'", a.get('onclick', ''))
        if not match or not re.search(r",'Trujillo - [^']+'\);", a.get('onclick', '')):
            raise ValueError('Unrecognized figure link')
        figures[match[1]] = BASE + '/SITEX/ptofiguras/viewsigcat/' + match[1]
    if not figures:
        raise ValueError('No Trujillo planning instruments found')
    return figures


def iso_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%d/%m/%Y').date().isoformat()
    except ValueError as exc:
        raise ValueError('Invalid labelled SITEX date: ' + value) from exc


def parse_detail(html, figure_id):
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.select_one('#divplaneamiento' + figure_id)
    if root is None:
        raise ValueError('Missing figure ' + figure_id)
    guard_pagination(root)
    info = root.select_one('#infoplaneamiento' + figure_id)
    if info is None:
        raise ValueError('Missing planning information')
    fields = {}
    for tr in info.select('tr'):
        th, td = tr.find('th', recursive=False), tr.find('td', recursive=False)
        if th and td:
            fields[text(th)] = text(td)
    if fields.get('Ámbito territorial') != 'Trujillo':
        raise ValueError('Figure belongs to another municipality')
    title = fields.get('Figura urbanística')
    if not title or not fields.get('Referencia'):
        raise ValueError('Missing instrument title/reference')
    events = []
    for tr in info.select('tr[id^=filatramite]'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 2:
            raise ValueError('Unexpected procedure row')
        a = cells[1].find('a', href=True)
        events.append({'fecha': iso_date(text(cells[0])), 'tramite': text(cells[1]),
                       'url': urljoin(BASE, a['href']) if a else None})
    documents = {}
    for a in root.select('a[href]'):
        href = a['href']
        if '/downloaddocumento/' not in href and not any(a['href'] == e['url'] for e in events):
            # Event links may be relative; the comparison below also handles them.
            if urljoin(BASE, href) not in {e['url'] for e in events if e['url']}:
                continue
        url = urljoin(BASE, href)
        row = a.find_parent('tr')
        label = a.get('download') or text(a) or text(row)
        documents[url] = {'titulo': label, 'url': url}
    return {
        'id': 'trujillo-sitex-' + figure_id, 'municipio': 'Trujillo',
        'codigo_ine': '10195', 'provincia': 'Cáceres', 'sitex_id': figure_id,
        'titulo': title, 'tipo': 'instrumento de planeamiento urbanístico',
        'referencia': fields['Referencia'], 'expediente': fields['Referencia'],
        'estado': fields.get('Estado'), 'fase': None,
        'fecha': None, 'fecha_acuerdo': None,
        'fecha_aprob': iso_date(fields.get('Fecha AD')),
        'fecha_publicacion': iso_date(fields.get('Fecha de publicación AD')),
        'diario_publicacion': fields.get('Diario de publicación AD'),
        'tramites': events, 'documentos': list(documents.values()),
        'url': BASE + '/SITEX/ptofiguras/viewsigcat/' + figure_id,
        'inventory_url': INVENTORY, 'inventory_method': 'POST municipioseleccionado=482',
        'source': 'junta_extremadura_sitex', 'origen': 'inventario_oficial_planeamiento',
        'source_entity_type': 'expediente',
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class TrujilloAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='trujillo', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE + '/SITEX/planeamiento')

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        source_urls = []
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'municipio-trujillo/1.0',
                                    'X-Requested-With': 'XMLHttpRequest'})

            def fetch(url, name, data=None):
                # This POST is the site's anonymous read-only inventory filter.
                response = session.request('POST' if data else 'GET', url, data=data, timeout=45)
                response.raise_for_status()
                if urlparse(response.url).hostname != 'sitex.juntaex.es':
                    raise ValueError('Unexpected source redirect')
                response.encoding = 'utf-8'
                source_urls.append(url)
                if captures:
                    folder = Path(captures)
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / name).write_bytes(response.content)
                return response.text

            figures = parse_inventory(fetch(INVENTORY, 'inventory.html', {'municipioseleccionado': '482'}))
            rows = [parse_detail(fetch(url, 'figure-' + fid + '.html'), fid)
                    for fid, url in figures.items()]
        # Write only after the entire inventory and every detail have succeeded.
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'live_records': len(rows),
                'source_urls': source_urls, 'limitations': LIMITATIONS,
                'coverage': 'complete SITEX Trujillo inventory snapshot; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
