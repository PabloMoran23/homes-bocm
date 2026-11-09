"""Municipal PXOM archive: one instrument, all recursively listed documents."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.castroderei.gal/es/pxom/'
MANAGER = 'https://www.castroderei.gal/archivos/file_manager.php'
PLAN = 'CASTRO_DE_REI_PXOM_APROBADO DEFINITIVO'
HOSTS = {'www.castroderei.gal', 'castroderei.gal'}


def canonical(url):
    parsed = urlparse(url)
    if parsed.hostname not in HOSTS or parsed.username or parsed.password:
        raise ValueError('Archive link outside municipal source')
    return 'https://www.castroderei.gal' + quote(unquote(parsed.path), safe='/+') + (
        '?' + quote(unquote(parsed.query), safe='=/*+') if parsed.query else '')


def parse_plan(html):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article .entry-content')
    if not article:
        raise ValueError('Missing municipal plan content')
    text = article.get_text(' ', strip=True)
    if ('PLAN GENERAL DE ORDENACIÓN MUNICIPAL DE CASTRO DE REI' not in text
            or 'Documento aprobado definitivo' not in text):
        raise ValueError('Plan identity or approval statement changed')
    frames = [canonical(urljoin(SOURCE, f['src'])) for f in article.select('iframe[src]')]
    if frames != [MANAGER]:
        raise ValueError('Plan document inventory changed')
    return frames[0]


def parse_directory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    section = soup.select_one('section')
    footer = section.select_one('footer') if section else None
    counts = re.fullmatch(r'\s*(\d+) carpeta/s y (\d+) archivo/s\s*', footer.get_text() if footer else '')
    if not counts:
        raise ValueError('Missing archive counts; cannot establish complete coverage')
    folders, documents = [], []
    for a in section.select('a[href]'):
        parent = a.find_parent('div', class_='group')
        if parent and 'bold' in parent.get('class', []) and a.get_text(strip=True) == '...':
            continue  # Explicit parent-directory link only.
        target = canonical(urljoin(url, a['href']))
        if parent and 'directory' in parent.get('class', []):
            path = parse_qs(urlparse(target).query).get('path', [''])[0]
            if urlparse(target).path != '/archivos/file_manager.php' or not path.endswith('/*'):
                raise ValueError('Unrecognized folder link')
            folders.append(target)
        elif parent and a.get_text(strip=True) and urlparse(target).path.startswith('/archivos/') and not urlparse(target).query:
            documents.append({'titulo': a.get_text(' ', strip=True), 'url': target,
                              'url_fuente': urljoin(url, a['href']), 'inventario_url': url})
        else:
            raise ValueError('Unrecognized link/pagination in archive; refusing partial result')
    if (len(folders), len(documents)) != tuple(map(int, counts.groups())):
        raise ValueError('Archive counts disagree with extracted links')
    return folders, documents


class CastroDeReiAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        time.sleep(0.15)
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-castro-de-rei/1.0'})
        response.raise_for_status()
        if canonical(response.url) != canonical(url):
            raise ValueError('Unexpected archive redirect')
        if len(response.content) > 5_000_000:
            raise ValueError('Oversize inventory; review before extracting')
        html = response.content.decode('utf-8')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            import hashlib
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (path / name).write_text(html, encoding='utf-8')
        return html

    def extract(self, fetch):
        manager = parse_plan(fetch(SOURCE))
        roots, docs = parse_directory(fetch(manager), manager)
        if docs or len(roots) != 1 or parse_qs(urlparse(roots[0]).query).get('path') != [PLAN + '/*']:
            raise ValueError('Municipal archive instrument inventory changed; review grouping')
        queue, seen, documents = roots[:], set(), {}
        while queue:
            url = queue.pop(0)
            if url in seen:
                raise ValueError('Repeated directory/cycle in archive')
            seen.add(url)
            if len(seen) > 500:
                raise ValueError('Archive crawl limit exceeded; no partial output')
            path = parse_qs(urlparse(url).query).get('path', [''])[0]
            if not path.startswith(PLAN + '/') or '..' in path.split('/'):
                raise ValueError('Folder outside selected instrument')
            folders, files = parse_directory(fetch(url), url)
            queue.extend(folders)
            for doc in files:
                if not unquote(urlparse(doc['url']).path).startswith('/archivos/' + PLAN + '/'):
                    raise ValueError('Document outside instrument')
                documents.setdefault(doc['url'], doc)
        if not documents:
            raise ValueError('No genuine plan documents')
        return [{
            'id': 'castro-de-rei-pxom-aprobado-definitivo',
            'municipio': 'Castro de Rei', 'provincia': 'Lugo', 'codigo_ine': '27010',
            'titulo': 'Plan General de Ordenación Municipal de Castro de Rei (PXOM)',
            'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación definitiva',
            'descripcion': 'Documento aprobado definitivo, según la página municipal del PXOM.',
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'inventario_url': manager,
            'source': 'ayuntamiento', 'origen': 'archivo_municipal_pxom',
            'documentos': sorted(documents.values(), key=lambda doc: doc['url']),
            'cobertura': 'Únicamente el PXOM del archivo municipal; no es un registro exhaustivo de obras o planeamiento.',
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }]

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = self.extract(self._fetch)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'documents': len(rows[0]['documentos']),
                'source_urls': [SOURCE, MANAGER], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
