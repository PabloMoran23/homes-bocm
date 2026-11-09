"""Current municipal planning instruments in the official Extremadura catalogue."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://sitex.juntaex.es'
INVENTORY = ROOT + '/SITEX/ptofiguras/listadoresultadossigcat'
CONSULTATION = ROOT + '/SITEX/planeamiento'
MUNICIPALITY = 'Malpartida de Cáceres'
LIMITATIONS = [
    'Only municipal instruments marked Vigente in SITEX; historical and supramunicipal plans excluded.',
    'Partial thematic coverage: no works inventory or granted licence register.',
    'Document links retained; PDF contents and project geometry are not extracted.',
    'PGM.PPO-001 approval date conflicts: SITEX 18/09/2026 versus DOE 18/09/2025; canonical approval date withheld.',
]


def _text(node):
    return node.get_text(' ', strip=True)


def _no_pagination(soup):
    # This endpoint serves a complete municipality tree. Fail visibly if the
    # portal changes to pagination rather than returning a partial snapshot.
    if soup.select('.paging, .pagination, .paginator, a[rel="next"], a[href*="/page:"], a[href*="page="]'):
        raise ValueError('Unexpected SITEX pagination; complete traversal must be implemented')


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    _no_pagination(soup)
    selected = soup.select_one('#PtofiguraMunicipio option[selected][value="368"]')
    if selected is None or _text(selected) != MUNICIPALITY:
        raise ValueError('SITEX did not confirm municipality 368 (INE 10115)')
    entries = soup.select('a.unenlaceafiguradeplaneamiento')
    if not entries:
        raise ValueError('SITEX planning tree missing')
    urls = []
    for entry in entries:
        status = entry.find('img')
        if status is None or status.get('alt') not in ('Vigente', 'No vigente', 'En trámite'):
            raise ValueError('Unknown planning status')
        if status['alt'] != 'Vigente':
            continue
        match = re.fullmatch(r"addTab\('(/SITEX/ptofiguras/viewsigcat/\d+)','([^']+)'\);", entry.get('onclick', ''))
        if not match:
            raise ValueError('Unrecognized SITEX instrument link')
        # Municipal entries carry the municipality prefix; regional plans do not.
        if not match[2].startswith(MUNICIPALITY + ' - '):
            continue
        target = ROOT + match[1]
        if target not in urls:
            urls.append(target)
    if not urls:
        raise ValueError('No current municipal instruments in SITEX')
    return urls


def _date(value):
    if not value or value == '-':
        return None
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


def parse_instrument(html, url):
    match = re.fullmatch(re.escape(ROOT) + r'/SITEX/ptofiguras/viewsigcat/(\d+)', url)
    if not match:
        raise ValueError('Unexpected instrument URL')
    figure_id = match[1]
    soup = BeautifulSoup(html, 'html.parser')
    scope = soup.select_one('#divplaneamiento' + figure_id)
    if scope is None:
        raise ValueError('Instrument container missing')
    _no_pagination(scope)
    info = scope.select_one('#infoplaneamiento' + figure_id)
    if info is None:
        raise ValueError('Instrument metadata missing')
    fields = {}
    for tr in info.select('tr'):
        th, td = tr.find('th'), tr.find('td')
        if th is not None and td is not None:
            fields[_text(th)] = _text(td)
    if fields.get('Ámbito territorial') != MUNICIPALITY or fields.get('Estado') != 'Vigente':
        raise ValueError('Wrong municipality or non-current instrument')
    title, reference = fields.get('Figura urbanística'), fields.get('Referencia')
    if not title or not reference or not reference.startswith('PGM'):
        raise ValueError('Missing municipal planning identity')
    approval = _date(fields.get('Fecha AD'))
    publication = _date(fields.get('Fecha de publicación AD'))
    documents = {}
    for a in scope.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        if parsed.hostname == 'sitex.juntaex.es' and re.fullmatch(r'/SITEX/ptofiguras/downloaddocumento/\d+', parsed.path):
            label = a.get('download') or _text(a.find_parent('tr'))
            kind = 'documento de planeamiento'
        elif parsed.hostname == 'doe.juntaex.es' and parsed.path.lower().endswith('.pdf'):
            label, kind = _text(a), 'publicación en DOE'
        else:
            continue
        documents[target] = {'url': target, 'titulo': label, 'tipo': kind, 'source_url': url}
    if not documents:
        raise ValueError('Instrument has no documentary links')
    procedures = []
    for tr in scope.select('#tablaCalificacionplaneamientostramit tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) == 2:
            procedures.append({'fecha': _date(_text(cells[0])), 'tramite': _text(cells[1]), 'source_url': url})
    row = {
        'id': 'malpartida-de-caceres-sitex-' + figure_id,
        'municipio': MUNICIPALITY, 'codigo_ine': '10115', 'provincia': 'Cáceres',
        'titulo': title, 'referencia': reference, 'tipo': 'instrumento de planeamiento',
        'estado_fuente': fields['Estado'], 'url': url, 'inventory_url': INVENTORY,
        'source': 'junta_extremadura', 'origen': 'sitex_planeamiento_municipal',
        'fecha': None, 'fecha_aprob': approval, 'fecha_publicacion': publication,
        'fechas_sitex': {'fecha_aprobacion_definitiva': approval,
                         'fecha_publicacion_aprobacion_definitiva': publication,
                         'source_url': url},
        'documentos': list(documents.values()), 'tramites': procedures,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }
    # Known discrepancy discovered during source verification. Do not choose an
    # agreement year silently; preserve the catalogue value with its provenance.
    if reference == 'PGM.PPO-001' and approval == '2026-09-18':
        row['fecha_aprob'] = None
        row['date_warning'] = LIMITATIONS[-1]
        row['date_conflict_source_url'] = 'https://doe.juntaex.es/otrosFormatos/html.php?anio=2026&doe=2010o&xml=2026081727'
    return row


class MalpartidaDeCaceresAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, *, data=None):
        headers = {'User-Agent': 'municipio-malpartida-de-caceres/1.0'}
        if data is not None:
            headers.update({'X-Requested-With': 'XMLHttpRequest', 'X-Update': 'planeamientosindex'})
        response = session.request('POST' if data is not None else 'GET', url,
                                   data=data, headers=headers, timeout=40)
        response.raise_for_status()
        if response.url != url or len(response.content) > 5_000_000:
            raise ValueError('Unexpected redirect or oversized SITEX response')
        response.encoding = 'utf-8'
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            name = 'inventory.html' if data is not None else 'figure-' + url.rsplit('/', 1)[-1] + '.html'
            (directory / name).write_bytes(response.content)
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            html = self._fetch(session, INVENTORY, data={'municipioseleccionado': '368'})
            urls = parse_inventory(html)
            rows = [parse_instrument(self._fetch(session, url), url) for url in urls]
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        # Only replace output after the entire inventory has succeeded.
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'source_urls': [CONSULTATION, INVENTORY, *urls],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {'status': 'disabled', 'count': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
