"""Current Miajadas planning instruments from the official regional SITEX inventory."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://sitex.juntaex.es'
INVENTORY = BASE + '/SITEX/ptofiguras/listadoresultadossigcat'
LIMITATIONS = [
    'Solo figuras vigentes del inventario SITEX de Miajadas; excluye las no vigentes.',
    'Cobertura parcial: sin inventario municipal de obras ni licencias concedidas; portal municipal HTTP 403.',
    'Enlaces documentales conservados; no se interpreta el contenido de cada PDF.',
    'Sin geometría de los instrumentos verificada; coordenadas nulas, publication_ready false.',
]


def _text(element):
    return element.get_text(' ', strip=True)


def _date(value):
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat() if value else None


def _no_pagination(soup):
    # Reviewed inventory is a complete HTML tree, not a paged search result.
    if soup.select('.paging, .pagination, .paginator, a[rel~=next]'):
        raise ValueError('SITEX pagination appeared; implement traversal before extracting')
    for a in soup.select('a[href]'):
        if _text(a).lower() in {'siguiente', 'next', 'última', 'ultima', 'last', '»', '›'}:
            raise ValueError('Unreviewed SITEX continuation link')


class MiajadasAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        _no_pagination(soup)
        trees = soup.select('#listaplaneamientosnuevaley, #listaplaneamientosantigualey')
        if len(trees) != 2:
            raise ValueError('Missing complete SITEX planning inventory')
        entries, statuses = {}, {}
        for tree in trees:
            root = tree.find('li', recursive=False)
            label = root.find('span', recursive=False) if root else None
            if label is None or _text(label) != 'Miajadas':
                raise ValueError('Inventory belongs to a different municipality')
            for a in tree.select('a.unenlaceafiguradeplaneamiento'):
                match = re.fullmatch(
                    r"addTab\('(/SITEX/ptofiguras/viewsigcat/(\d+))','Miajadas - ([^']+)'\);",
                    a.get('onclick', ''),
                )
                image = a.select_one('img[alt]')
                state = image.get('alt') if image else None
                if not match or state not in {'Vigente', 'No vigente', 'En trámite', 'En contratación'}:
                    raise ValueError('Unrecognized SITEX instrument link/status')
                key = match[2]
                if key in statuses and statuses[key] != state:
                    raise ValueError('Conflicting inventory status')
                statuses[key] = state
                if state == 'Vigente':
                    entries[key] = {'sitex_id': key, 'url': BASE + match[1], 'referencia': match[3]}
        if not entries:
            raise ValueError('No verified current Miajadas instruments')
        return list(entries.values()), {
            'inventory_records': len(statuses),
            'excluded_not_current': sum(v != 'Vigente' for v in statuses.values()),
        }

    @staticmethod
    def parse_instrument(html, entry):
        soup = BeautifulSoup(html, 'html.parser')
        key, url = entry['sitex_id'], entry['url']
        root = soup.select_one('#divplaneamiento' + key)
        info = soup.select_one('#infoplaneamiento' + key)
        if root is None or info is None:
            raise ValueError('Missing SITEX instrument detail')
        _no_pagination(root)
        fields = {}
        for row in info.select('tr'):
            th, td = row.find('th', recursive=False), row.find('td', recursive=False)
            if th and td:
                label, value = _text(th), _text(td)
                if label in fields and fields[label] != value:
                    raise ValueError('Conflicting SITEX metadata')
                fields[label] = value
        if fields.get('Ámbito territorial') != 'Miajadas' or fields.get('Estado') != 'Vigente':
            raise ValueError('Instrument is not current Miajadas planning')
        title = fields.get('Figura urbanística')
        if not title or fields.get('Referencia') != entry['referencia']:
            raise ValueError('Instrument identity mismatch')
        documents = {}
        for a in root.select('a[href]'):
            href = urljoin(url, a['href'])
            if re.fullmatch(re.escape(BASE) + r'/SITEX/ptofiguras/downloaddocumento/\d+', href):
                label = a.get('download') or _text(a.find_parent('tr'))
            elif re.fullmatch(r'https?://doe\.juntaex\.es/pdfs/doe/.+\.pdf', href):
                label = _text(a)
            else:
                continue
            documents[href] = {'titulo': label, 'url': href, 'source_url': url}
        if not documents:
            raise ValueError('Current instrument has no source documents')
        events = []
        for row in info.select('[id^=listadotramitesplaneamiento] tr'):
            cells = row.find_all('td', recursive=False)
            if len(cells) == 2:
                events.append({'fecha_tramite': _date(_text(cells[0])), 'tramite': _text(cells[1])})
        return {
            'id': 'miajadas-sitex-' + key,
            'municipio': 'Miajadas', 'codigo_ine': '10121', 'provincia': 'Cáceres',
            'titulo': title + ' — Miajadas', 'tipo': 'planeamiento_urbanistico',
            'fase': fields['Estado'], 'referencia': fields['Referencia'], 'sitex_id': key,
            'fecha': None, 'fecha_aprob': _date(fields.get('Fecha AD')),
            'fecha_publicacion': _date(fields.get('Fecha de publicación AD')),
            'fecha_deposito': _date(fields.get('Fecha de depósito')),
            'numero_deposito': fields.get('Nº de depósito'),
            'diario_publicacion': fields.get('Diario de publicación AD'),
            'url': url, 'source': 'sitex_junta_extremadura',
            'origen': 'registro_oficial_planeamiento',
            'organismo_fuente': 'Junta de Extremadura — SITEX',
            'documentos': list(documents.values()), 'tramites': events,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'limitaciones': LIMITATIONS,
        }

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-miajadas/1.0'

            def fetch(url, name, data=None):
                # POST only performs the same public municipality search as SITEX's UI.
                method = 'POST' if data else 'GET'
                with session.request(method, url, data=data, timeout=40, stream=True) as response:
                    response.raise_for_status()
                    content = bytearray()
                    for chunk in response.iter_content(65536):
                        content.extend(chunk)
                        if len(content) > 4_000_000:
                            raise ValueError('SITEX response exceeds reviewed size; no truncated extraction')
                source_urls.append(url)
                if self.config.get('capture_dir'):
                    directory = Path(self.config['capture_dir'])
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / name).write_bytes(content)
                return bytes(content).decode('utf-8')

            entries, coverage = self.parse_inventory(fetch(
                INVENTORY, 'sitex-inventory.html', {'municipioseleccionado': '378'}))
            rows = [self.parse_instrument(fetch(e['url'], 'sitex-' + e['sitex_id'] + '.html'), e)
                    for e in entries]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': source_urls,
                'inventory_search': {'municipioseleccionado': '378'}, **coverage,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of current instruments; no date-based truncation.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
