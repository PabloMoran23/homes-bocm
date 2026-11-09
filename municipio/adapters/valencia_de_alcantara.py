"""Current municipal planning instruments from the official regional SITEX inventory."""
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

BASE = 'https://sitex.juntaex.es'
INVENTORY = BASE + '/SITEX/ptofiguras/listadoresultadossigcat'
LIMITATIONS = [
    'Only municipal instruments marked Vigente by SITEX; excludes regional plans, En trámite and No vigente.',
    'Regional inventory coverage, not a complete municipal works or licence register; currency is as reported by SITEX.',
    'Documents are linked, not interpreted; bulletin links can identify a whole issue rather than an individual notice.',
    'No verified coordinates or geometry; no granted licences extracted.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('a[rel~=next], .pagination, .paging, .paginator, a.next'):
        raise ValueError('Unexpected pagination: extend crawler before accepting partial coverage')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).lower() in {'siguiente', 'next', '»', '›'}:
            raise ValueError('Unexpected next page')
    return soup


def _date(value):
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat() if value else None


class ValenciaDeAlcantaraAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = _soup(html)
        option = soup.select_one('#PtofiguraMunicipio option[value="491"][selected]')
        root = soup.select_one('#capaderesultadosportramosdeley')
        if not option or option.get_text(strip=True) != 'Valencia de Alcántara' or not root:
            raise ValueError('Missing Valencia de Alcántara inventory identity or tree')
        items = {}
        for a in root.select('a.unenlaceafiguradeplaneamiento'):
            title = a.get('title', '')
            if title.lower().startswith('plan territorial'):
                continue
            img = a.select_one('img')
            if not img or img.get('alt') not in {'Vigente', 'No vigente', 'En trámite', 'En contratación'}:
                raise ValueError('Unknown planning status')
            if img['alt'] != 'Vigente':
                continue
            match = re.search(r"addTab\('/SITEX/ptofiguras/viewsigcat/(\d+)'", a.get('onclick', ''))
            if not match or not title:
                raise ValueError('Invalid planning detail link')
            ident = match[1]
            items[ident] = {'sitex_id': ident, 'url': BASE + '/SITEX/ptofiguras/viewsigcat/' + ident}
        if not items:
            raise ValueError('No current municipal instruments found')
        return list(items.values())

    @staticmethod
    def parse_detail(html, item):
        soup = _soup(html)
        ident = item['sitex_id']
        box = soup.select_one('#infoplaneamiento' + ident)
        if box is None:
            raise ValueError('Missing instrument information')
        fields = {}
        for tr in box.select('tr'):
            th, td = tr.find('th'), tr.find('td')
            if th and td:
                fields[th.get_text(' ', strip=True)] = td.get_text(' ', strip=True)
        if fields.get('Ámbito territorial') != 'Valencia de Alcántara' or fields.get('Estado') != 'Vigente':
            raise ValueError('Instrument municipality/status mismatch')
        if not fields.get('Figura urbanística') or not fields.get('Referencia'):
            raise ValueError('Missing instrument title/reference')
        docs = {}
        # Scope documents to this instrument, never the global navigation/forms.
        files = soup.select_one('#archivosplaneamiento' + ident)
        if files:
            for a in files.select('a[href]'):
                url = urljoin(item['url'], a['href'])
                if '/SITEX/ptofiguras/downloaddocumento/' in url:
                    docs[url] = {'titulo': a.get('download') or a.get_text(' ', strip=True),
                                 'url': url, 'tipo': 'documento_tecnico', 'procedencia': item['url']}
            if not docs:
                raise ValueError('Document tab present without usable document links')
        tramites = []
        for tr in box.select('[id^="filatramite"]'):
            cells = tr.find_all('td', recursive=False)
            if len(cells) != 2:
                raise ValueError('Malformed procedure row')
            event = {'fecha': _date(cells[0].get_text(strip=True)), 'tramite': cells[1].get_text(' ', strip=True)}
            links = []
            for a in cells[1].select('a[href]'):
                url = urljoin(item['url'], a['href'])
                if not url.startswith(('http://', 'https://')):
                    raise ValueError('Invalid procedure URL')
                links.append(url)
                docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                                      'tipo': 'publicacion_tramite', 'procedencia': item['url']})
            event['urls'] = links
            tramites.append(event)
        return {
            'id': 'valencia-de-alcantara-sitex-' + ident,
            'municipio': 'Valencia de Alcántara', 'provincia': 'Cáceres', 'codigo_ine': '10203',
            'titulo': fields['Figura urbanística'], 'referencia': fields['Referencia'],
            # The source's instrument reference groups its documents; this is
            # not a claimed municipal licence/file number.
            'expediente_grupo': fields['Referencia'],
            'tipo': 'planeamiento', 'estado_fuente': fields['Estado'],
            'fecha': None, 'fecha_acuerdo': None,
            'fecha_aprob': _date(fields.get('Fecha AD', '')),
            'fecha_publicacion': _date(fields.get('Fecha de publicación AD', '')),
            'fecha_deposito': _date(fields.get('Fecha de depósito', '')),
            'numero_deposito': fields.get('Nº de depósito') or None,
            'url': item['url'], 'source': 'junta_extremadura', 'origen': 'sitex_planeamiento_vigente',
            'sitex_id': ident, 'documentos': list(docs.values()), 'tramites': tramites,
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False,
        }

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        captures = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'municipio-valencia-de-alcantara/1.0'})

            def fetch(url, name, **kwargs):
                response = session.request('POST' if kwargs else 'GET', url, timeout=40, **kwargs)
                response.raise_for_status()
                response.encoding = 'utf-8'
                if captures:
                    captures.mkdir(parents=True, exist_ok=True)
                    (captures / name).write_text(response.text, encoding='utf-8')
                return response.text

            html = fetch(INVENTORY, 'inventory.html', data={'municipioseleccionado': '491'},
                         headers={'X-Requested-With': 'XMLHttpRequest', 'X-Update': 'planeamientosindex'})
            items = self.parse_inventory(html)
            rows = []
            for item in items:
                time.sleep(0.15)
                rows.append(self.parse_detail(fetch(item['url'], 'detail-' + item['sitex_id'] + '.html'), item))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [INVENTORY] + [i['url'] for i in items],
                'inventory_method': 'POST municipioseleccionado=491', 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
