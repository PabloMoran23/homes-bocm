"""Montijo (Badajoz): official SITEX planning inventory linked by the council."""
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
SOURCE = BASE + '/SITEX/planeamiento'
INVENTORY = BASE + '/SITEX/ptofiguras/listadoresultadossigcat'
LIMITATIONS = [
    'Only the current SITEX inventory for Montijo, including historical and pending instruments; not all municipal works.',
    'SITEX is an informative regional register, not a certified statement of legal validity.',
    'Attachment links are retained; their full contents and continued availability are not verified by the scraper.',
    'No granted licence register, coordinates or inferred dates; some instruments have no attachments or dates.',
    'The shared classifier may leave references without numbers pending; source references are not modified to bypass that guard.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _no_pagination(soup):
    # The reviewed endpoint returns a complete nested tree. Fail if it gains paging.
    if soup.select('.pagination, .paging, .paginator, a[rel~=next], a[rel~=prev]'):
        raise ValueError('Unreviewed pagination in SITEX; refusing partial inventory')
    for a in soup.select('a[href]'):
        if re.search(r'(?:/page[:/]|[?&]page=)', a['href']) or _text(a).lower() in {'siguiente', 'next', '»', '›'}:
            raise ValueError('Unreviewed pagination in SITEX')


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    _no_pagination(soup)
    selected = soup.select_one('#PtofiguraMunicipio option[selected][value="123"]')
    if not selected or selected.get('value') != '123' or _text(selected) != 'Montijo':
        raise ValueError('SITEX inventory is not scoped to Montijo (internal municipality 123)')
    items = {}
    for a in soup.select('a.unenlaceafiguradeplaneamiento'):
        match = re.search(r"addTab\('(/SITEX/ptofiguras/viewsigcat/(\d+))','Montijo - ([^']+)'", a.get('onclick', ''))
        if not match or not a.get('title'):
            raise ValueError('Unexpected planning tree entry')
        path, key, reference = match.groups()
        items[key] = {'source_id': key, 'url': BASE + path, 'referencia': reference,
                      'titulo_inventario': a['title']}
    if not items:
        raise ValueError('Empty or changed SITEX planning tree')
    return list(items.values())


def _date(value):
    if not value or value in {'-', '00/00/0000'}:
        return None
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


def parse_detail(html, item):
    soup = BeautifulSoup(html, 'html.parser')
    _no_pagination(soup)
    key = item['source_id']
    info = soup.find(id='infoplaneamiento' + key)
    if info is None:
        raise ValueError(f'Missing planning detail {key}')
    fields = {}
    for tr in info.select('tr'):
        th, td = tr.find('th', recursive=False), tr.find('td', recursive=False)
        if th and td:
            fields[_text(th)] = _text(td)
    if fields.get('Ámbito territorial') != 'Montijo' or fields.get('Referencia') != item['referencia']:
        raise ValueError(f'Wrong municipality/reference in detail {key}')
    if not fields.get('Figura urbanística') or not fields.get('Estado'):
        raise ValueError(f'Missing instrument metadata {key}')
    row = {
        **item, 'id': 'montijo-sitex-' + key, 'expediente': fields['Referencia'],
        'municipio': 'Montijo', 'codigo_ine': '06088',
        'provincia': 'Badajoz', 'titulo': fields['Figura urbanística'],
        'tipo': 'instrumento de planeamiento urbanístico', 'estado_fuente': fields['Estado'],
        'source': 'junta_extremadura_sitex', 'origen': 'inventario_planeamiento',
        'inventory_url': INVENTORY, 'inventory_parameters': {'municipioseleccionado': '123'},
        'publication_ready': False, 'geometry_status': 'unavailable',
        'tramites': [], 'documentos': [],
    }
    docs = {}
    for tr in info.select('tr[id^=filatramite]'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 2:
            raise ValueError('Changed procedure row')
        event = {'tramite': _text(cells[1]), 'fecha': _date(_text(cells[0]))}
        links = []
        for a in cells[1].select('a[href]'):
            target = urljoin(item['url'], a['href'])
            if urlparse(target).scheme not in {'http', 'https'}:
                raise ValueError('Unexpected document scheme')
            links.append(target)
            docs.setdefault(target, {'titulo': _text(a) or event['tramite'], 'url': target,
                                     'origen': 'tramite', 'source_url': item['url']})
        if links:
            event['document_urls'] = links
        row['tramites'].append(event)
    archive = soup.find(id='archivosplaneamiento' + key)
    if archive:
        for a in archive.select('a[href]'):
            target = urljoin(item['url'], a['href'])
            if '/ptofiguras/downloaddocumento/' not in urlparse(target).path:
                raise ValueError('Unreviewed attachment link')
            tr = a.find_parent('tr')
            title = a.get('download') or (_text(tr.find('td')) if tr else _text(a))
            docs.setdefault(target, {'titulo': title, 'url': target,
                                     'origen': 'archivo_instrumento', 'source_url': item['url']})
    row['documentos'] = list(docs.values())
    row['document_coverage'] = 'linked_documents' if docs else 'metadata_only'
    for source, dest in [('Fecha AD', 'fecha_aprob'), ('Fecha de publicación AD', 'fecha_publicacion')]:
        date = _date(fields.get(source))
        if date:
            row[dest] = date
    if fields.get('Diario de publicación AD'):
        row['diario_publicacion'] = fields['Diario de publicación AD']
    return row


class MontijoAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, name, data=None):
        response = session.post(url, data=data, timeout=45) if data else session.get(url, timeout=45)
        response.raise_for_status()
        if urlparse(response.url).hostname != 'sitex.juntaex.es':
            raise ValueError('Unexpected SITEX redirect')
        response.encoding = 'utf-8'
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'municipio-montijo-inventory/1.0',
                                    'X-Requested-With': 'XMLHttpRequest'})
            html = self._fetch(session, INVENTORY, 'sitex-inventory.html', {'municipioseleccionado': '123'})
            items = parse_inventory(html)
            rows = [parse_detail(self._fetch(session, item['url'], 'sitex-' + item['source_id'] + '.html'), item)
                    for item in items]
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'coverage': 'current_sitex_municipal_tree',
                'source_urls': [SOURCE, INVENTORY] + [r['url'] for r in rows], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full refresh; no timestamp filter silently dropping historical instruments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
