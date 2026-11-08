"""Municipal planning inventory via the officially linked Extremadura SITEX.

One record per active municipal instrument; documents and dated procedures are
children. Non-current instruments and supra-municipal territorial plans excluded.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL = 'https://jerezcaballeros.es/urbanismo-y-obras-publicas/'
SITEX = 'https://sitex.juntaex.es'
LANDING = SITEX + '/SITEX/planeamiento'
INVENTORY = SITEX + '/SITEX/ptofiguras/listadoresultadossigcat'
NAME = 'Jerez de los Caballeros'
LIMITATIONS = [
    'Cobertura parcial: instrumentos municipales vigentes o en trámite en SITEX; excluye no vigentes y planes territoriales.',
    'No cubre todas las obras públicas ni licencias concedidas; los formularios no son licencias.',
    'Documentos enlazados, sin interpretar su contenido ni verificar geometrías vectoriales.',
    'Estado y fechas según SITEX, de carácter informativo; sin deducir aprobación de una publicación.',
    'La sede municipal PEPCH contiene documentación adicional no recorrida por este adaptador.',
]


def soup(html):
    return BeautifulSoup(html, 'html.parser')


def check_pagination(parsed):
    for a in parsed.select('a[href]'):
        if ('next' in a.get('rel', []) or
                a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', '»', '›'} or
                re.search(r'(?:/page[:/]|[?&]page=)', a['href'])):
            raise ValueError('Unexpected pagination: extend traversal before extracting')


def parse_municipality(html):
    parsed = soup(html)
    options = [o for o in parsed.select('#PtofiguraMunicipio option')
               if o.get_text(' ', strip=True) == NAME]
    if len(options) != 1 or options[0].get('value') != '98':
        raise ValueError('SITEX municipality mapping changed')
    return options[0]['value']


def parse_inventory(html):
    parsed = soup(html)
    check_pagination(parsed)
    parse_municipality(html)
    rows = {}
    links = parsed.select('a.unenlaceafiguradeplaneamiento')
    if not links:
        raise ValueError('Missing SITEX planning inventory')
    for a in links:
        script = a.get('onclick', '')
        m = re.fullmatch(r"addTab\('(/SITEX/ptofiguras/viewsigcat/(\d+))','([^']+)'\);", script)
        if not m:
            raise ValueError('Unrecognized instrument link')
        # Territorial instruments also appear in the municipality response.
        if not m[3].startswith(NAME + ' - '):
            continue
        status = a.get_text(' ', strip=True).rsplit(' - ', 1)[-1]
        if status == 'NV':
            continue
        if status not in {'V', 'TR'}:
            raise ValueError('Unknown instrument status')
        item = {'sitex_id': m[2], 'url': SITEX + m[1],
                'referencia_inventario': m[3].split(' - ', 1)[1],
                'titulo_inventario': ' '.join(a.get('title', '').split()),
                'estado_inventario': status}
        if m[2] in rows and rows[m[2]] != item:
            raise ValueError('Conflicting instrument identity')
        rows[m[2]] = item
    if not rows:
        raise ValueError('No active municipal planning instruments')
    return list(rows.values())


def parse_date(text):
    return datetime.strptime(text, '%d/%m/%Y').date().isoformat() if text else None


def parse_detail(html, item):
    parsed = soup(html)
    ident = item['sitex_id']
    root = parsed.select_one('#divplaneamiento' + ident)
    info = parsed.select_one('#infoplaneamiento' + ident)
    if root is None or info is None:
        raise ValueError('Missing instrument detail: ' + ident)
    check_pagination(root)
    fields = {}
    for tr in info.select('tr'):
        th, td = tr.find('th', recursive=False), tr.find('td', recursive=False)
        if th and td:
            fields[th.get_text(' ', strip=True)] = td.get_text(' ', strip=True)
    if fields.get('Ámbito territorial') != NAME or not fields.get('Figura urbanística'):
        raise ValueError('Wrong municipality or missing instrument type')
    status = fields.get('Estado')
    expected = {'V': 'Vigente', 'TR': 'En trámite'}[item['estado_inventario']]
    if status != expected:
        raise ValueError('Inventory/detail status mismatch: ' + str(status))
    procedures = []
    docs = {}
    for tr in info.select('[id^=filatramite]'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 2:
            raise ValueError('Changed procedure layout')
        procedure = {'fecha': parse_date(cells[0].get_text(strip=True)),
                     'tramite': cells[1].get_text(' ', strip=True)}
        a = cells[1].select_one('a[href]')
        if a:
            procedure['url'] = urljoin(item['url'], a['href'])
            docs[procedure['url']] = {'titulo': procedure['tramite'], 'url': procedure['url'],
                                      'origen': 'tramite_sitex', 'source_url': item['url']}
        procedures.append(procedure)
    for a in root.select('[id^=archivosplaneamiento] a[href]'):
        url = urljoin(item['url'], a['href'])
        if '/downloaddocumento/' not in url:
            raise ValueError('Unrecognized document link')
        docs[url] = {'titulo': a.get('download') or a.get_text(' ', strip=True),
                     'url': url, 'origen': 'archivo_sitex', 'source_url': item['url']}
    if not procedures and 'No se han definido trámites' not in info.get_text(' ', strip=True):
        raise ValueError('Missing planning procedures')
    return {
        **item, 'id': 'jerez-de-los-caballeros-sitex-' + ident,
        'municipio': NAME, 'provincia': 'Badajoz', 'codigo_ine': '06070',
        'expediente': 'SITEX:' + ident, 'referencia': fields.get('Referencia'),
        'categoria': 'planeamiento urbanístico',
        'titulo': fields['Figura urbanística'] + ' — ' + item['referencia_inventario'],
        'tipo': fields['Figura urbanística'], 'estado': status,
        'descripcion': item['titulo_inventario'],
        'fecha': None, 'fecha_aprob': parse_date(fields.get('Fecha AD', '')),
        'fecha_publicacion': parse_date(fields.get('Fecha de publicación AD', '')),
        'diario_publicacion': fields.get('Diario de publicación AD'),
        'fecha_acuerdo': None, 'tramites': procedures, 'documentos': list(docs.values()),
        'source': 'ayuntamiento', 'organismo_fuente': 'Junta de Extremadura — SITEX',
        'origen': 'planeamiento_sitex_enlazado_por_ayuntamiento',
        'source_inventory': INVENTORY, 'municipal_source_url': MUNICIPAL,
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False,
    }


class JerezDeLosCaballerosAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        capture = self.config.get('capture_dir')
        sources = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-jerez-de-los-caballeros/1.0'

            def fetch(url, filename, data=None):
                r = session.get(url, timeout=40) if data is None else session.post(url, data=data, timeout=40,
                    headers={'X-Requested-With': 'XMLHttpRequest', 'X-Update': 'planeamientosindex'})
                r.raise_for_status()
                r.encoding = 'utf-8'
                sources.append(url)
                if capture:
                    target = Path(capture) / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(r.content)
                return r.text

            municipal = soup(fetch(MUNICIPAL, 'municipal.html'))
            if not any(a['href'].rstrip('/') == LANDING for a in municipal.select('a[href]')):
                raise ValueError('Municipal link to SITEX missing')
            municipality = parse_municipality(fetch(LANDING, 'sitex-landing.html'))
            items = parse_inventory(fetch(INVENTORY, 'sitex-inventory.html', {'municipioseleccionado': municipality}))
            rows = []
            for item in items:
                time.sleep(.2)
                rows.append(parse_detail(fetch(item['url'], 'sitex-' + item['sitex_id'] + '.html'), item))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources,
                'limitations': LIMITATIONS, 'inventory_request': {'method': 'POST', 'municipioseleccionado': municipality}}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current snapshot; deliberately no date watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
