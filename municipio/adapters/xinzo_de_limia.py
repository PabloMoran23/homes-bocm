"""Xinzo de Limia planning instruments from the official Xunta register."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://territorioeurbanismo.xunta.gal/es/territorio-y-urbanismo/registro-de-ordenacion-del-territorio-y-urbanismo/buscador'
SOURCE = BASE + '?provincia=32&concello=696'
HEADERS = ['Instrumento', 'Tipo', 'Título', 'Fecha inscripción', 'Núm. Registro',
           'Provincia', 'Competencia de aprobación', 'Fecha de aprobación',
           'Fecha publicación DOGA', 'Fecha publicación BOP', 'Observaciones', 'Documento']


def source_date(value):
    if value in ('', '---'):
        return None
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


def parse_inventory(html, source_url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    for field, value, label in [('provincia', '32', 'Ourense'), ('concello', '696', 'Xinzo de Limia')]:
        selected = soup.select_one(f'select[name="{field}"] option[selected]')
        if not selected or selected.get('value') != value or selected.get_text(strip=True) != label:
            raise ValueError('Register municipality/province filter missing or changed')
    table = soup.select_one('table#edit-table')
    if not table or [h.get_text(' ', strip=True) for h in table.select('thead th')] != HEADERS:
        raise ValueError('Planning register table schema changed')
    records = []
    for tr in table.select('tbody tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != len(HEADERS):
            raise ValueError('Unexpected planning register row')
        values = [c.get_text(' ', strip=True) for c in cells]
        instrument, subtype, title, inscription, number, province, authority, approval, dog, bop, notes, _ = values
        if province != 'Ourense' or 'XINZO DE LIMIA' not in title.upper():
            raise ValueError('Register returned a different municipality')
        if not instrument or not re.fullmatch(r'(?:RPG/\d+/\d{4}|ROTPG/(?:P|OT)/\d+/\d{4})', number):
            raise ValueError('Missing instrument or unrecognized register identifier')
        documents = []
        for a in cells[11].select('a[href]'):
            link = urljoin(source_url, a['href'])
            if urlparse(link).hostname != 'www.planeamentourbanistico.xunta.es':
                raise ValueError('Unexpected document provenance')
            documents.append({'titulo': a.get_text(' ', strip=True), 'url': link,
                              'source_url': source_url, 'registro': number})
        records.append({
            'id': 'xinzo-de-limia-plan-' + number.replace('/', '-').lower(),
            'municipio': 'Xinzo de Limia', 'codigo_ine': '32032', 'provincia': 'Ourense',
            'titulo': title, 'tipo': instrument, 'subtipo_registro': subtype or None,
            'registro': number, 'competencia_aprobacion': authority,
            'fecha': None, 'fecha_inscripcion': source_date(inscription),
            'fecha_aprob': source_date(approval), 'fecha_publicacion': None,
            'fecha_publicacion_dog': source_date(dog), 'fecha_publicacion_bop': source_date(bop),
            'observaciones': notes or None, 'url': SOURCE, 'source_url': source_url,
            'source': 'xunta', 'origen': 'registro_oficial_planeamiento_xunta',
            'documentos': documents, 'document_status': 'linked' if documents else 'not_linked_in_register',
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    if not records:
        raise ValueError('No usable planning instruments; review source before replacing output')
    # Drupal can expose only numbered links as well as rel=next. Visit every
    # discovered page; preserve municipality filters even if pager omits them.
    pages = set()
    for a in soup.select('.pagination a[href], .pager a[href], a[rel="next"]'):
        target = urlparse(urljoin(source_url, a['href']))
        if target.hostname != urlparse(BASE).hostname or target.path != urlparse(BASE).path:
            raise ValueError('Unexpected pagination target')
        query = parse_qs(target.query)
        page = query.get('page', ['0'])
        if len(page) != 1 or not page[0].isdigit():
            raise ValueError('Unrecognized pagination')
        for key, expected in [('provincia', '32'), ('concello', '696')]:
            if key in query and query[key] != [expected]:
                raise ValueError('Pagination changes municipality filter')
        pages.add(BASE + '?' + urlencode({'provincia': '32', 'concello': '696', 'page': int(page[0])}))
    return records, pages


class XinzoDeLimiaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=(10, 35), headers={
            'User-Agent': 'municipio-xinzo-de-limia/1.0 (public planning inventory)'})
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(BASE).hostname or urlparse(response.url).path != urlparse(BASE).path:
            raise ValueError('Unexpected register redirect')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            page = parse_qs(urlparse(url).query).get('page', ['0'])[0]
            (directory / f'xunta-inventory-{page}.html').write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(out_jsonl, records):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
        temp.replace(output)

    def backfill_proyectos(self, out_jsonl):
        pending = {SOURCE}
        visited, signatures, records = set(), set(), {}
        while pending:
            url = sorted(pending)[0]
            pending.remove(url)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Pagination safety limit reached; output not replaced')
            rows, pages = parse_inventory(self._fetch(url), url)
            signature = tuple(row['id'] for row in rows)
            if signature in signatures:
                raise ValueError('Repeated inventory page; pagination may be ignored')
            signatures.add(signature)
            visited.add(url)
            for row in rows:
                key = row['id']
                if key in records:
                    prior = records[key]
                    ignored = {'documentos', 'source_url', 'document_status'}
                    if {k: v for k, v in prior.items() if k not in ignored} != {k: v for k, v in row.items() if k not in ignored}:
                        raise ValueError('Conflicting entries for one planning instrument')
                    links = {d['url']: d for d in prior['documentos'] + row['documentos']}
                    prior['documentos'] = list(links.values())
                    prior['document_status'] = 'linked' if links else 'not_linked_in_register'
                else:
                    records[key] = row
            # Page zero and the initial URL are equivalent.
            visited.add(BASE + '?provincia=32&concello=696&page=0')
            pending.update(pages - visited)
        self._write(out_jsonl, list(records.values()))
        return {'status': 'ok', 'rows': len(records), 'source_urls': sorted(visited - {BASE + '?provincia=32&concello=696&page=0'}),
                'coverage': 'official regional planning register filtered to Xinzo de Limia; partial municipal coverage'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
