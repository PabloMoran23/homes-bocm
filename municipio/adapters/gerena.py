"""Gerena's official ITA 53 planning document inventory (full gallery pagination)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://transparencia.gerena.es/es/transparencia/indicadores-de-transparencia/'
          'indicador/53.-Se-publican-y-se-mantienen-publicados-las-modificaciones-aprobadas-'
          'del-PGOU-y-los-Planes-parciales-aprobados.-00033/')
PREFIX = '/es/transparencia/.galleries/IND-53-/'
LIMITATIONS = [
    'Partial municipal coverage: only the current ITA 53 planning inventory; not all works or planning proceedings.',
    'Documents are grouped by municipal gallery; the distinct 2020 Colegio study is separated from ED Equipamiento SUO1.',
    'Document CMS timestamps are retained as fecha_publicacion_portal, not agreement or approval dates.',
    'No licence grants, inferred legal validity, approval dates, coordinates or geometry.',
    'Document links are inventoried; document contents and availability are not exhaustively verified.',
    'PGOM/POU pages and urbanismo notices were researched but are outside this adapter scope.',
]


def checked_url(href, base=SOURCE):
    url = urldefrag(urljoin(base, href))[0]
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != urlparse(SOURCE).netloc:
        raise ValueError('Unexpected non-official URL: ' + url)
    return url


def parse_sections(html, page_url=SOURCE):
    """Return source gallery title, documents, and explicit pagination URLs."""
    soup = BeautifulSoup(html, 'html.parser')
    sections = {}
    for section in soup.select('section.gallery'):
        heading = section.select_one('h4.gallery-title')
        if heading is None:
            continue
        title = heading.get_text(' ', strip=True)
        if title in sections:
            raise ValueError('Duplicate gallery heading')
        docs = {}
        for a in section.select('a[href]'):
            path = urlparse(urljoin(page_url, a['href'])).path
            if PREFIX not in path:
                continue
            url = checked_url(a['href'], page_url)
            doc = {'titulo': a.get_text(' ', strip=True), 'url': url,
                   'source_url': page_url}
            media = a.find_parent('div', class_='media')
            if media:
                desc = media.select_one('.description')
                stamp = media.select_one('time[datetime]')
                if desc:
                    doc['descripcion'] = desc.get_text(' ', strip=True)
                if stamp:
                    doc['fecha_publicacion_portal'] = stamp['datetime']
            docs[url] = doc
        if not docs:
            raise ValueError('Gallery has no source documents: ' + title)
        pages = set()
        for a in section.select('a.pagelink[href], a.currentpagelink[href]'):
            url = checked_url(a['href'], page_url)
            if urlparse(url).path.rstrip('/') != urlparse(SOURCE).path.rstrip('/'):
                raise ValueError('Unexpected pagination path')
            query = parse_qs(urlparse(url).query)
            if query:
                if len(query) != 1 or not next(iter(query)).startswith('pagegalleryfiles-'):
                    raise ValueError('Unsupported pagination query')
                pages.add(url)
        # OpenCMS marks the active page explicitly. A server ignoring page queries
        # must fail, rather than returning page 1 as complete coverage.
        requested = parse_qs(urlparse(page_url).query)
        group = section.select_one('.download-group[id]')
        if group and 'page' + group['id'] in requested:
            current = section.select_one('a.currentpagelink[numpag]')
            if current is None or current['numpag'] != requested['page' + group['id']][0]:
                raise ValueError('Pagination response did not select the requested page')
        sections[title] = {'documents': list(docs.values()), 'pages': sorted(pages)}
    if not sections:
        raise ValueError('Official planning galleries missing or empty')
    return sections


def extract_inventory(fetch):
    """Fetch every page of each gallery, never merge other galleries' repeated page 1."""
    sections = parse_sections(fetch(SOURCE))
    source_urls = [SOURCE]
    rows = []
    for title, section in sections.items():
        docs = {d['url']: d for d in section['documents']}
        pending = list(section['pages'])
        visited = {SOURCE}
        signatures = {tuple(sorted(docs))}
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            visited.add(url)
            # Page 1 is already represented by the base response.
            if list(parse_qs(urlparse(url).query).values()) == [['1']]:
                continue
            if len(visited) > 500:
                raise ValueError('Pagination safety limit reached; refusing partial output')
            parsed = parse_sections(fetch(url), url)
            source_urls.append(url)
            if title not in parsed:
                raise ValueError('Gallery disappeared during pagination')
            part = parsed[title]
            signature = tuple(sorted(d['url'] for d in part['documents']))
            if signature in signatures:
                raise ValueError('Repeated gallery page; refusing partial output')
            signatures.add(signature)
            docs.update((d['url'], d) for d in part['documents'])
            pending.extend(p for p in part['pages'] if p not in visited)
        # This source gallery contains the earlier study AND the separate 2020
        # school study. Keep their documents separate using the source subfolder.
        groups = {}
        for doc in docs.values():
            school = '/ESTUDIO-DE-DETALLE.-2020.-COLEGIO/' in doc['url']
            group_title = title + ' — ESTUDIO DE DETALLE. 2020. COLEGIO' if school else title
            groups.setdefault(group_title, []).append(doc)
        for group_title, documents in groups.items():
            display_title = group_title
            if len(documents) == 1 and documents[0].get('descripcion', '').startswith('Aprobación definitiva del Estudio de Detalle'):
                display_title = documents[0]['descripcion']
            key = hashlib.sha256(group_title.encode()).hexdigest()[:20]
            rows.append({'id': 'gerena-plan-' + key, 'municipio': 'Gerena',
                         'codigo_ine': '41045', 'provincia': 'Sevilla',
                         'titulo': display_title, 'titulo_grupo_fuente': title,
                         'tipo': 'planeamiento_urbanistico', 'url': documents[0]['url'],
                         'inventory_url': SOURCE, 'source': 'ayuntamiento',
                         'origen': 'inventario_municipal_planeamiento_ita53',
                         'documentos': documents, 'publication_ready': False,
                         'geometry_status': 'unavailable'})
    return rows, source_urls


class GerenaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        capture = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-gerena-inventory/1.0'

            def fetch(url):
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if checked_url(response.url) != url:
                    raise ValueError('Unexpected inventory redirect')
                if capture:
                    folder = Path(capture)
                    folder.mkdir(parents=True, exist_ok=True)
                    name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
                    (folder / name).write_text(response.text, encoding='utf-8')
                return response.text

            rows, urls = extract_inventory(fetch)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': urls,
                'documents': sum(len(row['documentos']) for row in rows),
                'coverage': 'current_ita53_inventory_all_gallery_pages',
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Snapshot refresh: this inventory has no reliable incremental cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public licence-grant inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
