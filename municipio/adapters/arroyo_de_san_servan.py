"""Current municipal planning instruments discovered through the official SITEX tree."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://sitex.juntaex.es'
INVENTORY = ROOT + '/SITEX/ptofiguras/listadoresultadossigcat'
MUNICIPIO = 'Arroyo de San Serván'
LIMITATIONS = [
    'Only current municipal instruments in SITEX; historical and territorial plans excluded.',
    'SITEX is not a complete inventory of recent DOE notices, works or municipal licences.',
    'Document links retained; PDF contents are not parsed. No verified project geometry.',
]


def _text(node):
    return node.get_text(' ', strip=True)


def _no_pagination(soup):
    if soup.select('.paging, .pagination, .paginator, a[rel~=next]'):
        raise ValueError('Pagination detected: inventory must be reviewed before extraction')
    for a in soup.select('a[href]'):
        if re.fullmatch(r'siguiente|next|[»›]', _text(a), re.I):
            raise ValueError('Pagination detected: refusing partial extraction')


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    _no_pagination(soup)
    selected = soup.select_one('#PtofiguraMunicipio option[value="13"]')
    if not selected or selected.get('value') != '13' or _text(selected) != MUNICIPIO:
        raise ValueError('SITEX municipality identifier missing or mismatched')
    anchors = soup.select('a.unenlaceafiguradeplaneamiento')
    if not anchors:
        raise ValueError('Missing SITEX planning tree')
    records = {}
    for a in anchors:
        onclick = a.get('onclick', '')
        match = re.search(r"addTab\('(/SITEX/ptofiguras/viewsigcat/(\d+))','([^']+)'\)", onclick)
        img = a.select_one('img')
        if not match or not img or img.get('alt') not in {'Vigente', 'No vigente', 'En trámite', 'En contratación'}:
            raise ValueError('Unrecognized planning entry')
        # Territorial figures appear in the same tree, but are outside this adapter's scope.
        if not match[3].startswith(MUNICIPIO + ' - ') or img['alt'] != 'Vigente':
            continue
        records[match[2]] = ROOT + match[1]
    if not records:
        raise ValueError('No current municipal instruments; review source before accepting empty snapshot')
    return records


def _date(value):
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat() if value else None


def parse_instrument(html, figure_id, url):
    soup = BeautifulSoup(html, 'html.parser')
    _no_pagination(soup)
    info = soup.select_one('#infoplaneamiento' + figure_id)
    heading = soup.select_one('#cabeceraplaneamiento' + figure_id + ' h1')
    if not info or not heading:
        raise ValueError('Missing instrument detail')
    fields = {}
    for tr in info.select('tr'):
        th, td = tr.find('th'), tr.find('td')
        if th and td:
            fields[_text(th)] = _text(td)
    if fields.get('Ámbito territorial') != MUNICIPIO or fields.get('Estado') != 'Vigente':
        raise ValueError('Instrument municipality/status differs from inventory')
    if not fields.get('Figura urbanística') or not fields.get('Referencia'):
        raise ValueError('Missing instrument identity')
    docs = {}
    for a in soup.select('#archivosplaneamiento' + figure_id + ' a[href], #infoplaneamiento' + figure_id + ' a[href]'):
        href = a['href']
        if '/ptofiguras/downloaddocumento/' not in href and not re.match(r'https?://doe\.juntaex\.es/.*\.pdf$', href):
            continue
        doc_url = urljoin(url, href)
        docs[doc_url] = {'titulo': a.get('download') or _text(a), 'url': doc_url, 'url_ficha': url}
    if not docs:
        raise ValueError('Instrument has no linked source documents')
    tramites = []
    for tr in info.select('tr[id^=filatramite]'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 2:
            raise ValueError('Unrecognized procedure row')
        tramites.append({'fecha': _date(_text(cells[0])), 'tramite': _text(cells[1])})
    return {
        'id': 'arroyo-de-san-servan-sitex-' + figure_id,
        'municipio': MUNICIPIO, 'codigo_ine': '06012', 'provincia': 'Badajoz',
        'titulo': _text(heading), 'tipo': 'planeamiento_urbanistico',
        'figura_urbanistica': fields['Figura urbanística'], 'referencia': fields['Referencia'],
        'sitex_id': figure_id, 'estado': fields['Estado'],
        'fecha': None, 'fecha_aprob': _date(fields.get('Fecha AD')),
        'fecha_publicacion': _date(fields.get('Fecha de publicación AD')),
        'diario_publicacion': fields.get('Diario de publicación AD'),
        'numero_deposito': fields.get('Nº de depósito'),
        'fecha_deposito': _date(fields.get('Fecha de depósito')),
        'url': url, 'source': 'junta_extremadura_sitex', 'origen': 'registro_oficial_planeamiento',
        'url_inventario': INVENTORY, 'tramites': tramites, 'documentos': list(docs.values()),
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False, 'cobertura': LIMITATIONS,
    }


class ArroyoDeSanServanAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, capture_name, data=None):
        response = session.post(url, data=data, timeout=40) if data else session.get(url, timeout=40)
        response.raise_for_status()
        if len(response.content) > 8_000_000:
            raise ValueError('Source exceeds reviewed size; refusing truncation')
        response.encoding = 'utf-8'
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture_name).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-arroyo-de-san-servan/1.0'
            # Read-only AJAX search used by the official municipality selector.
            inventory = self._fetch(session, INVENTORY, 'sitex-inventory.html', {'municipioseleccionado': '13'})
            figures = parse_inventory(inventory)
            rows = [parse_instrument(self._fetch(session, url, 'sitex-' + ident + '.html'), ident, url)
                    for ident, url in figures.items()]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [INVENTORY, *figures.values()],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
