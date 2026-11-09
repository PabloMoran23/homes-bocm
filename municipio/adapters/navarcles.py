"""Navarcles: complete document tree for the municipal POUM advance, not a licence register."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.navarcles.cat'
SOURCE = BASE + '/ajuntament/poum'
INVENTORY = SOURCE + '/documentacio-avanc-poum'
PARTICIPATION = SOURCE + '/programa-de-participacio-ciutadana'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('#readspeakerPage')
    if body is None or body.select_one('h1') is None:
        raise ValueError('Missing municipal content; cannot extract a POUM snapshot')
    # These pages are a document tree, not a paginated search. Fail on any
    # pagination change instead of returning a silently incomplete snapshot.
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if ('next' in a.get('rel', []) or label in {'següent', 'seguent', 'siguiente', 'next', '»', '›'}
                or re.search(r'[?&](?:page|pagina|pag|start|offset)=', a['href'], re.I)):
            raise ValueError('Pagination detected; document crawler must be reviewed')
    return body


def document_page(html, page_url):
    body = content(html)
    documents = {}
    children = set()
    soup = BeautifulSoup(html, 'html.parser')
    # Attachments live in a sibling sidebar, outside the text article.
    for a in soup.select('#readspeakerPage a[href], #page-documents a[href]'):
        url = urljoin(page_url, a['href']).split('#')[0]
        parts = urlsplit(url)
        if parts.netloc != urlsplit(BASE).netloc:
            continue
        if parts.path.startswith('/media/repository/POUM/') and parts.path.lower().endswith('.pdf'):
            title = a.get_text(' ', strip=True)
            if not title:
                raise ValueError('Untitled POUM document')
            documents[url] = {'titulo': title, 'url': url, 'url_fuente': page_url}
        if url.startswith(INVENTORY + '/'):
            if parts.query:
                raise ValueError('Unexpected document-tree query')
            children.add(url.rstrip('/'))
    children.discard(page_url)
    return list(documents.values()), children


def parse_record(html, documents, pages):
    body = content(html)
    paragraphs = [p.get_text(' ', strip=True) for p in body.select('.ddbbtext p')]
    narrative = ' '.join(paragraphs)
    match = re.search(
        r"El (\d{1,2}) d[e’']\s*(\w+) de (\d{4}), el Ple de la Corporació va aprovar per unanimitat l['’]Avanç del POUM",
        narrative,
    )
    if body.select_one('h1').get_text(strip=True) != 'POUM' or not match or 'Navarcles' not in narrative:
        raise ValueError('Expected explicit Navarcles POUM advance approval narrative')
    approval = date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()
    if not documents:
        raise ValueError('No source documents for POUM advance')
    return {
        'id': 'navarcles-poum-avanc', 'municipio': 'Navarcles', 'codigo_ine': '08140',
        'titulo': "Avanç del Pla d'Ordenació Urbanística Municipal de Navarcles",
        'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación del avance',
        'fecha': None, 'fecha_acuerdo': approval, 'fecha_aprob': approval,
        'fecha_publicacion': None,
        'url': SOURCE, 'url_documento': INVENTORY,
        'source': 'ayuntamiento', 'origen': 'documentacio_avanc_poum',
        'descripcion': '\n'.join(paragraphs),
        'documentos': sorted(documents, key=lambda d: d['url']),
        'source_urls': sorted(pages),
        'date_provenance': {'fecha_acuerdo': SOURCE, 'fecha_aprob': SOURCE,
                            'fecha_publicacion': 'No verified publication date; page updates are not publication dates'},
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'coverage': 'POUM advance document tree only; not all municipal planning or public works',
    }


class NavarclesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        response = requests.get(url, timeout=35, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-navarcles/1.0')})
        with response:
            response.raise_for_status()
            if urlsplit(response.url).netloc != urlsplit(BASE).netloc:
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Source response exceeds reviewed size')
                chunks.append(chunk)
            html = b''.join(chunks).decode('utf-8')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            target = Path(capture_dir)
            target.mkdir(parents=True, exist_ok=True)
            (target / (urlsplit(url).path.rsplit('/', 1)[-1] + '.html')).write_text(html, encoding='utf-8')
        return html

    def backfill_proyectos(self, out_jsonl):
        root = self._fetch(SOURCE)
        body = content(root)
        links = {urljoin(SOURCE, a['href']).rstrip('/') for a in body.select('a[href]')}
        if not {INVENTORY, PARTICIPATION} <= links:
            raise ValueError('POUM document inventory or participation link missing')
        pending, visited, documents = {INVENTORY, PARTICIPATION}, {SOURCE}, {}
        while pending:
            if len(visited) >= 30:
                raise ValueError('Document tree exceeds reviewed page bound; no partial output written')
            url = min(pending)
            pending.remove(url)
            docs, children = document_page(self._fetch(url), url)
            if (url != INVENTORY and not docs) or (not docs and not children):
                raise ValueError('Empty document page: ' + url)
            visited.add(url)
            for doc in docs:
                # Retain every page that provides a document, even if linked twice.
                existing = documents.setdefault(doc['url'], {**doc, 'paginas_fuente': []})
                existing['paginas_fuente'].append(url)
            pending.update(children - visited)
        rows = [parse_record(root, list(documents.values()), visited)]
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temp = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'documents': len(documents),
                'source_urls': sorted(visited), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Refresh the entire small tree; no date cursor that could miss changed attachments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        raise NotImplementedError('Licences disabled: no verified granted-licence inventory')

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
