"""Partial inventory of municipal Plan Parcial publications in Córdoba's BOP.

Search results are discovery data, not licences. Only titles identifying an actual
partial plan are accepted. Publication dates come from the dated BOP URL, never
from a signature or an inferred approval. No PDF text dependency is required.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://bop.dipucordoba.es'
SEARCH = BASE + '/buscar'
ISSUER = 'Ayuntamiento de Aguilar de la Frontera'
PARAMS = {'buscar': '1', 'emisor': '389', 'texto': 'Plan Parcial',
          'porPagina': '100', 'ordenarPor': '2'}
LIMITATIONS = [
    'Partial coverage: municipal Plan Parcial titles with identifiable sectors in the BOP search, 2010 onwards.',
    'Other planning instruments, works, licences and pre-2010 archives are outside this adapter.',
    'Publication is not proof of current legal validity, construction or a granted licence.',
    'Agreement dates are not extracted; no verified coordinates or geometry.',
    'Municipal and transparency websites returned HTTP 403 during research.',
]


def normalize(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def parse_search(html, source_url):
    """Return all search notices and the advertised total, including non-projects."""
    soup = BeautifulSoup(html, 'html.parser')
    if (not soup.select('li.announcement') and
            'No se encontraron datos para los criterios de búsqueda especificados indicados.' in soup.get_text(' ', strip=True)):
        return [], 0
    ranges = set(re.findall(r'Resultados del\s+(\d+)\s+al\s+(\d+)\s+de\s+(\d+)',
                            soup.get_text(' ', strip=True)))
    if len(ranges) != 1:
        raise ValueError('BOP result count missing or ambiguous')
    start, end, total = map(int, ranges.pop())
    notices = {}
    for item in soup.select('li.announcement'):
        issuer, title, link = item.select_one('h3'), item.select_one('p'), item.select_one('a.pdf[href]')
        if not issuer or issuer.get_text(' ', strip=True) != ISSUER:
            raise ValueError('Unexpected BOP issuer; municipality filter failed')
        if not title or not link:
            raise ValueError('BOP announcement markup changed')
        url = urljoin(source_url, link['href'])
        match = re.fullmatch(r'/visor-pdf/(\d{2})-(\d{2})-(\d{4})/(BOP-A-\d{4}-\d+)\.pdf', urlparse(url).path)
        if urlparse(url).netloc != urlparse(BASE).netloc or not match:
            raise ValueError('Unexpected BOP document URL')
        day, month, year, identifier = match.groups()
        notices[url] = {'id': identifier, 'titulo': title.get_text(' ', strip=True),
                        'url': url, 'fecha_publicacion': date(int(year), int(month), int(day)).isoformat(),
                        'inventory_url': source_url, 'emisor': ISSUER}
    if total <= 0 or start != 1 or end != len(notices) or end > total:
        raise ValueError('Empty or inconsistent BOP search result range')
    return list(notices.values()), total


def plan_identity(title):
    """Keep base plans and modifications separate; exclude incidental mentions."""
    text = normalize(title)
    if not re.search(r'\bplan parcial\b', text):
        return None
    if re.search(r'ordenanza|bases|licitaci|contrataci|subasta|reparcelaci|estudio de detalle|proyecto de urbanizaci', text):
        return None
    # The title must announce the instrument itself, not just mention it.
    if not re.search(r'aprobacion|informacion publica', text):
        return None
    tail = text.split('plan parcial', 1)[1]
    sector = re.search(r'\b(SR|SI)\s*-\s*(\d+)\b', tail, re.I)
    if sector:
        code = sector[1].upper() + '-' + str(int(sector[2]))
    else:
        residential = re.search(r'\bsector residencial\s+(\d+)\b', tail)
        if not residential:
            raise ValueError('Named partial plan has no unambiguous sector: ' + title)
        code = 'SR-' + str(int(residential[1]))
    modified = bool(re.search(r'modificacion|modificado', text.split('plan parcial', 1)[0]))
    # Modifications with different descriptions must not be merged just because
    # they affect the same sector. Current inventory has one notice per modification.
    suffix = '-' + hashlib.sha256(tail.encode()).hexdigest()[:12] if modified else ''
    return ('modificacion-' if modified else 'plan-') + code.lower() + suffix, code, modified


def group_plans(notices):
    grouped = {}
    for notice in notices:
        identity = plan_identity(notice['titulo'])
        if identity is None:
            continue
        key, code, modified = identity
        if key not in grouped:
            grouped[key] = {
                'id': 'aguilar-de-la-frontera-' + key,
                'municipio': 'Aguilar de la Frontera', 'codigo_ine': '14002', 'provincia': 'Córdoba',
                'titulo': ('Modificación del Plan Parcial ' if modified else 'Plan Parcial ') + code,
                'tipo': 'modificación de plan parcial' if modified else 'plan parcial',
                'sector': code, 'source': 'ayuntamiento', 'origen': 'bop_cordoba',
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'publication_ready': False, 'geometry_status': 'unavailable',
                'documentos': [],
            }
        docs = grouped[key]['documentos']
        if not any(doc['url'] == notice['url'] for doc in docs):
            docs.append(dict(notice))
    if not grouped:
        raise ValueError('No genuine named partial plans found in municipal BOP inventory')
    for row in grouped.values():
        row['documentos'].sort(key=lambda doc: (doc['fecha_publicacion'], doc['id']))
        # Date belongs to this specific publication, not the plan's approval.
        latest = row['documentos'][-1]
        row['url'] = latest['url']
        row['fecha_publicacion'] = latest['fecha_publicacion']
        row['descripcion'] = '\n'.join(doc['titulo'] for doc in row['documentos'])
    return sorted(grouped.values(), key=lambda row: row['id'])


class AguilarDeLaFronteraAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, url, params=None):
        response = requests.get(url, params=params, timeout=45,
                                headers={'User-Agent': 'municipio-aguilar-inventory/1.0'})
        response.raise_for_status()
        if urlparse(response.url).netloc != urlparse(BASE).netloc:
            raise ValueError('Unexpected source redirect')
        return response

    def _inventory(self, capture):
        source_urls = []

        def fetch(extra):
            response = self._get(SEARCH, {**PARAMS, **extra})
            source_urls.append(response.url)
            capture('search-' + str(len(source_urls)) + '.html', response.content)
            notices, total = parse_search(response.text, response.url)
            return notices, total

        notices, total = fetch({})
        if len(notices) < total:
            # Exhaust the date interval instead of assuming one page is enough.
            # A saturated single day fails loudly, never produces partial output.
            def interval(first, last):
                found, count = fetch({'fechaIni': first.isoformat(), 'fechaFin': last.isoformat()})
                if len(found) == count:
                    return found
                if first == last:
                    raise ValueError('More than 100 notices on one day: pagination required')
                mid = first + (last - first) // 2
                return interval(first, mid) + interval(mid + timedelta(days=1), last)

            notices = interval(date(2010, 1, 4), date.today())
            unique = {doc['url']: doc for doc in notices}
            if len(unique) != total:
                raise ValueError('BOP inventory changed during pagination or has unaccounted results')
            notices = list(unique.values())
        return notices, source_urls

    def backfill_proyectos(self, out_jsonl: Path):
        capture_dir = self.config.get('capture_dir')

        def capture(name, data):
            if capture_dir:
                folder = Path(capture_dir)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / name).write_bytes(data)

        notices, sources = self._inventory(capture)
        rows = group_plans(notices)
        for row in rows:
            for doc in row['documentos']:
                response = self._get(doc['url'])
                if not response.content.startswith(b'%PDF-'):
                    raise ValueError('BOP attachment is not a PDF: ' + doc['url'])
                doc['sha256'] = hashlib.sha256(response.content).hexdigest()
                doc['content_type'] = response.headers.get('Content-Type', '')
                capture(doc['id'] + '.pdf', response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'inventory_notices': len(notices),
                'documents': sum(len(row['documentos']) for row in rows),
                'source_urls': sources + [doc['url'] for row in rows for doc in row['documentos']],
                'coverage': 'partial_municipal_plan_parcial_publications_since_2010',
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'Licence extraction is outside verified coverage'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
