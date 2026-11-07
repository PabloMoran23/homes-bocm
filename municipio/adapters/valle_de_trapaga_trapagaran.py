"""Municipal urbanisation-project inventory and its paginated document trees."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.trapagaran.net'
PREFIX = '/es-ES/Servicios/Urbanismo/'
SOURCE = BASE + PREFIX + 'Paginas/Proyectosdeurbanizacion.aspx'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
LIMITATIONS = [
    'Solo inventario municipal Proyectos de urbanización y sus árboles documentales; no todo el planeamiento ni obras municipales.',
    'Documentos enlazados, sin interpretar el contenido de todos los PDF; fechas solo de narrativa explícita HTML.',
    'La publicación de un proyecto no acredita ejecución física ni concesión de licencia.',
    'Sin geometría de proyecto verificada; visor cartográfico no convertido a coordenadas.',
]


def canonical(url):
    parts = urlsplit(requests.utils.requote_uri(url))
    if parts.hostname != 'www.trapagaran.net' or not parts.path.startswith(PREFIX):
        raise ValueError('Unexpected link outside municipal urbanism: ' + url)
    return urlunsplit(('https', parts.netloc, parts.path, parts.query, ''))


def parse_page(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('#SectionBody')
    heading = body.select_one('.articleInfoBox h3') if body else None
    if heading is None:
        raise ValueError('Missing municipal article structure: ' + url)
    for element in body.select('.viewMore, script, style'):
        element.decompose()
    pages, docs = {}, {}
    for a in body.select('a[href]'):
        href = a['href'].strip()
        if href.startswith('#'):
            continue
        if href.lower().startswith('javascript:'):
            raise ValueError('Unsupported postback/pagination: ' + url)
        target = canonical(urljoin(url, href))
        label = a.get_text(' ', strip=True)
        bucket = pages if urlsplit(target).path.lower().endswith('.aspx') else docs
        if not label and target in bucket:
            continue
        bucket[target] = label or target.rsplit('/', 1)[-1]
    narrative = body.select_one('.contentArticle .ms-rtestate-field')
    return {
        'titulo': heading.get_text(' ', strip=True),
        'texto': narrative.get_text(' ', strip=True).replace('\u200b', '') if narrative else '',
        'paginas': pages, 'documentos': docs,
    }


def publication_date(text):
    # A bulletin's publication date is never the agreement/approval date.
    if not ('Boletín Oficial' in text and 'se ha publicado' in text):
        return None
    match = re.search(r'(\d{1,2}) de (' + '|'.join(MONTHS) + r') de (\d{4})', text, re.I)
    if not match:
        return None
    return date(int(match[3]), MONTHS.index(match[2].lower()) + 1, int(match[1])).isoformat()


class ValleDeTrapagaTrapagaranAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []

    def _fetch(self, url):
        time.sleep(0.15)
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-trapagaran/1.0 (public urbanism inventory)'
        })
        response.raise_for_status()
        if canonical(response.url) != canonical(url):
            raise ValueError('Unexpected source redirect: ' + response.url)
        if len(response.content) > 5_000_000:
            raise ValueError('Oversized HTML; extraction aborted without partial output')
        response.encoding = 'utf-8'
        self.source_urls.append(url)
        capture = self.config.get('capture_dir')
        if capture:
            folder = Path(capture)
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
            (folder / name).write_bytes(response.content)
        return response.text

    def _crawl(self, start):
        pending, visited, parsed = [start], set(), []
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 250:
                raise ValueError('Document tree exceeds safety bound; no truncated output written')
            visited.add(url)
            page = parse_page(self._fetch(url), url)
            parsed.append((url, page))
            pending.extend(u for u in page['paginas'] if u not in visited)
        return parsed

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        # Inventory pages only: project-detail links become roots, not pagination.
        pending, seen, roots = [SOURCE], set(), {}
        while pending:
            url = pending.pop(0)
            if url in seen:
                continue
            if len(seen) >= 100:
                raise ValueError('Inventory pagination exceeds safety bound')
            seen.add(url)
            page = parse_page(self._fetch(url), url)
            if page['titulo'].casefold() != 'proyectos de urbanización':
                raise ValueError('Unexpected inventory heading')
            for link, title in page['paginas'].items():
                if urlsplit(link).path == urlsplit(SOURCE).path:
                    pending.append(link)
                elif re.search(r'proyecto de urbanizaci[oó]n', title, re.I):
                    roots[link] = title
                else:
                    raise ValueError('Unrecognised inventory entry: ' + title)
        if not roots:
            raise ValueError('No genuine project detail pages in inventory')
        rows = []
        for root in sorted(roots):
            tree = self._crawl(root)
            docs, narratives = {}, []
            for url, page in tree:
                if page['texto']:
                    narratives.append({'url': url, 'texto': page['texto']})
                for link, title in page['documentos'].items():
                    doc = docs.setdefault(link, {'titulo': title, 'url': link, 'procedencia': []})
                    doc['procedencia'].append({'url': url, 'seccion': page['titulo']})
            if not docs:
                raise ValueError('Project without linked documentation: ' + root)
            main = tree[0][1]
            published = publication_date(main['texto'])
            rows.append({
                'id': self.slug + '-proy-' + hashlib.sha256(root.encode()).hexdigest()[:16],
                'municipio': 'Valle de Trápaga-Trapagaran', 'codigo_ine': '48080', 'provincia': 'Bizkaia',
                'titulo': main['titulo'], 'tipo': 'proyecto_urbanizacion',
                'fase': 'aprobación inicial' if 'aprobación inicial' in main['texto'].lower() else None,
                'fecha_publicacion': published, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'fecha_publicacion_fuente': root if published else None,
                'url': root, 'source': 'ayuntamiento', 'origen': 'inventario_proyectos_urbanizacion',
                'url_inventario': SOURCE, 'documentos': list(docs.values()),
                'paginas_fuente': [url for url, _ in tree], 'textos_fuente': narratives,
                'descripcion': main['texto'] or None,
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'limitaciones': LIMITATIONS,
            })
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': self.source_urls, 'limitations': LIMITATIONS}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot; failed page/document discovery never replaces prior output.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
