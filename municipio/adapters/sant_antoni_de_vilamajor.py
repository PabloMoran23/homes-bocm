"""Current municipal works inventories; no licence or procurement inference."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.santantonidevilamajor.cat'
INDEX = BASE + '/ajuntament/projectes-municipals'
INVENTORIES = {
    'projectes-en-tramit-dinformacio-publica': "Projectes en tràmit d'informació pública",
    'projectes-municipals-aprovats': 'Projectes municipals aprovats',
    'projectes-municipals-no-aprovats': 'Projectes municipals no aprovats',
}
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
DATE = r"(\d{1,2})\s+(?:de\s+|d['’])([a-zç]+)\s+de\s+(\d{4})"


def norm(text):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFKD', text.lower()).encode('ascii', 'ignore').decode()).split())


def source_date(text):
    match = re.search(DATE, text.lower())
    if not match:
        return None
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


def check_page(html, heading):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    h1 = main.select_one('h1') if main else None
    if not h1 or h1.get_text(' ', strip=True) != heading:
        raise ValueError('Missing expected municipal inventory heading: ' + heading)
    if main.select('.pagination, .paginacio, [rel~=next], [rel~=prev]'):
        raise ValueError('Pagination detected; refusing a partial snapshot')
    for a in main.select('a[href]'):
        if norm(a.get_text(' ', strip=True)) in {'seguent', 'seguents', 'siguiente', 'next', 'mes', 'mes resultats'} and a['href'] not in {'', '#'}:
            raise ValueError('Continuation detected; review inventory traversal')
    return main


def document(a, source):
    url = urljoin(source, a['href'])
    if urlparse(url).hostname != urlparse(BASE).hostname or not urlparse(url).path.lower().endswith('.pdf'):
        raise ValueError('Unexpected project document URL: ' + url)
    title = re.sub(r'\s*\([\d.,]+\s*[KMG]B\)\s*$', '', a.get_text(' ', strip=True)).strip()
    if not title.startswith('Projecte '):
        raise ValueError('Unsupported document title: ' + title)
    return {'titulo': title, 'url': url, 'source_url': source}


class SantAntoniDeVilamajorAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html, category):
        source = INDEX + '/' + category
        main = check_page(html, INVENTORIES[category])
        blocks = main.select('.dinamic .ddbbtext')
        if not blocks:
            raise ValueError('Inventory structure changed or empty; review source')
        sections = []
        for block in blocks:
            heading = block.select_one('h3')
            if heading:
                title = heading.get_text(' ', strip=True)
                if not title.startswith('Projecte '):
                    raise ValueError('Unsupported inventory entry: ' + title)
                sections.append((title, ' '.join(p.get_text(' ', strip=True) for p in block.select('p'))))
        anchors = main.select('#page-documents a[href]')
        if category == 'projectes-municipals-no-aprovats':
            anchors = main.select('.dinamic .ddbbtext a[href]')
        docs = {}
        for a in anchors:
            doc = document(a, source)
            docs.setdefault(doc['url'], doc)
        if not docs:
            raise ValueError('Inventory has no project documents')
        groups = [[] for _ in sections]
        if not sections and category == 'projectes-municipals-no-aprovats':
            sections = [(d['titulo'], '') for d in docs.values()]
            groups = [[] for _ in sections]
        for doc in docs.values():
            # Match by title, never by list position. Minor title suffix differences
            # on the municipal page are accepted only with a unique long prefix.
            candidates = [i for i, (title, _) in enumerate(sections)
                          if norm(doc['titulo']).startswith(norm(title)) or norm(title).startswith(norm(doc['titulo']))
                          or norm(doc['titulo']).split()[:13] == norm(title).split()[:13]]
            if len(candidates) != 1:
                raise ValueError('Ambiguous/unmatched project document: ' + doc['titulo'])
            groups[candidates[0]].append(doc)
        rows = []
        for (title, description), documents in zip(sections, groups):
            if not documents:
                raise ValueError('Project lacks source document: ' + title)
            lower = description.lower()
            initial = bool(re.search(r'aprov(?:ar|at)\s+inicialment', lower))
            definitive = bool(re.search(r'aprov(?:ar|at)\s+definitivament', lower))
            agreement_match = re.search(r'(?:en data|de data|del dia)\s+' + DATE, lower)
            agreement = source_date(agreement_match[0]) if agreement_match else None
            automatic = definitive and ('sense necessitat' in lower or 'es considera aprovat' in lower)
            phase = 'no aprobado' if category.endswith('no-aprovats') else (
                'aprobación definitiva' if definitive else 'aprobación inicial' if initial else None)
            if phase is None:
                raise ValueError('Project approval narrative changed: ' + title)
            publication_match = re.search(r'\(bopb\)\s+del\s+' + DATE, lower)
            initial_date = agreement if initial else None
            definitive_date = agreement if definitive and not automatic and not initial else None
            rows.append({
                'id': 'sant-antoni-de-vilamajor-proy-' + hashlib.sha256(norm(title).encode()).hexdigest()[:16],
                'municipio': 'Sant Antoni de Vilamajor', 'provincia': 'Barcelona', 'codigo_ine': '08198',
                'titulo': documents[0]['titulo'], 'tipo': 'proyecto_obra_publica', 'fase': phase,
                'fecha': None, 'fecha_acuerdo': agreement,
                'fecha_publicacion': source_date(publication_match[0]) if publication_match else None,
                'fecha_aprob': definitive_date if definitive else initial_date,
                'fecha_aprob_inicial': initial_date, 'fecha_aprob_definitiva': definitive_date,
                'aprobacion_definitiva_automatica': automatic,
                'descripcion': description or None, 'url': source, 'url_documento': documents[0]['url'],
                'documentos': documents, 'inventario': INVENTORIES[category],
                'source': 'ayuntamiento', 'origen': 'projectes_municipals',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'geometry_status': 'No project geometry extracted; documents retained as links',
            })
        return rows

    def _fetch(self, url):
        with requests.get(url, timeout=(10, 45), stream=True,
                          headers={'User-Agent': 'municipio-sant-antoni-de-vilamajor/1.0'}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 2_000_000:
                    raise ValueError('Inventory response exceeds 2 MB; refusing truncation')
                chunks.append(chunk)
            content = b''.join(chunks)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / (url.rsplit('/', 1)[-1] + '.html')).write_bytes(content)
        return content.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        main = check_page(self._fetch(INDEX), 'Projectes municipals')
        categories = {urljoin(INDEX, a['href']).rstrip('/') for a in main.select('a[href]')
                      if urljoin(INDEX, a['href']).startswith(INDEX + '/')}
        expected = {INDEX + '/' + category for category in INVENTORIES}
        if categories != expected:
            raise ValueError('Municipal inventory categories changed; review coverage')
        rows = []
        for category in INVENTORIES:
            rows.extend(self.parse_inventory(self._fetch(INDEX + '/' + category), category))
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Project appears in multiple inventories; reconcile before writing')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [INDEX, *sorted(expected)], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
