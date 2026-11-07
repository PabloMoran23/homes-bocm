"""Tuineje planning dossiers in the official archive linked by the municipality."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL = 'https://transparencia.tuineje.es/es/informacion-del-plan-insular-o-general-de-ordenacion-y-de-los-planes-y-proyectos-de-desarrollo-del'
BASE = 'https://www3.gobiernodecanarias.org/aplicaciones/archivoplaneamientopt/pages/consulta/'
INVENTORY = BASE + 'islaMunicipio.jsp?municipio=30&provincia=35'
CATEGORIES = ('urbanisticaPlaneamientoGeneral.jsp', 'urbanisticaPlaneamientoDesarrollo.jsp')
LIMITATIONS = [
    'Partial municipal coverage: only general and development planning dossiers in the linked regional archive; not a works or granted-licence register.',
    'Historical archive presence and Disponible are not proof of current legal validity or execution; annulled and superseded plans remain labelled in document titles.',
    'Document URLs are retained; PDF contents and geometries are not extracted. No inferred coordinates or phases.',
    'Counts are checked against inventory and document category totals; incomplete/paginated responses fail instead of producing a truncated snapshot.',
    'Raw approval date can denote COTMAC assumption instead: comments are retained and qualified dates are handled separately.',
]


def text(node):
    return node.get_text(' ', strip=True) if node else ''


def iso(value):
    if not value:
        return None
    return datetime.strptime(value.replace('-', '/'), '%d/%m/%Y').date().isoformat()


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    if not re.search(r'Municipio\s*:\s*TUINEJE\b', text(soup.select_one('#migas')), re.I):
        raise ValueError('Lost Tuineje public archive session')
    counts = {}
    for a in soup.select('a[href]'):
        name = urlparse(a['href']).path.rsplit('/', 1)[-1]
        if name in CATEGORIES:
            match = re.search(r'\((\d+)\)', text(a))
            if not match:
                raise ValueError('Missing inventory count')
            counts[name] = int(match[1])
    if set(counts) != set(CATEGORIES) or not sum(counts.values()):
        raise ValueError('No usable planning inventory')
    return counts


def parse_listing(html, url, expected):
    soup = BeautifulSoup(html, 'html.parser')
    if not re.search(r'Municipio\s*:\s*TUINEJE\b', text(soup.select_one('#migas')), re.I):
        raise ValueError('Wrong municipality in listing')
    table = soup.select_one('table#row')
    footer = text(table.select_one('tfoot')) if table else ''
    count = re.search(r'Total de Expedientes:\s*(\d+)', footer)
    if not count or int(count[1]) != expected:
        raise ValueError('Inventory/listing count mismatch')
    records = []
    for tr in table.select('tbody > tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 9:
            raise ValueError('Unexpected dossier columns')
        exp = text(cells[0])
        a = cells[0].select_one('a[href]')
        if not re.fullmatch(r'\d{4}/\d{4}', exp) or not a or not text(cells[3]):
            raise ValueError('Unidentified planning dossier')
        target = urljoin(url, a['href'])
        if (urlparse(target).path != urlparse(BASE + 'expedienteUrbanistico.jsp').path
                or urlparse(target).netloc != urlparse(BASE).netloc
                or parse_qs(urlparse(target).query).get('numexp') != [exp]):
            raise ValueError('Unexpected dossier link')
        records.append({
            'id': 'tuineje-plan-' + exp.replace('/', '-'), 'expediente': exp,
            'municipio': 'Tuineje', 'codigo_ine': '35030', 'provincia': 'Las Palmas',
            'titulo': text(cells[3]), 'tipo': 'instrumento de planeamiento',
            'instrumento_codigo': text(cells[1]), 'figura_codigo': text(cells[2]),
            'fecha_aprobacion_catalogo': iso(text(cells[4])),
            'fecha_publicacion': iso(text(cells[5])), 'fecha_normativa': iso(text(cells[6])),
            'url': target, 'inventory_url': INVENTORY, 'listing_url': url,
            'municipal_source_url': MUNICIPAL, 'source': 'gobierno_de_canarias',
            'origen': 'archivo_planeamiento_enlazado_por_ayuntamiento',
            'situacion_archivo': text(cells[8]), 'publication_ready': False,
            'geometry_status': 'unavailable',
        })
    if len(records) != expected or len({r['id'] for r in records}) != expected:
        raise ValueError('Incomplete or paginated dossier listing; refusing truncation')
    return records


def parse_detail(html, record):
    soup = BeautifulSoup(html, 'html.parser')
    breadcrumbs = text(soup.select_one('#migas'))
    if ('Municipio: TUINEJE' not in breadcrumbs or
            'Expediente: ' + record['expediente'] not in breadcrumbs):
        raise ValueError('Wrong or unavailable dossier detail')
    title = soup.select_one('textarea[name="asunto"]')
    if text(title) != record['titulo']:
        raise ValueError('Listing/detail title mismatch')
    comment = text(soup.select_one('textarea[name="comentario"]'))
    docs = []
    for a in soup.select('a[href]'):
        match = re.fullmatch(r"javascript:showPdf\('(\d+)'\)", a['href'])
        if not match:
            continue
        cells = a.find_parent('tr').find_all('td', recursive=False)
        docs.append({'id': match[1], 'titulo': text(a),
                     'url': urljoin(BASE, '../otros/ShowPdfServlet?iddoc=' + match[1]),
                     'source_url': record['url'],
                     'fecha_aprobacion_documento': iso(text(cells[-1]))})
    category_counts = [int(m) for m in re.findall(r'\((\d+) documentos?\)', text(soup))]
    if len(category_counts) != 5 or sum(category_counts) != len(docs) or not docs:
        raise ValueError('Incomplete or paginated document inventory; refusing truncation')
    if len({d['id'] for d in docs}) != len(docs):
        raise ValueError('Duplicate document identifiers')
    # The archive itself qualifies some dates in its comments. Never turn
    # assumption/receipt dates into approvals; preserve the raw catalogue field.
    approval = record['fecha_aprobacion_catalogo']
    if re.search(r'LA FECHA|FECHA SEÑALADA|FECHA INDICADA', comment, re.I):
        approval = None
    explicit = re.search(r'EL (\d{2}-\d{2}-\d{4}) FUE APROBADO DEFINITIVAMENTE', comment, re.I)
    if explicit:
        approval = iso(explicit[1])
    return {**record, 'fecha_aprob': approval, 'comentarios_fuente': comment,
            'fecha_aprob_provenance': 'comentario explícito' if explicit else
                ('columna Fecha aprobación del catálogo' if approval else 'fecha de catálogo cualificada; no inferida'),
            'documentos': docs}


class TuinejeAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='tuineje', config=None, base_url=''):
        super().__init__(slug, config, base_url or MUNICIPAL)

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        sources = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-tuineje/1.0 (public planning inventory)'

            def fetch(url):
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if urlparse(response.url).netloc != urlparse(url).netloc:
                    raise ValueError('Unexpected source redirect')
                response.encoding = response.apparent_encoding
                sources.append(url)
                if captures:
                    folder = Path(captures)
                    folder.mkdir(parents=True, exist_ok=True)
                    name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
                    (folder / name).write_text(response.text, encoding='utf-8')
                return response.text

            municipal = BeautifulSoup(fetch(MUNICIPAL), 'html.parser')
            if not any(
                urlparse(urljoin(MUNICIPAL, a['href']))._replace(query='') == urlparse(INVENTORY)._replace(query='')
                and parse_qs(urlparse(a['href']).query) == parse_qs(urlparse(INVENTORY).query)
                for a in municipal.select('a[href]')
            ):
                raise ValueError('Municipal provenance link disappeared')
            counts = parse_inventory(fetch(INVENTORY))
            records = []
            # Category visits set the public session context required by details.
            for category in CATEGORIES:
                url = BASE + category
                for row in parse_listing(fetch(url), url, counts[category]):
                    records.append(parse_detail(fetch(row['url']), row))
        if len({r['id'] for r in records}) != len(records):
            raise ValueError('Dossiers overlap across categories')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
        return {'count': len(records), 'source_urls': sources, 'limitations': LIMITATIONS,
                'coverage': 'complete snapshot of two archive categories, partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
