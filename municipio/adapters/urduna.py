"""Orduña's municipal planning library; documents are grouped by instrument."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.urduna.com/es-ES/Servicios/Urbanismo/Paginas/default.aspx'
REVISION_DOCUMENTS = {
    '20241217-certificado-resultado-exposicion-publica.pdf',
    '20241217-documento-alcance-estudio-ambiental-estrategico.pdf',
    '20250915-10_aprobarcion-criterios.pdf',
}


def _url(href):
    url = urljoin(SOURCE, href)
    if urlsplit(url).hostname != 'www.urduna.com':
        raise ValueError('Unexpected external planning document or pagination')
    return quote(url, safe=':/?=&%')


def parse_page(html):
    """Parse one page, including its declared result range and pagination links."""
    soup = BeautifulSoup(html, 'html.parser')
    sections = {}
    for heading in soup.select('h3.ms-WPTitle'):
        body = heading.parent.find_next_sibling('div', class_='ms-WPBody')
        if body:
            sections[heading.get_text(' ', strip=True)] = body
    pgou = sections.get('PGOU 2004')
    if pgou is None:
        raise ValueError('Missing municipal PGOU inventory')
    ranges = set(re.findall(r'Resultados\s+(\d+)\s*-\s*(\d+)\s+de\s+(\d+)', pgou.get_text(' ', strip=True)))
    if len(ranges) != 1:
        raise ValueError('Missing or ambiguous inventory count')
    start, end, total = map(int, ranges.pop())
    if not 1 <= start <= end <= total:
        raise ValueError('Invalid inventory range')
    documents = []
    for section in ('PGOU 2004', 'Plan Especial de Rehabilitación del Casco Histórico',
                    'Modificaciones de planeamiento pormenorizadas'):
        body = sections.get(section)
        if body is None:
            continue
        for a in body.select('a[href]'):
            if not urlsplit(a['href']).path.lower().endswith('.pdf'):
                continue
            documents.append({'titulo': a.get_text(' ', strip=True),
                              'url': _url(a['href']), 'seccion_fuente': section})
    pgou_docs = [d for d in documents if d['seccion_fuente'] == 'PGOU 2004']
    if len(pgou_docs) != end - start + 1 or len({d['url'] for d in pgou_docs}) != len(pgou_docs):
        raise ValueError('Inventory range does not match documents')
    pages = set()
    for a in soup.select('.pagination a[href]'):
        url = _url(a['href'])
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        if parts.path != urlsplit(SOURCE).path or set(query) != {'page'} or not query['page'][0].isdigit():
            raise ValueError('Unrecognized pagination')
        pages.add(int(query['page'][0]))
    return documents, (start, end, total), pages


def group_documents(documents):
    groups = {}
    for doc in documents:
        section = doc['seccion_fuente']
        filename = unquote(urlsplit(doc['url']).path.rsplit('/', 1)[-1])
        if section == 'PGOU 2004':
            if re.fullmatch(r'fase-[123]-.+\.pdf', filename) or filename in REVISION_DOCUMENTS:
                key, title = 'pgou-revision', 'Revisión del Plan General de Ordenación Urbana de Urduña / Orduña'
            elif re.fullmatch(r'(?:00[1-4]_[A-Z_]+|\d+(?:-\d+){1,2})\.pdf', filename):
                key, title = 'pgou-2004', 'PGOU 2004 de Urduña / Orduña'
            else:
                raise ValueError('Unclassified PGOU document: ' + filename)
        elif section == 'Plan Especial de Rehabilitación del Casco Histórico':
            key, title = 'per-casco-historico', section
        else:
            title = re.sub(r'\s*\(PDF\b.*$', '', doc['titulo'], flags=re.I).strip()
            if not re.match(r'^\d+ª Modificación Puntual del Plan ', title):
                raise ValueError('Unclassified planning modification')
            key = 'modificacion-' + hashlib.sha256(title.encode()).hexdigest()[:16]
        if key not in groups:
            groups[key] = {
                'id': 'urduna-proy-' + key, 'municipio': 'Urduña / Orduña',
                'codigo_ine': '48074', 'provincia': 'Bizkaia', 'titulo': title,
                'tipo': 'planeamiento_urbanistico', 'url': SOURCE,
                'source': 'ayuntamiento', 'origen': 'biblioteca_municipal_urbanismo',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None,
                'fecha_provenance': 'El índice no indica fechas; los nombres de archivo no se interpretan como fechas de acuerdos o publicación.',
                'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            }
        if not any(d['url'] == doc['url'] for d in groups[key]['documentos']):
            groups[key]['documentos'].append(doc)
    if not groups:
        raise ValueError('No verified municipal planning instruments')
    return list(groups.values())


class UrdunaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='urduna', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.urduna.com')

    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-urduna/1.0'})
        response.raise_for_status()
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            page = parse_qs(urlsplit(url).query).get('page', ['1'])[0]
            (directory / ('inventory-' + page + '.html')).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pending, visited, documents, positions = {1}, set(), {}, set()
        total = None
        source_urls = []
        while pending:
            page = min(pending)
            pending.remove(page)
            if page in visited:
                continue
            if page < 1 or page > 1000:
                raise ValueError('Pagination exceeds safety bound; no partial output written')
            url = SOURCE if page == 1 else SOURCE + '?page=' + str(page)
            docs, (start, end, count), links = parse_page(self._fetch(url))
            source_urls.append(url)
            if total is not None and count != total:
                raise ValueError('Inventory count changed during extraction')
            total = count
            current_positions = set(range(start, end + 1))
            if positions & current_positions:
                raise ValueError('Repeated pagination range')
            positions |= current_positions
            for doc in docs:
                documents.setdefault(doc['url'], doc)
            visited.add(page)
            pending |= links - visited
        pgou_count = sum(d['seccion_fuente'] == 'PGOU 2004' for d in documents.values())
        if positions != set(range(1, total + 1)) or pgou_count != total:
            raise ValueError('Incomplete pagination or duplicate documents; no partial output written')
        rows = group_documents(documents.values())
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': source_urls,
                'documents': len(documents), 'pages': len(visited)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
