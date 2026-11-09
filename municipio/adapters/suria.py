"""Two municipal planning document inventories, grouped by instrument."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.suria.cat'
POUM = BASE + '/poum'
DOCUMENTS = BASE + '/poum/documents2/'
NORMES = BASE + '/urbanisme/normativa-urbanistica/normes-subsidiaries-de-planejament/'
SOURCES = (POUM, DOCUMENTS, NORMES)
LIMITATIONS = [
    'Partial coverage: only municipal POUM and 2003 Normes Subsidiàries document pages.',
    'Later Normes amendments, RPUC, electronic noticeboard and transparency inventories are not crawled.',
    'POUM materials do not establish current legal status or definitive approval.',
    'CMS modification dates and dates in filenames are not agreement/publication dates.',
    'No granted licence inventory or verified geometry; publication_ready=false.',
]
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def _article(html):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('#pepe article')
    if article is None:
        raise ValueError('Súria municipal article missing')
    # These reviewed document inventories are single pages. Fail closed if a
    # continuation appears rather than returning a silently incomplete snapshot.
    if soup.select_one('a[rel~=next], .pagination, .paginacio, .paginador'):
        raise ValueError('Pagination requires review')
    for a in article.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'següent', 'siguiente', 'next', 'més', '»', '>'}:
            raise ValueError('Inventory continuation requires review')
    return article


def _documents(article, source):
    docs = {}
    for li in article.select('li'):
        for a in li.select('a[href]'):
            url = urljoin(source, a['href'])
            parts = urlsplit(url)
            if parts.hostname not in {'www.suria.cat', 'suria.cat'}:
                continue
            if not parts.path.lower().endswith(('.pdf', '.jpg', '.png')):
                continue
            # Preserve literal source href as provenance; normalize municipal
            # legacy HTTP/double-slash URLs for reliable direct access.
            path = re.sub('/+', '/', parts.path)
            url = urlunsplit(('https', 'www.suria.cat', path, parts.query, ''))
            docs.setdefault(url, {
                'titulo': li.get_text(' ', strip=True).removesuffix('.').removesuffix('Enllaç').rstrip(': '),
                'url': url, 'source_url': source, 'source_href': a['href'],
            })
    if not docs:
        raise ValueError('No municipal planning documents found')
    return list(docs.values())


def _record(key, title, source, description, docs):
    return {
        'id': 'suria-proy-' + key, 'municipio': 'Súria', 'codigo_ine': '08274',
        'provincia': 'Barcelona', 'titulo': title, 'tipo': 'planeamiento_urbanistico',
        'url': source, 'source': 'ayuntamiento', 'origen': 'planejament_municipal',
        'descripcion': description, 'documentos': docs,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'fase': None,
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class SuriaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_projects(overview_html, documents_html, normes_html):
        overview = _article(overview_html)
        text = overview.get_text(' ', strip=True)
        if not re.search(r"procés d[’']elaboració del Pla d[’']Ordenació Urbanística Municipal de Súria", text):
            raise ValueError('POUM elaboration narrative changed; review status')
        inventory = _article(documents_html)
        if not inventory.find(string=re.compile('DOCUMENTS')) or 'POUM' not in inventory.get_text():
            raise ValueError('POUM document inventory changed')
        poum = _record('poum', "Pla d'Ordenació Urbanística Municipal de Súria (POUM)", POUM,
                       text, _documents(inventory, DOCUMENTS))
        poum['source_urls'] = [POUM, DOCUMENTS]
        poum['coverage_notes'] = 'Grouped advance, proposal and participation materials; no definitive approval asserted.'

        normes = _article(normes_html)
        description = '\n'.join(' '.join(p.get_text(' ', strip=True).split()) for p in normes.select('p') if p.get_text(strip=True))
        if 'Normes Subsidiàries de Planejament' not in description:
            raise ValueError('Normes instrument narrative missing')
        approval = re.search(r'aprovada definitivament.*?en sessió de (\d{1,2}) de (\w+) de (\d{4})', description)
        publication = re.search(r'publicada.*?DOGC.*?de (\d{1,2})/(\d{1,2})/(\d{2,4})', description)
        if not approval or not publication or approval[2] not in MONTHS:
            raise ValueError('Explicit Normes approval/publication dates missing')
        record = _record('normes-subsidiaries-2003', 'Normes Subsidiàries de Planejament de Súria', NORMES,
                         description, _documents(normes, NORMES))
        record['fecha_aprob'] = date(int(approval[3]), MONTHS[approval[2]], int(approval[1])).isoformat()
        year = int(publication[3])
        if year < 100:
            # The explicit approval year disambiguates the source's two-digit year.
            year += int(approval[3]) // 100 * 100
        record['fecha_publicacion'] = date(year, int(publication[2]), int(publication[1])).isoformat()
        record['fase'] = 'aprobación definitiva'
        record['source_urls'] = [NORMES]
        record['coverage_notes'] = 'Published 2003 version; subsequent amendments excluded, not a consolidated current plan.'
        record['enlaces_relacionados'] = [
            {'titulo': a.find_parent('li').get_text(' ', strip=True), 'url': a['href']}
            for a in normes.select('li a[href]') if urlsplit(a['href']).hostname == 'dtes.gencat.cat'
        ]
        return [poum, record]

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pages = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-suria/1.0'
            for name, url in zip(('poum', 'documents', 'normes'), SOURCES):
                with session.get(url, timeout=40, stream=True) as response:
                    response.raise_for_status()
                    if urlsplit(response.url).hostname != 'www.suria.cat':
                        raise ValueError('Unexpected source redirect')
                    body = bytearray()
                    for chunk in response.iter_content(65536):
                        body.extend(chunk)
                        if len(body) > 4_000_000:
                            raise ValueError('Source size exceeds reviewed limit')
                    html = body.decode('utf-8')
                if self.config.get('evidence_dir'):
                    capture = Path(self.config['evidence_dir'])
                    capture.mkdir(parents=True, exist_ok=True)
                    (capture / (name + '.html')).write_text(html, encoding='utf-8')
                pages.append(html)
        rows = self.parse_projects(*pages)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES), 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
