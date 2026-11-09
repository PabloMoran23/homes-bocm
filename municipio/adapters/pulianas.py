"""Pulianas planning instruments in the Junta's public environmental inventory.

This is partial municipal coverage, not a licence register or proof of planning
approval. All dated events belong to the environmental documents themselves.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://www.juntadeandalucia.es/medioambiente/daepu/'
SEARCH = ROOT + 'resolucions/find'
LIMITATIONS = [
    'Partial coverage: Junta environmental assessment inventory; primary municipality PULIANAS only.',
    'Not the complete municipal planning, public works or granted licence inventory.',
    'Environmental admission/inadmission labels do not prove planning approval or current validity.',
    'Document resolution/publication dates are not municipal agreement or planning approval dates.',
    'No verified project coordinates or geometry; publication_ready is false.',
]


def clean(text):
    return ' '.join(text.split())


def source_url(href, base):
    url = urljoin(base, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'www.juntadeandalucia.es' or not parsed.path.startswith('/medioambiente/daepu/'):
        raise ValueError('Unexpected source URL: ' + url)
    return re.sub(r';jsessionid=[^/?#;]+', '', url)


def inventory_url(page):
    return SEARCH + '?' + urlencode({'find': 'findResolucionesFiltered', 'filter5': 'PULIANAS', 'size': 25, 'page': page})


def iso_date(value):
    return datetime.strptime(clean(value), '%d/%m/%Y').date().isoformat()


def parse_inventory(html, expected_page=1):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table')
    if not table:
        raise ValueError('Missing environmental inventory table')
    headers = [clean(x.get_text(' ', strip=True)) for x in table.select('th')]
    if headers != ['Órgano Tramitador', 'Actuación', 'Provincia', 'Otras Provincias', 'Municipio', 'Otros Municipios', 'Tipo de Resolución', 'Fecha de Resolución', 'Número de Expediente', 'Resoluciones y Otros Documentos (*)']:
        raise ValueError('Environmental inventory schema changed')
    footer = table.select_one('tr.footer')
    pages = re.search(r'Página\s+(\d+)\s+de\s+(\d+)', footer.get_text(' ', strip=True) if footer else '')
    if not pages or int(pages[1]) != expected_page or not 1 <= int(pages[1]) <= int(pages[2]):
        raise ValueError('Missing or inconsistent pagination')
    rows = []
    for tr in table.select('tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells or 'footer' in tr.get('class', []):
            continue
        if len(cells) != 10:
            raise ValueError('Malformed inventory row')
        values = [clean(td.get_text(' ', strip=True)) for td in cells]
        if values[2].upper() != 'GRANADA' or values[4].upper() != 'PULIANAS':
            raise ValueError('Inventory returned a different municipality/province')
        link = cells[9].select_one('a[href]')
        if not link or not values[8]:
            raise ValueError('Inventory row lacks detail or expediente')
        url = source_url(link['href'], SEARCH)
        if not re.fullmatch(re.escape(ROOT) + r'resolucions/\d+', url):
            raise ValueError('Unexpected resolution detail link')
        rows.append({'url': url, 'expediente': values[8]})
    if not rows:
        raise ValueError('No usable Pulianas planning instruments')
    return rows, int(pages[2])


def parse_detail(html, url, expediente):
    soup = BeautifulSoup(html, 'html.parser')

    def field(label):
        node = next((x for x in soup.select('label') if clean(x.get_text(' ', strip=True)) == label), None)
        box = node.parent.select_one('.box') if node else None
        if box is None:
            raise ValueError('Missing detail field: ' + label)
        return clean(box.get_text(' ', strip=True))

    if field('Municipio:').upper() != 'PULIANAS' or field('Provincia:').upper() != 'GRANADA':
        raise ValueError('Detail municipality/province mismatch')
    if field('Número de Expediente:') != expediente:
        raise ValueError('Detail expediente mismatch')
    title = field('Actuación:')
    if not re.search(r'\bPLAN (?:PARCIAL|ESPECIAL|GENERAL)\b', title, re.I):
        raise ValueError('Detail no longer identifies a planning instrument')
    table = soup.select_one('table')
    if not table or [clean(x.get_text(' ', strip=True)) for x in table.select('th')] != ['Tipo', 'Fecha de Resolución', 'Enlace al documento']:
        raise ValueError('Missing document inventory')
    # Current detail inventories are unpaginated. Fail if that contract changes.
    if re.search(r'Página\s+\d+\s+de\s+\d+', table.get_text(' ', strip=True)) or soup.select('a[rel="next"]'):
        raise ValueError('Detail document pagination requires review')
    docs = {}
    for tr in table.select('tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells or 'footer' in tr.get('class', []):
            continue
        if len(cells) != 3:
            raise ValueError('Malformed document row')
        kind = clean(cells[0].get_text(' ', strip=True))
        event_date = iso_date(cells[1].get_text(' ', strip=True))
        links = cells[2].select('a[href]')
        if not links or not kind:
            raise ValueError('Missing document link/type')
        for a in links:
            target = source_url(a['href'], url)
            if not re.fullmatch(re.escape(ROOT) + r'resolucions/downloadFile/[\w-]+', target):
                raise ValueError('Unexpected document link')
            # The table labels all dates "Fecha de Resolución", including BOJA.
            # Retain that literal provenance; it is neither the BOJA issue date
            # nor a planning approval date (verified against the linked PDFs).
            docs[target] = {'titulo': kind, 'tipo_fuente': kind, 'url': target,
                            'source_url': url, 'fecha_resolucion_fuente': event_date,
                            'fecha_publicacion': None}
    if not docs:
        raise ValueError('Planning instrument has no source documents')
    return {
        'id': 'pulianas-plan-' + hashlib.sha256(expediente.encode()).hexdigest()[:16],
        'municipio': 'Pulianas', 'codigo_ine': '18165', 'provincia': 'Granada',
        'titulo': title, 'tipo': 'instrumento de planeamiento urbanístico',
        'expediente': expediente, 'organo_tramitador': field('Órgano Tramitador:'),
        'source': 'junta_de_andalucia', 'origen': 'inventario_evaluacion_ambiental_estrategica',
        'url': url, 'source_urls': [url], 'inventory_url': inventory_url(1),
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'fecha_resolucion_ficha': iso_date(field('Fecha de Resolución:')),
        'fase': None, 'documentos': list(docs.values()),
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False, 'coverage': 'partial_environmental_planning_inventory',
    }


class PulianasAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='pulianas', config=None, base_url=''):
        super().__init__(slug, config, base_url or ROOT)

    def _fetch(self, session, url, capture):
        response = session.get(url, timeout=40)
        response.raise_for_status()
        source_url(response.url, url)
        html = response.content.decode('utf-8')
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(out_jsonl, records):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        grouped, seen = {}, set()
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-pulianas/1.0 (public planning inventory)'
            page, total = 1, None
            while True:
                entries, page_total = parse_inventory(self._fetch(session, inventory_url(page), f'inventory-{page}.html'), page)
                if page_total > 100 or (total is not None and page_total != total):
                    raise ValueError('Inventory pagination changed or exceeds safety bound; no partial output')
                total = page_total
                for entry in entries:
                    if entry['url'] in seen:
                        raise ValueError('Repeated inventory entry; pagination may be looping')
                    seen.add(entry['url'])
                    detail = self._fetch(session, entry['url'], 'detail-' + entry['url'].rsplit('/', 1)[1] + '.html')
                    record = parse_detail(detail, **entry)
                    key = record['expediente']
                    if key in grouped:
                        old = grouped[key]
                        old['source_urls'] = sorted(set(old['source_urls'] + record['source_urls']))
                        documents = {(d['url'], d['tipo_fuente'], d['fecha_resolucion_fuente']): d for d in old['documentos'] + record['documentos']}
                        old['documentos'] = list(documents.values())
                    else:
                        grouped[key] = record
                if page == total:
                    break
                page += 1
        records = sorted(grouped.values(), key=lambda row: row['expediente'])
        self._write(out_jsonl, records)
        return {'status': 'ok', 'rows': len(records), 'pages': total,
                'source_urls': [inventory_url(p) for p in range(1, total + 1)] + sorted(seen),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current inventory snapshot, including all documents per case.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
