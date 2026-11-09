"""Santa Marta (06121): current planning inventory from Junta de Extremadura SITEX."""
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
PORTAL = ROOT + '/SITEX/planeamiento'
INVENTORY = ROOT + '/SITEX/ptofiguras/listadoresultadossigcat'
LIMITATIONS = [
    'Only SITEX instruments marked Vigente or En trámite; superseded historical instruments excluded.',
    'SITEX status is retained verbatim and may lag recorded approval events; no independent legal currency assertion.',
    'Not an inventory of building licences, procurement or all municipal public works.',
    'Some instruments expose gazette notices only, without the full technical plan.',
    'No verified instrument geometry or coordinates; PDF plans are retained as links, not vectorized.',
    'Publication dates refer to the final approval publication field; initial notice dates remain in tramites.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # This endpoint currently returns the complete municipal tree, without paging.
    if soup.select('.pagination, .paging, .paginator, a[rel~=next]'):
        raise ValueError('Unimplemented pagination in SITEX response')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', '»', '›'} and a['href'] not in {'', '#'}:
            raise ValueError('Unimplemented pagination in SITEX response')
    return soup


def _date(text):
    if not text.strip():
        return None
    return datetime.strptime(text.strip(), '%d/%m/%Y').date().isoformat()


def parse_inventory(html):
    soup = _soup(html)
    option = soup.select_one('#PtofiguraMunicipio option[value="166"]')
    if not option or option.get_text(strip=True) != 'Santa Marta' or not option.has_attr('selected'):
        raise ValueError('SITEX inventory is not selected for Santa Marta (internal ID 166)')
    entries = {}
    for a in soup.select('a[onclick]'):
        match = re.search(r"/SITEX/ptofiguras/viewsigcat/(\d+)", a['onclick'])
        if not match:
            continue
        label = a.get_text(' ', strip=True)
        if not re.search(r' - (?:NV|V|TR)$', label):
            raise ValueError('Unknown instrument state: ' + label)
        if label.endswith(' - NV'):
            continue
        if 'Santa Marta - ' not in a['onclick']:
            raise ValueError('Unexpected municipality in instrument tree')
        ident = match[1]
        entry = {'sitex_id': ident, 'url': ROOT + match[0],
                 'estado_inventario': 'Vigente' if label.endswith(' - V') else 'En trámite'}
        if ident in entries and entries[ident] != entry:
            raise ValueError('Conflicting duplicate instrument')
        entries[ident] = entry
    if not entries:
        raise ValueError('No current Santa Marta instruments; review source')
    return list(entries.values())


def parse_detail(html, entry):
    soup = _soup(html)
    block = soup.select_one('#divplaneamiento' + entry['sitex_id'])
    if block is None:
        raise ValueError('Instrument detail absent')
    info = block.select_one('#infoplaneamiento' + entry['sitex_id'])
    if info is None:
        raise ValueError('Instrument information absent')
    fields = {}
    for tr in info.select('tr'):
        th, td = tr.find('th', recursive=False), tr.find('td', recursive=False)
        if th is not None and td is not None:
            fields[th.get_text(' ', strip=True)] = td.get_text(' ', strip=True)
    municipal_id = info.select_one('.campoconidsdemunicipiosparamapa')
    if fields.get('Ámbito territorial') != 'Santa Marta' or municipal_id is None or municipal_id.get_text(strip=True) != '166':
        raise ValueError('Instrument belongs to another municipality')
    title, reference, state = (fields.get(k) for k in ('Figura urbanística', 'Referencia', 'Estado'))
    if not title or not reference or state != entry['estado_inventario']:
        raise ValueError('Missing fields or conflicting instrument state')
    events = []
    for tr in info.select('tr[id^="filatramite"]'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 2:
            raise ValueError('Changed event markup')
        events.append({'fecha': _date(cells[0].get_text(strip=True)),
                       'tramite': cells[1].get_text(' ', strip=True),
                       'urls': [urljoin(entry['url'], a['href']) for a in cells[1].select('a[href]')]})
    if not events:
        raise ValueError('No planning procedure events')
    docs = {}
    for a in block.select('a[href]'):
        url = urljoin(entry['url'], a['href'])
        parsed = urlparse(url)
        if not ((parsed.hostname == 'sitex.juntaex.es' and '/downloaddocumento/' in parsed.path)
                or (parsed.hostname == 'doe.juntaex.es' and parsed.path.lower().endswith('.pdf'))):
            continue
        docs.setdefault(url, {'titulo': a.get('download') or a.get_text(' ', strip=True),
                             'url': url, 'url_origen': entry['url'],
                             'organismo': 'Junta de Extremadura',
                             'clase': 'documento_tecnico' if '/downloaddocumento/' in parsed.path else 'publicacion_DOE'})
    if not docs:
        raise ValueError('Instrument lacks linked source documents')
    approval = _date(fields.get('Fecha AD', ''))
    return {
        'id': 'santa-marta-sitex-' + entry['sitex_id'],
        'municipio': 'Santa Marta', 'provincia': 'Badajoz', 'codigo_ine': '06121',
        'titulo': title, 'tipo': 'planeamiento_urbanistico', 'referencia': reference,
        'estado_fuente': state, 'fecha': None, 'fecha_aprob': approval,
        'fecha_publicacion': _date(fields.get('Fecha de publicación AD', '')),
        'fecha_acuerdo': None,
        'url': entry['url'], 'source': 'junta_extremadura_sitex',
        'origen': 'registro_planeamiento_urbanistico', 'sitex_id': entry['sitex_id'],
        'documentos': list(docs.values()), 'tramites': events,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class SantaMartaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        sources = []
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'municipio-santa-marta/1.0'})

            def fetch(url, *, data=None):
                response = session.request('POST' if data else 'GET', url, data=data, timeout=40,
                    headers={'X-Requested-With': 'XMLHttpRequest', 'X-Update': 'planeamientosindex'} if data else {})
                response.raise_for_status()
                response.encoding = 'utf-8'
                sources.append(url)
                capture = self.config.get('capture_dir')
                if capture:
                    dest = Path(capture)
                    dest.mkdir(parents=True, exist_ok=True)
                    name = 'inventory.html' if data else 'detail-' + url.rsplit('/', 1)[-1] + '.html'
                    (dest / name).write_text(response.text, encoding='utf-8')
                return response.text

            entries = parse_inventory(fetch(INVENTORY, data={'municipioseleccionado': '166'}))
            rows = []
            for entry in entries:
                time.sleep(0.2)
                rows.append(parse_detail(fetch(entry['url']), entry))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources,
                'inventory_method': 'POST', 'inventory_parameters': {'municipioseleccionado': '166'},
                'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
