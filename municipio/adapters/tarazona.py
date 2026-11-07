"""Tarazona's municipal PGOU document tree, grouped as one instrument."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.tarazona.es/tarazona-tematico/urbanismo-y-obras-publicas/plan-general-ordenacion-urbana'
LIMITATIONS = [
    'Cobertura parcial: únicamente el árbol documental municipal del PGOU; no es un registro de todas las actuaciones ni de licencias concedidas.',
    'Los documentos de distintas versiones se conservan como publicados; no se acredita vigencia, aprobación ni ejecución.',
    'La actualización del CMS y el directorio Pgou_2022 no son fechas de publicación o acuerdo.',
    'Sin geometría verificada; se retienen enlaces a planos sin convertirlos en coordenadas.',
    'Se recopilan enlaces documentales; no se descarga ni valida íntegramente cada documento.',
]


def _in_tree(url):
    parsed, root = urlparse(url), urlparse(SOURCE)
    return (parsed.scheme == 'https' and parsed.netloc == root.netloc
            and (parsed.path == root.path or parsed.path.startswith(root.path + '/')))


def parse_page(html: str, url: str):
    """Read document links only from node body; follow tree navigation and pagers."""
    if not _in_tree(url):
        raise ValueError('Page outside official PGOU tree')
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#block-system-main')
    body = main.select_one('.field-name-body') if main else None
    heading = main.select_one('h1') if main else None
    if body is None or heading is None:
        raise ValueError('Missing PGOU node body/title')
    title = heading.get_text(' ', strip=True)
    docs = []
    for a in body.select('a[href]'):
        target = urldefrag(urljoin(url, a['href']))[0]
        p = urlparse(target)
        if (p.scheme == 'https' and p.netloc == urlparse(SOURCE).netloc
                and p.path.startswith('/sites/default/files/')
                and p.path.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png', '.zip'))):
            docs.append({'titulo': a.get_text(' ', strip=True), 'url': target,
                         'seccion': title, 'source_page': url})
    pages = set()
    for a in main.select('a[href]'):
        target = urldefrag(urljoin(url, a['href']))[0]
        if _in_tree(target) and target != url:
            pages.add(target)
    for a in soup.select('.pager a[href], a[rel~=next]'):
        target = urldefrag(urljoin(url, a['href']))[0]
        if not _in_tree(target):
            raise ValueError('Pagination outside PGOU tree; refusing incomplete snapshot')
        if target != url:
            pages.add(target)
    return title, docs, sorted(pages)


def collect_projects(fetch):
    pending, visited, documents = [SOURCE], [], {}
    while pending:
        url = pending.pop(0)
        if url in visited:
            continue
        title, docs, links = parse_page(fetch(url), url)
        if url == SOURCE and 'Plan General' not in title:
            raise ValueError('PGOU inventory identity changed')
        visited.append(url)
        for doc in docs:
            item = documents.setdefault(doc['url'], {**doc, 'source_pages': [], 'apariciones': []})
            reference = {k: doc[k] for k in ('titulo', 'seccion', 'source_page')}
            if reference not in item['apariciones']:
                item['apariciones'].append(reference)
            if url not in item['source_pages']:
                item['source_pages'].append(url)
        pending.extend(link for link in links if link not in visited and link not in pending)
    if not documents or not any('texto_refundido' in urlparse(u).path for u in documents):
        raise ValueError('No verified PGOU texto refundido document in inventory')
    return [{
        'id': 'tarazona-pgou-' + hashlib.sha256(SOURCE.encode()).hexdigest()[:16],
        'municipio': 'Tarazona', 'codigo_ine': '50251', 'provincia': 'Zaragoza',
        'titulo': 'Plan General de Ordenación Urbana de Tarazona',
        'tipo': 'PGOU', 'url': SOURCE, 'source': 'ayuntamiento',
        'origen': 'inventario_documental_planeamiento',
        'documentos': sorted(documents.values(), key=lambda d: d['url']),
        'source_urls': visited, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
        'limitations': LIMITATIONS,
    }]


class TarazonaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='tarazona', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-tarazona/1.0 (public planning inventory)'

            def fetch(url):
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if not _in_tree(response.url) or urlparse(response.url).path != urlparse(url).path:
                    raise ValueError('Unexpected PGOU redirect')
                if 'text/html' not in response.headers.get('Content-Type', '').lower():
                    raise ValueError('Expected HTML inventory')
                if self.config.get('evidence_dir'):
                    folder = Path(self.config['evidence_dir'])
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
                return response.content

            rows = collect_projects(fetch)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'documents': len(rows[0]['documentos']),
                'source_urls': rows[0]['source_urls'], 'limitations': LIMITATIONS,
                'coverage': 'municipal_pgou_document_tree', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
