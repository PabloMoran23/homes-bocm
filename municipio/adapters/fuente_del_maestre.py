"""Fuente del Maestre: current SITEX planning inventory (not a licence register)."""
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
LIMITATIONS = [
    'Only SITEX instruments marked Vigente or En trámite; No vigente history excluded.',
    'Not a complete inventory of municipal works, licences or execution programmes.',
    'SITEX status and dated procedures are retained independently; they may differ.',
    'Document links are inventoried, not interpreted as separate projects; no geometry inferred.',
]


def check_pagination(soup):
    for a in soup.select('a[href]'):
        if (set(a.get('rel', [])) & {'next', 'prev'} or
                a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'anterior', 'última', '»', '›'} or
                re.search(r'(?:[?&]|/)page[:=/]', a['href'])):
            raise ValueError('Unexpected pagination: review crawler before extracting')
    if soup.select('.paging, .pagination, .paginator'):
        raise ValueError('Unexpected pagination container')


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    selected = [o for o in soup.select('#PtofiguraMunicipio option[selected]') if o.get('value')]
    if len(selected) != 1 or selected[0].get('value') != '79' or selected[0].get_text(strip=True) != 'Fuente del Maestre':
        raise ValueError('Inventory municipality filter not confirmed')
    items = {}
    excluded = 0
    for a in soup.select('a.unenlaceafiguradeplaneamiento'):
        match = re.search(r"addTab\('(/SITEX/ptofiguras/viewsigcat/(\d+))'", a.get('onclick', ''))
        img = a.select_one('img[alt]')
        if not match or not img:
            raise ValueError('Unrecognized planning link')
        status = img['alt']
        if status == 'No vigente':
            excluded += 1
            continue
        if status not in {'Vigente', 'En trámite'}:
            raise ValueError('Unrecognized instrument status')
        items[match[2]] = {'url': ROOT + match[1], 'status': status}
    if not items:
        raise ValueError('No current planning instruments found')
    return list(items.values()), excluded


def parse_instrument(html, url, expected_status):
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    fields = {}
    for tr in soup.select('table tr'):
        th, td = tr.find('th', recursive=False), tr.find('td', recursive=False)
        if th and td:
            fields[th.get_text(' ', strip=True)] = td.get_text(' ', strip=True)
    if fields.get('Ámbito territorial') != 'Fuente del Maestre':
        raise ValueError('Instrument belongs to another municipality')
    if fields.get('Estado') != expected_status:
        raise ValueError('Inventory/detail status mismatch')
    if not fields.get('Figura urbanística') or not fields.get('Referencia'):
        raise ValueError('Missing instrument identity')
    record = {
        'id': 'fuente-del-maestre-sitex-' + url.rstrip('/').split('/')[-1],
        'municipio': 'Fuente del Maestre', 'provincia': 'Badajoz', 'codigo_ine': '06054',
        'titulo': fields['Figura urbanística'], 'referencia': fields['Referencia'],
        'tipo': 'planeamiento_urbanistico', 'estado_fuente': fields['Estado'],
        'url': url, 'inventory_url': INVENTORY, 'inventory_filter': {'municipioseleccionado': '79'},
        'source': 'junta_extremadura_sitex', 'origen': 'inventario_oficial_planeamiento',
        'geometry_status': 'unavailable', 'publication_ready': False,
    }
    for label, key in [('Fecha AD', 'fecha_aprob'), ('Fecha de publicación AD', 'fecha_publicacion'),
                       ('Fecha de depósito', 'fecha_deposito')]:
        if fields.get(label):
            record[key] = datetime.strptime(fields[label], '%d/%m/%Y').date().isoformat()
    record['tramites'] = []
    docs = {}
    for tr in soup.select('tr[id^="filatramite"]'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 2:
            raise ValueError('Invalid procedure row')
        event = {'fecha': datetime.strptime(cells[0].get_text(strip=True), '%d/%m/%Y').date().isoformat(),
                 'descripcion': cells[1].get_text(' ', strip=True)}
        a = cells[1].select_one('a[href]')
        if a:
            event['url'] = urljoin(url, a['href'])
            docs[event['url']] = {'titulo': event['descripcion'], 'url': event['url'],
                                  'procedencia': 'tramite_sitex', 'fecha_tramite': event['fecha']}
        record['tramites'].append(event)
    for a in soup.select('a[href*="/ptofiguras/downloaddocumento/"]'):
        target = urljoin(url, a['href'])
        if urlparse(target).hostname != 'sitex.juntaex.es':
            raise ValueError('Unexpected document host')
        docs[target] = {'titulo': a.get('download') or a.find_parent('tr').get_text(' ', strip=True),
                        'url': target, 'procedencia': 'documento_sitex'}
    record['documentos'] = list(docs.values())
    record['limitaciones'] = LIMITATIONS
    return record


class FuenteDelMaestreAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, *, inventory=False):
        if inventory:
            response = session.post(url, data={'municipioseleccionado': '79'}, timeout=40,
                                    headers={'X-Requested-With': 'XMLHttpRequest'})
        else:
            response = session.get(url, timeout=40)
        response.raise_for_status()
        if urlparse(response.url).hostname != 'sitex.juntaex.es':
            raise ValueError('Unexpected source redirect')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            name = 'inventory-live' if inventory else url.rstrip('/').split('/')[-1]
            (path / (name + '.html')).write_text(response.text, encoding='utf-8')
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
            session.headers['User-Agent'] = 'municipio-fuente-del-maestre/1.0'
            items, excluded = parse_inventory(self._fetch(session, INVENTORY, inventory=True))
            rows = [parse_instrument(self._fetch(session, item['url']), item['url'], item['status'])
                    for item in items]
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'excluded_no_vigente': excluded,
                'source_urls': [INVENTORY] + [item['url'] for item in items],
                'limitations': LIMITATIONS, 'coverage': 'current_sitex_municipal_planning'}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot, so changes to status and attachments are reflected.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
