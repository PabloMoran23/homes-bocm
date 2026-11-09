"""Fregenal municipal planning figures from the official regional SITEX inventory."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

NAME = 'Fregenal de la Sierra'
ROOT = 'https://sitex.juntaex.es'
LANDING = ROOT + '/SITEX/planeamiento'
INVENTORY = ROOT + '/SITEX/ptofiguras/listadoresultadossigcat'
LIMITATIONS = [
    'Snapshot of SITEX municipal planning figures; not all municipal works or licences.',
    'Includes vigente, no vigente and en trámite as reported by SITEX; status is not an approval event.',
    'Dates are registry metadata, not independently reconciled with every linked official bulletin.',
    'Document links retained; document contents and project geometries are not extracted.',
    'Figure 40684: SITEX AD 24/03/2025 differs from linked DOE agreement date 25/03/2025; registry date retained with provenance.',
    'Municipal downloads portal returned HTTP 403 during research.',
]


def text(node):
    return node.get_text(' ', strip=True)


def check_pagination(soup):
    # The observed endpoint returns a complete tree. Fail if pagination appears,
    # rather than silently treating a changed, paged endpoint as a full snapshot.
    if soup.select('.pagination, .paging, .paginator, a[rel="next"]'):
        raise ValueError('Unexpected pagination in SITEX; full traversal needs review')


def municipality_id(html):
    soup = BeautifulSoup(html, 'html.parser')
    options = soup.select('#PtofiguraMunicipio option')
    matches = [o.get('value') for o in options if text(o) == NAME]
    if len(matches) != 1 or not str(matches[0]).isdigit():
        raise ValueError('Municipality selector missing or ambiguous')
    return matches[0]


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    trees = soup.select('#listaplaneamientosnuevaley, #listaplaneamientosantigualey')
    if len(trees) != 2:
        raise ValueError('SITEX planning trees missing')
    urls = {}
    excluded = []
    for tree in trees:
        for a in tree.select('a.unenlaceafiguradeplaneamiento'):
            match = re.fullmatch(r"addTab\('(/SITEX/ptofiguras/viewsigcat/\d+)','([^']+)'\);", a.get('onclick', ''))
            if not match:
                raise ValueError('Unrecognised figure link')
            if not match[2].startswith(NAME + ' - '):
                if match[2].startswith('Plan Territorial'):
                    excluded.append(urljoin(ROOT, match[1]))
                    continue
                raise ValueError('Unexpected nonmunicipal figure in tree')
            urls[urljoin(ROOT, match[1])] = None
    if not urls:
        raise ValueError('Empty municipal planning inventory')
    return list(urls), excluded


def iso_date(value):
    if not value or value in ('-', '—'):
        return None
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


def parse_figure(html, url):
    figure_id = urlparse(url).path.rsplit('/', 1)[-1]
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content')
    if content is None:
        raise ValueError('Missing figure content')
    check_pagination(content)
    fields = {}
    for row in content.select('table.juntaex tr'):
        th, td = row.find('th', recursive=False), row.find('td', recursive=False)
        if th and td:
            key = text(th)
            value = text(td)
            if key in fields and fields[key] != value:
                raise ValueError('Ambiguous figure metadata: ' + key)
            fields[key] = value
    if fields.get('Ámbito territorial') != NAME:
        raise ValueError('Figure belongs to a different municipality')
    heading = content.select_one('h1')
    title = fields.get('Figura urbanística') or (text(heading) if heading else None)
    reference = fields.get('Referencia')
    if not title or not reference or not fields.get('Estado'):
        raise ValueError('Incomplete named planning figure')
    documents = {}
    events = []
    for row in content.select('#tablaCalificacionplaneamientostramit tbody tr'):
        cells = row.find_all('td', recursive=False)
        if len(cells) != 2:
            continue
        event = {'fecha': iso_date(text(cells[0])), 'tramite': text(cells[1]), 'source_url': url}
        events.append(event)
    for a in content.select('#tablaCalificacionplaneamientostramit a[href], [id^="archivosplaneamiento"] a[href], #tablaCalificacionplaneamientosrecursos a[href]'):
        target = urljoin(url, a['href'])
        if urlparse(target).scheme not in ('https', 'http'):
            raise ValueError('Unexpected document URL')
        label = a.get('download') or text(a)
        if not label and a.find_parent('tr'):
            label = text(a.find_parent('tr'))
        documents[target] = {'url': target, 'titulo': label, 'source_url': url}
    related = [{'url': urljoin(url, a['href']), 'titulo': text(a)}
               for a in content.select('a[href]')
               if a['href'] != '#' and '/imprimir' not in a['href']
               and urljoin(url, a['href']) not in documents]
    return {
        'id': 'fregenal-sitex-' + figure_id,
        'municipio': NAME, 'codigo_ine': '06050', 'provincia': 'Badajoz',
        'titulo': title, 'tipo': 'instrumento de planeamiento urbanístico',
        'expediente': reference, 'sitex_id': figure_id,
        'denominacion_registro': text(heading) if heading else None,
        'estado': fields['Estado'],
        'fecha_aprob': iso_date(fields.get('Fecha AD')),
        'fecha_publicacion': iso_date(fields.get('Fecha de publicación AD')),
        'date_provenance': {'source_url': url, 'fecha_aprob': 'Fecha AD (SITEX)',
                            'fecha_publicacion': 'Fecha de publicación AD (SITEX)'},
        'url': url, 'inventory_url': INVENTORY, 'source': 'sitex-junta-extremadura',
        'origen': 'inventario_oficial_planeamiento', 'source_entity_type': 'expediente',
        'tramites': events, 'documentos': list(documents.values()),
        'enlaces_relacionados': related,
        'metadata_fuente': fields,
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class FregenalDeLaSierraAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        capture = self.config.get('capture_dir')
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-planning-inventory/1.0'

            def fetch(url, filename, data=None):
                response = session.request('POST' if data else 'GET', url, data=data, timeout=45,
                                           headers={'X-Requested-With': 'XMLHttpRequest'} if data else {})
                response.raise_for_status()
                if urlparse(response.url).hostname != 'sitex.juntaex.es':
                    raise ValueError('Unexpected source redirect')
                if capture:
                    path = Path(capture) / filename
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(response.content)
                source_urls.append(url)
                return response.text

            selected_id = municipality_id(fetch(LANDING, 'landing.html'))
            inventory = fetch(INVENTORY, 'inventory.html', {'municipioseleccionado': selected_id})
            urls, excluded = parse_inventory(inventory)
            rows = [parse_figure(fetch(url, 'figure-' + url.rsplit('/', 1)[-1] + '.html'), url) for url in urls]
        # A failed request/parser never overwrites an existing snapshot with partial results.
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': source_urls,
                'inventory_method': 'POST', 'inventory_parameters': {'municipioseleccionado': selected_id},
                'excluded_territorial_figures': excluded, 'limitations': LIMITATIONS,
                'publication_ready': False, 'coverage': 'current_sitex_municipal_planning_tree'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
