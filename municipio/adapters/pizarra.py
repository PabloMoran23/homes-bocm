"""Pizarra planning instruments in the official Junta environmental inventory.

A full snapshot of entries whose primary municipality is Pizarra, not a licence
register or a complete municipal planning register. No plan approval is inferred
from an environmental resolution. Associated documents stay on one expediente.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://www.juntadeandalucia.es/medioambiente/daepu/'
SOURCE = ROOT + 'resolucions/find?find=findResolucionesFiltered&filter5=PIZARRA'
LIMITATIONS = [
    'Cobertura parcial: inventario ambiental DAEPU, municipio principal PIZARRA; '
    'no incluye expedientes donde figure solamente en Otros Municipios.',
    'No es un inventario completo de planeamiento municipal ni de obras o licencias.',
    'Resoluciones ambientales no acreditan aprobación urbanística, vigencia ni ejecución.',
    'Fechas de resolución y publicación documental separadas; sin fecha de aprobación inferida.',
    'Sin coordenadas ni geometría verificadas; publication_ready=false.',
]


def clean(text):
    return ' '.join(text.split())


def canonical(url):
    """Remove public servlet session routing tokens from persistent provenance."""
    return re.sub(r';jsessionid=[^/?#;]+', '', url, flags=re.I)


def official(url):
    url = canonical(url)
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'www.juntadeandalucia.es'
            or not parsed.path.startswith('/medioambiente/daepu/')):
        raise ValueError('Unexpected DAEPU URL: ' + url)
    return url


def iso_date(value):
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    table = next((t for t in soup.select('table')
                  if 'Número de Expediente' in t.get_text(' ', strip=True)), None)
    if table is None:
        raise ValueError('Missing DAEPU inventory table')
    page = re.search(r'Página\s+(\d+)\s+de\s+(\d+)', table.get_text(' ', strip=True))
    if not page or not 1 <= int(page[1]) <= int(page[2]):
        raise ValueError('Missing or invalid pagination; completeness cannot be verified')
    rows = []
    for tr in table.select('tr'):
        if 'footer' in tr.get('class', []):
            continue
        cells = tr.find_all('td', recursive=False)
        if not cells:
            continue
        if len(cells) != 10:
            raise ValueError('Changed DAEPU inventory columns')
        values = [clean(c.get_text(' ', strip=True)) for c in cells]
        if values[2].upper() != 'MÁLAGA' or values[4].upper() != 'PIZARRA':
            raise ValueError('Municipality/province filter not respected')
        link = cells[9].select_one('a[href]')
        if not values[1] or not values[8] or link is None:
            raise ValueError('Incomplete planning entry')
        target = official(urljoin(url, link['href']))
        if not re.fullmatch(r'/medioambiente/daepu/resolucions/\d+', urlsplit(target).path):
            raise ValueError('Unexpected resolution link')
        rows.append({'expediente': values[8], 'titulo': values[1], 'url': target})
    if not rows:
        raise ValueError('No verified Pizarra planning entries')
    current, total = int(page[1]), int(page[2])
    next_url = None
    if current < total:
        # Build each request with the explicit filter: session-dependent pagination
        # must not accidentally fall back to the unfiltered regional inventory.
        query = parse_qs(urlsplit(url).query)
        query.update(find=['findResolucionesFiltered'], filter5=['PIZARRA'], page=[str(current + 1)])
        next_url = urlunsplit((*urlsplit(SOURCE)[:3], urlencode(query, doseq=True), ''))
    return rows, current, total, next_url


def parse_detail(html, entry):
    soup = BeautifulSoup(html, 'html.parser')
    fields = {}
    for label in soup.select('label'):
        value = label.find_next_sibling('div', class_='box')
        if value is not None:
            fields[clean(label.get_text()).rstrip(':')] = clean(value.get_text(' ', strip=True))
    if fields.get('Municipio', '').upper() != 'PIZARRA' or fields.get('Provincia', '').upper() != 'MÁLAGA':
        raise ValueError('Detail is outside Pizarra, Málaga')
    if fields.get('Número de Expediente') != entry['expediente'] or fields.get('Actuación') != entry['titulo']:
        raise ValueError('Inventory/detail identity mismatch')
    documents = []
    for tr in soup.select('table tr'):
        cells = tr.find_all('td', recursive=False)
        if 'footer' in tr.get('class', []) or not cells:
            continue
        if len(cells) != 3:
            raise ValueError('Changed document table')
        link = cells[2].select_one('a[href]')
        if link is None:
            raise ValueError('Document without link')
        kind = clean(cells[0].get_text(' ', strip=True))
        date = iso_date(clean(cells[1].get_text()))
        doc = {'tipo': kind, 'url': official(urljoin(entry['url'], link['href'])),
               'source_url': entry['url']}
        # DAEPU labels this entire column "Fecha de Resolución", including PB.
        # Retain that literal field; also identify PB as publication, never approval.
        doc['fecha_resolucion_fuente'] = date
        doc['fecha_publicacion' if kind.startswith('Publicación en BOJA') else 'fecha_resolucion'] = date
        if doc not in documents:
            documents.append(doc)
    if not documents:
        raise ValueError('No associated planning documents')
    return {**entry, 'documentos': documents, 'organo_tramitador': fields.get('Órgano Tramitador'),
            'fecha_resolucion_ficha': iso_date(fields['Fecha de Resolución'])}


def group_instruments(entries):
    grouped = {}
    for entry in entries:
        key = entry['expediente']
        if key not in grouped:
            grouped[key] = {
                'id': 'pizarra-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Pizarra', 'codigo_ine': '29080', 'provincia': 'Málaga',
                'titulo': entry['titulo'], 'tipo': 'instrumento de planeamiento urbanístico',
                'expediente': key, 'url': entry['url'], 'inventory_url': SOURCE,
                'source': 'junta_de_andalucia', 'origen': 'daepu',
                'descripcion': entry['titulo'], 'documentos': [], 'fichas_fuente': [],
                'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            }
        row = grouped[key]
        ficha = {k: entry[k] for k in ('url', 'titulo', 'organo_tramitador', 'fecha_resolucion_ficha')}
        if ficha not in row['fichas_fuente']:
            row['fichas_fuente'].append(ficha)
        for doc in entry['documentos']:
            if doc not in row['documentos']:
                row['documentos'].append(doc)
    return list(grouped.values())


class PizarraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='pizarra', config=None, base_url=''):
        if slug != 'pizarra':
            raise ValueError('This adapter only covers Pizarra (29080)')
        super().__init__(slug, config, base_url or SOURCE)

    def _fetch(self, session, url):
        url = official(url)
        response = session.get(url, timeout=45)
        response.raise_for_status()
        official(response.url)
        if not response.content or 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Empty/non-HTML official source')
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            name = 'daepu-' + hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (folder / name).write_bytes(response.content)
        self.source_urls.append(url)
        return response.content

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = []
        entries, seen, page_number, total_pages = [], set(), 0, None
        with requests.Session() as session:
            session.headers['User-Agent'] = self.config.get('user_agent', 'municipio-pizarra/1.0')
            url = SOURCE
            while url:
                page_rows, current, total, next_url = parse_inventory(self._fetch(session, url), url)
                if current != page_number + 1 or (total_pages is not None and total_pages != total):
                    raise ValueError('Inconsistent pagination; snapshot aborted')
                page_number, total_pages = current, total
                fresh = 0
                for entry in page_rows:
                    if entry['url'] in seen:
                        continue
                    seen.add(entry['url'])
                    entries.append(parse_detail(self._fetch(session, entry['url']), entry))
                    fresh += 1
                if not fresh:
                    raise ValueError('Repeated inventory page; snapshot aborted')
                url = next_url
        rows = group_instruments(entries)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'written': len(rows), 'live_records': len(rows),
                'inventory_pages': page_number, 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
