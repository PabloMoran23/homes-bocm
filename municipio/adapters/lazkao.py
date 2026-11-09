"""Municipal NNSS and PGOU document inventories; one row per instrument."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.lazkao.eus'
NORMAS = BASE + '/es/ayuntamiento/normas-subsidiarias.html'
VIEWER = 'https://herrigis.gis-cdn.net/lazkao_aass/index_es.html'
PGOU = BASE + '/es/pgou/inicio-pgou.html'
DIAGNOSTICO = BASE + '/es/pgou/diagnostico-pgou.html'
LIMITATIONS = [
    'Cobertura parcial: inventarios NNSS y diagnóstico PGOU; no histórico de modificaciones, obras o licencias.',
    'Sin fechas de acuerdo/aprobación verificadas; la fecha del catálogo de documentos no se atribuye al plan.',
    'Cartografía AIU del visor no asignada como geometría de los instrumentos; sin coordenadas inferidas.',
    'No se afirma vigencia jurídica consolidada ni aprobación del nuevo PGOU.',
    'El sitio contiene texto ajeno inyectado, también en el prefijo de la respuesta PDF del diagnóstico; integridad no certificada.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # Fail closed if either reviewed single-page inventory becomes paginated.
    for a in soup.select('a[href]'):
        href = a['href']
        if href in ('', '#'):
            continue
        if (a.find_parent(class_='pagination') is not None
                or 'next' in a.get('rel', [])
                or re.search(r'[?&](?:limitstart|start|page)=', href)
                or a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'hurrengoa'}):
            raise ValueError('Inventory pagination changed; review required before extracting a partial snapshot')
    return soup


def parse_normas(page_html, inventory_html):
    page = _soup(page_html)
    frame = page.select_one('iframe[src]')
    if not frame or urljoin(NORMAS, frame['src']) != VIEWER:
        raise ValueError('Municipal NNSS viewer provenance changed')
    soup = _soup(inventory_html)
    section = soup.select_one('#deskarga')
    if not section or 'Normas Subsidiarias' not in soup.get_text(' ', strip=True):
        raise ValueError('NNSS document inventory missing')
    docs = {}
    for a in section.select('a[href]'):
        url = quote(urljoin(VIEWER, a['href']), safe=':/%?=&,')
        parsed = urlparse(url)
        if parsed.path.lower().endswith('.pdf'):
            if parsed.hostname != 'herrigis.gis-cdn.net' or not parsed.path.startswith('/lazkao_aass/dokumentazioa/'):
                raise ValueError('Unexpected NNSS document host/path')
            docs[url] = {'titulo': a.get_text(' ', strip=True), 'url': url, 'source_url': VIEWER}
    titles = ' '.join(d['titulo'] for d in docs.values()).lower()
    if 'memoria' not in titles or 'normas generales' not in titles:
        raise ValueError('NNSS core documents missing')
    return _record('nnss', 'Normas Subsidiarias de Lazkao', NORMAS, list(docs.values()),
                   [NORMAS, VIEWER])


def parse_pgou(start_html, inventory_html):
    start = _soup(start_html)
    article = start.select_one('.item-page, article')
    if not article or not any('Plan General de Ordenación Urbana' in h.get_text(' ', strip=True)
                              for h in article.select('h1,h2')):
        raise ValueError('PGOU identity missing from municipal page')
    if not any(urljoin(PGOU, a['href']) == DIAGNOSTICO for a in start.select('a[href]')):
        raise ValueError('PGOU diagnosis inventory no longer linked by municipality')
    soup = _soup(inventory_html)
    section = soup.select_one('#phoca-dl-category-box')
    if not section or not section.select_one('.pd-ctitle') or section.select_one('.pd-ctitle').get_text(strip=True) != 'PGOU':
        raise ValueError('PGOU document inventory missing')
    docs = {}
    for block in section.select('.pd-filebox'):
        title = block.select_one('.pd-title')
        links = block.select('.pd-filename a[href]')
        if not title or len(links) != 1:
            raise ValueError('Malformed PGOU document entry')
        url = urljoin(DIAGNOSTICO, links[0]['href'])
        if not url.startswith(DIAGNOSTICO + '?download=') or not re.search(r'\?download=\d+:', url):
            raise ValueError('Unexpected PGOU document URL')
        docs[url] = {'titulo': title.get_text(' ', strip=True), 'url': url, 'source_url': DIAGNOSTICO}
    # A navigation heading or generic announcement alone is not sufficient.
    if not any('diagn' in d['titulo'].lower() for d in docs.values()):
        raise ValueError('PGOU diagnosis document missing')
    row = _record('pgou', 'Plan General de Ordenación Urbana de Lazkao (PGOU)', PGOU,
                  list(docs.values()), [PGOU, DIAGNOSTICO])
    row['descripcion'] = ('Inventario municipal de diagnóstico del nuevo PGOU. Incluye documentación '
                          'de contexto territorial PTP/PTS; estos anexos no son proyectos independientes.')
    return row


def _record(key, title, url, documents, sources):
    return {
        'id': 'lazkao-proy-' + key, 'municipio': 'Lazkao', 'codigo_ine': '20049',
        'provincia': 'Gipuzkoa', 'titulo': title, 'tipo': 'planeamiento_urbanistico',
        'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
        'documentos': documents, 'source_urls': sources,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False, 'limitations': LIMITATIONS,
    }


class LazkaoAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, name):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-lazkao/1.0'})
        response.raise_for_status()
        if response.url != url or 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Unexpected source redirect or content type: ' + url)
        if len(response.content) > 4_000_000:
            raise ValueError('Source exceeds reviewed size; no partial parse')
        if self.config.get('evidence_dir'):
            dest = Path(self.config['evidence_dir']) / (name + '.html')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(response.content)
        response.encoding = 'utf-8'
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = [parse_normas(self._fetch(NORMAS, 'normas'), self._fetch(VIEWER, 'inventory')),
                parse_pgou(self._fetch(PGOU, 'pgou'), self._fetch(DIAGNOSTICO, 'diagnostico'))]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'live_records': len(rows),
                'source_urls': [NORMAS, VIEWER, PGOU, DIAGNOSTICO], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of the two current inventories; no date cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
