"""Municipal planning document inventory; one record per instrument, not per PDF."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://transparencia.benacazon.es/es/transparencia/'
          'indicadores-de-transparencia/indicador/'
          'Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00005')
PAGE_PARAM = 'pagegalleryfiles-1-1'
DOC_ROOT = '/export/sites/benacazon/es/transparencia/.galleries/IND-50-/'
SECTIONS = {
    'NORMAS SUBSIDIARIAS': ('nnss', 'Normas Subsidiarias de Benacazón'),
    'Información': ('pgou', 'Plan General de Ordenación Urbana de Benacazón'),
    'Ordenación': ('pgou', 'Plan General de Ordenación Urbana de Benacazón'),
    'Aprobación Inicial del PGOU, planimetría':
        ('pgou', 'Plan General de Ordenación Urbana de Benacazón'),
    'Aprobación Inicial del PGOU en el BOP':
        ('pgou', 'Plan General de Ordenación Urbana de Benacazón'),
}
LIMITATIONS = [
    'Cobertura parcial: inventario documental NNSS/PGOU del indicador municipal, no todos los expedientes ni obras.',
    'Las secciones Proyecto y Aprobación Inicial reutilizan planos AVANCE; se conservan sus etiquetas sin inferir fase o vigencia.',
    'No se extraen fechas de publicación/acuerdo/aprobación de los PDF ni del CMS.',
    'Sin registro de licencias concedidas, sin coordenadas y sin geocodificación.',
    'OpenCMS genera enlaces Siguiente fuera de rango al compartir parámetro entre galerías; se respeta Última de cada galería.',
]


def page_url(number):
    return SOURCE if number == 1 else f'{SOURCE}?{PAGE_PARAM}={number}'


def parse_inventory(html: str, url: str):
    """Return grouped documents and all advertised gallery pages (including last)."""
    soup = BeautifulSoup(html, 'html.parser')
    pages = set()
    for pagination in soup.select('.pagination'):
        numbers = []
        last_number = None
        numbered = []
        for a in pagination.select('a[href]'):
            href = a['href']
            if href.startswith('#'):
                continue
            target = urlparse(urljoin(url, href))
            query = parse_qs(target.query)
            if (target.hostname != urlparse(SOURCE).hostname
                    or target.path.rstrip('/') != urlparse(SOURCE).path
                    or set(query) != {PAGE_PARAM}
                    or len(query[PAGE_PARAM]) != 1
                    or not query[PAGE_PARAM][0].isdigit()):
                raise ValueError('Unrecognized inventory pagination; refusing partial coverage')
            number = int(query[PAGE_PARAM][0])
            if not 1 <= number <= 100:
                raise ValueError('Pagination exceeds reviewed safety bound; refusing truncation')
            numbers.append(number)
            if 'lastpagelink' in a.get('class', []):
                last_number = number
            if a.get_text(strip=True).isdigit():
                numbered.append(number)
        # OpenCMS incorrectly generates Next=N+1 for the smaller galleries
        # when N exceeds their last page. Respect each gallery's Last link.
        # At its actual last page, Last is a fragment and numbered links give
        # the bound. Never interpret that erroneous Next as new inventory.
        last = pagination.select_one('a.lastpagelink[href]')
        if last is not None and last['href'].startswith('#'):
            if not numbered:
                raise ValueError('No numbered pages at end of gallery')
            last_number = max(numbered)
        bound = last_number if last_number is not None else max(numbers, default=1)
        pages.update(range(1, bound + 1))

    groups = {}
    for a in soup.select('a[href]'):
        target = urldefrag(urljoin(url, a['href']))[0]
        parsed = urlparse(target)
        if (parsed.hostname != urlparse(SOURCE).hostname
                or not parsed.path.startswith(DOC_ROOT)
                or not parsed.path.lower().endswith('.pdf')):
            continue
        # Heading elements can themselves wrap the link (the BOP attachment).
        wrapper = a.find_parent(['h3', 'h4'])
        heading = (wrapper if wrapper is not None else a).find_previous(['h3', 'h4'])
        if not heading:
            continue
        section = heading.get_text(' ', strip=True)
        if section not in SECTIONS:
            continue
        key, title = SECTIONS[section]
        expected = DOC_ROOT + ('pgou/' if key == 'nnss' else 'avance-pgou/')
        if not parsed.path.startswith(expected):
            raise ValueError('Document moved to a different instrument section')
        group = groups.setdefault(key, {'titulo': title, 'documentos': {}})
        document = group['documentos'].setdefault(target, {
            'titulo': a.get_text(' ', strip=True), 'url': target,
            'secciones_fuente': [], 'source_urls': [],
        })
        for field, value in [('secciones_fuente', section), ('source_urls', url)]:
            if value not in document[field]:
                document[field].append(value)
    if not groups:
        raise ValueError('No supported planning documents; source may have changed')
    return groups, pages


class BenacazonAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        pending, visited, instruments = {1}, set(), {}
        capture = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'municipio-benacazon/1.0'})
            while pending:
                number = min(pending)
                pending.remove(number)
                url = page_url(number)
                response = session.get(url, timeout=40)
                response.raise_for_status()
                final = urlparse(response.url)
                if (final.scheme != 'https' or final.hostname != urlparse(SOURCE).hostname
                        or final.path.rstrip('/') != urlparse(SOURCE).path
                        or parse_qs(final.query) != parse_qs(urlparse(url).query)):
                    raise ValueError('Unexpected inventory redirect')
                groups, pages = parse_inventory(response.text, url)
                # The first gallery (NNSS) has the largest page count. Detect
                # servers ignoring the requested page, rather than deduplicating it away.
                soup = BeautifulSoup(response.text, 'html.parser')
                current = soup.select_one('.pagination .active a')
                if current and current.get_text(strip=True) != str(number):
                    raise ValueError('Requested gallery page was not served')
                if capture:
                    dest = Path(capture)
                    dest.mkdir(parents=True, exist_ok=True)
                    (dest / f'inventory-{number}.html').write_text(response.text, encoding='utf-8')
                visited.add(number)
                pending.update(pages - visited)
                for key, group in groups.items():
                    record = instruments.setdefault(key, {
                        'id': f'benacazon-planeamiento-{key}',
                        'titulo': group['titulo'], 'municipio': 'Benacazón',
                        'codigo_ine': '41015', 'provincia': 'Sevilla',
                        'tipo': 'planeamiento_urbanistico', 'url': SOURCE,
                        'inventory_url': SOURCE, 'source': 'ayuntamiento',
                        'origen': 'inventario_documental_planeamiento',
                        'publication_ready': False, 'geometry_status': 'unavailable',
                        'limitaciones': LIMITATIONS, 'documentos': {},
                    })
                    for link, doc in group['documentos'].items():
                        existing = record['documentos'].setdefault(link, doc)
                        for field in ('source_urls', 'secciones_fuente'):
                            existing[field] = sorted(set(existing[field] + doc[field]))
        rows = []
        for key in sorted(instruments):
            row = instruments[key]
            row['documentos'] = [row['documentos'][u] for u in sorted(row['documentos'])]
            rows.append(row)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows),
                'source_urls': [page_url(n) for n in sorted(visited)],
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Snapshot refresh: crawl every advertised page again, no date watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
