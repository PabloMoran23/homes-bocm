"""Casabermeja planning instruments in the official Junta EAE inventory.

Environmental resolutions are documents of an instrument, never planning approvals.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://www.juntadeandalucia.es/medioambiente/daepu/'
INVENTORY = ROOT + 'resolucions/find'
LIMITATIONS = [
    'Cobertura parcial: instrumentos con resoluciones EAE publicados por la Junta; no es el registro municipal completo ni acredita vigencia.',
    'La web municipal respondió HTTP 202 sin contenido en la investigación; PGOM y otros instrumentos municipales no cubiertos.',
    'Fechas de resolución ambiental; no se infieren fechas de publicación, acuerdo municipal o aprobación urbanística.',
    'Sin licencias concedidas ni geometría verificada; no se generan coordenadas.',
]


def clean(text):
    return ' '.join(text.split())


def canonical(url):
    return re.sub(r';jsessionid=[^/?#]*', '', url, flags=re.I)


def expediente(text):
    value = clean(text).strip('() ')
    if not re.fullmatch(r'EA/MA/\d+/\d+', value):
        raise ValueError('Unexpected environmental expediente: ' + text)
    return value


def iso(text):
    return datetime.strptime(clean(text), '%d/%m/%Y').date().isoformat()


def official(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'www.juntadeandalucia.es' or not parsed.path.startswith('/medioambiente/daepu/'):
        raise ValueError('Unexpected source URL: ' + url)
    return url


def parse_inventory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    paging = re.search(r'Página\s+(\d+)\s+de\s+(\d+)', soup.get_text(' ', strip=True))
    if not paging:
        raise ValueError('Missing inventory pagination metadata')
    page, pages = map(int, paging.groups())
    if not 1 <= page <= pages:
        raise ValueError('Invalid page count')
    headers = [clean(th.get_text(' ', strip=True)) for th in soup.select('table th')]
    if headers[:5] != ['Órgano Tramitador', 'Actuación', 'Provincia', 'Otras Provincias', 'Municipio']:
        raise ValueError('Changed inventory schema')
    rows = []
    for tr in soup.select('table tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells or 'footer' in tr.get('class', []):
            continue
        if len(cells) != 10:
            raise ValueError('Unexpected inventory row width')
        values = [clean(c.get_text(' ', strip=True)) for c in cells]
        # Fail if the municipal filter is ignored: never collect nearby towns.
        if values[2].upper() != 'MÁLAGA' or values[4].upper() != 'CASABERMEJA':
            raise ValueError('Municipality/province filter mismatch')
        link = cells[9].select_one('a[href]')
        if not link:
            raise ValueError('Resolution without detail link')
        detail = official(canonical(urljoin(url, link['href'])))
        if not re.fullmatch(re.escape(ROOT) + r'resolucions/\d+', detail):
            raise ValueError('Unexpected detail identifier')
        title_match = re.search(r'\b(MODIFICACIÓN\b.*|PLAN\s+(?:PARCIAL|ESPECIAL)\b.*)', values[1], re.I)
        if not title_match:
            raise ValueError('Unreviewed planning instrument type: ' + values[1])
        rows.append({'expediente': expediente(values[8]), 'titulo_instrumento': title_match[0],
                     'titulo': values[1], 'tipo': values[6], 'fecha_resolucion': iso(values[7]),
                     'organo_tramitador': values[0], 'url': detail, 'inventory_url': url})
    if not rows:
        raise ValueError('Empty inventory requires review')
    return rows, page, pages


def parse_documents(html, url, expected):
    soup = BeautifulSoup(html, 'html.parser')
    fields = {}
    for label in soup.select('label'):
        value = label.parent.select_one('.box')
        if value:
            fields[clean(label.get_text())] = clean(value.get_text(' ', strip=True))
    if fields.get('Municipio:', '').upper() != 'CASABERMEJA' or fields.get('Provincia:', '').upper() != 'MÁLAGA':
        raise ValueError('Detail municipality/province mismatch')
    if expediente(fields.get('Número de Expediente:', '')) != expected['expediente']:
        raise ValueError('Detail expediente mismatch')
    if iso(fields.get('Fecha de Resolución:', '')) != expected['fecha_resolucion']:
        raise ValueError('Detail resolution date mismatch')
    docs = {}
    for tr in soup.select('table tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 3:
            continue
        for a in cells[2].select('a[href]'):
            target = official(canonical(urljoin(url, a['href'])))
            if '/resolucions/downloadFile/' not in target:
                raise ValueError('Unexpected environmental document link')
            title = clean(cells[0].get_text(' ', strip=True))
            source_date = iso(cells[1].get_text())
            # BOJA attachment rows use the same column for the announcement date;
            # that value must not become a gazette publication/resolution date.
            docs[target] = {'titulo': title,
                            'fecha_fuente': source_date,
                            'campo_fecha_fuente': 'Fecha de Resolución',
                            'fecha_resolucion': None if 'Publicación en BOJA' in title else source_date,
                            'url': target, 'source_url': url,
                            'procedencia': 'Junta de Andalucía — resolución ambiental'}
    if not docs:
        raise ValueError('No environmental documents on detail')
    return list(docs.values())


def group_instruments(resolutions):
    grouped = {}
    for resolution in resolutions:
        key = resolution['expediente']
        row = grouped.setdefault(key, {
            'id': 'casabermeja-eae-' + key.lower().replace('/', '-'),
            'municipio': 'Casabermeja', 'codigo_ine': '29039', 'provincia': 'Málaga',
            'expediente_ambiental': key, 'titulo': resolution['titulo_instrumento'],
            'tipo': 'planeamiento_urbanistico', 'url': resolution['url'],
            'inventory_url': resolution['inventory_url'], 'source': 'junta_de_andalucia',
            'origen': 'inventario_evaluacion_ambiental_estrategica',
            'resoluciones': [], 'documentos': [], 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'geometry_status': 'unavailable', 'geometry': None, 'lat': None, 'lon': None,
            'publication_ready': False, 'limitaciones': LIMITATIONS,
        })
        # IDs are resolution URLs; duplicate rows across pages cannot add documents twice.
        if any(r['url'] == resolution['url'] for r in row['resoluciones']):
            continue
        row['resoluciones'].append({k: v for k, v in resolution.items() if k not in ('documentos', 'titulo_instrumento')})
        known = {d['url'] for d in row['documentos']}
        row['documentos'].extend(d for d in resolution['documentos'] if d['url'] not in known)
    return list(grouped.values())


def write_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    temp.replace(path)


class CasabermejaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl):
        capture = self.config.get('capture_dir')
        sources = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-casabermeja/1.0'

            def fetch(url):
                official(url)
                response = session.get(url, timeout=40)
                response.raise_for_status()
                official(response.url)
                if response.status_code != 200 or not response.content:
                    raise ValueError('Empty or incomplete source: ' + url)
                sources.append(url)
                if capture:
                    directory = Path(capture)
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / f'source-{len(sources):03}.html').write_bytes(response.content)
                return response.content

            resolutions, seen = [], set()
            page, total_pages = 1, None
            while True:
                url = INVENTORY + '?' + urlencode({'find': 'findResolucionesFiltered', 'filter5': 'CASABERMEJA', 'page': page, 'size': 10})
                batch, current, pages = parse_inventory(fetch(url), url)
                if current != page or (total_pages is not None and pages != total_pages):
                    raise ValueError('Inconsistent pagination; retry snapshot')
                total_pages = pages
                new = [r for r in batch if r['url'] not in seen]
                if not new:
                    raise ValueError('Repeated inventory page')
                for row in new:
                    seen.add(row['url'])
                    row['documentos'] = parse_documents(fetch(row['url']), row['url'], row)
                    resolutions.append(row)
                if page == pages:
                    break
                page += 1
        rows = group_instruments(resolutions)
        write_rows(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'resolutions': len(resolutions),
                'pages': total_pages, 'source_urls': sources, 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current inventory snapshot; no watermark that drops older documents.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        write_rows(out_jsonl, [])
        return {'rows': 0, 'status': 'disabled', 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
