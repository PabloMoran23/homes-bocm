"""Barbastro's municipal Estudios de Detalle inventory (partial coverage)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://barbastro.org/areas/urbanismo/estudios-en-detalle'
ARTICLE_ID = re.compile(r'^/component/content/article/(\d+)-')


def _official(url):
    p = urlparse(url)
    if p.scheme != 'https' or p.hostname != 'barbastro.org':
        raise ValueError(f'Unexpected non-municipal URL: {url}')
    return url


def _article(html):
    soup = BeautifulSoup(html, 'html.parser')
    # This inventory is currently unpaginated. Fail closed if that changes.
    if soup.select('.pagination, .pagenav, a[rel~=next], link[rel~=next], [class*=pagination]'):
        raise ValueError('Pagination detected; full traversal needs review')
    article = soup.select_one('.com-content-article')
    if article is None or article.select_one('[itemprop=articleBody]') is None:
        raise ValueError('Missing municipal article body')
    return article


def parse_inventory(html, url=SOURCE):
    article = _article(html)
    heading = article.select_one('h1')
    if heading is None or heading.get_text(' ', strip=True) != 'Estudios de Detalle':
        raise ValueError('Unexpected Estudios de Detalle inventory')
    entries = {}
    for a in article.select('[itemprop=articleBody] a[href]'):
        target = _official(urljoin(url, a['href']))
        match = ARTICLE_ID.match(urlparse(target).path)
        title = a.get_text(' ', strip=True)
        if not match or not re.match(r'^Área\s+\d', title):
            raise ValueError('Unrecognized inventory entry; refusing partial extraction')
        key = match[1]
        if key in entries and entries[key]['titulo'] != title:
            raise ValueError('Conflicting inventory identity')
        entries[key] = {'article_id': key, 'titulo': title, 'url': target}
    if not entries:
        raise ValueError('Empty planning inventory')
    return list(entries.values())


def parse_detail(html, entry):
    article = _article(html)
    description = article.select_one('[itemprop=articleBody]').get_text(' ', strip=True)
    if not re.search(r'Estudio\s+(?:de\s+)?Detalle|E\.\s*D\.', description, re.I):
        raise ValueError('Detail does not identify a planning instrument')
    # Current JTAttach and legacy Joomla links coexist. Group by the displayed
    # filename, retaining both URL variants, without claiming byte equivalence.
    documents = {}
    for a in article.select('.jtcf_adjuntos a[href], a.jtattach-filename[href]'):
        label = ' '.join(a.find_all(string=True, recursive=False)).strip()
        label = ' '.join(label.split()) or a.get_text(' ', strip=True)
        target = _official(urljoin(entry['url'], a['href']))
        path = urlparse(target).path
        if not (path.startswith(f"/attachments/article/{entry['article_id']}/") or
                path.startswith('/images/jtattach/estudios-en-detalle/')):
            raise ValueError('Unexpected attachment provenance')
        doc = documents.setdefault(label, {'titulo': label, 'urls': [], 'source_url': entry['url']})
        if target not in doc['urls']:
            doc['urls'].append(target)
    if not documents:
        raise ValueError('Planning detail has no documents')
    return {
        'id': f"barbastro-ed-{entry['article_id']}",
        'municipio': 'Barbastro', 'codigo_ine': '22048', 'provincia': 'Huesca',
        'titulo': 'Estudio de Detalle — ' + entry['titulo'],
        'tipo': 'instrumento de planeamiento', 'descripcion': description,
        'url': entry['url'], 'inventory_url': SOURCE,
        'source': 'ayuntamiento', 'origen': 'inventario_estudios_de_detalle',
        'documentos': list(documents.values()),
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'fase': None, 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'Inventario municipal de estudios de detalle; vigencia y fechas no verificadas en PDFs',
    }


class BarbastroAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='barbastro', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://barbastro.org')

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-barbastro/1.0 (public planning inventory)'

            def fetch(url, filename):
                response = session.get(_official(url), timeout=40)
                response.raise_for_status()
                _official(response.url)
                source_urls.append(response.url)
                if captures:
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / filename).write_text(response.text, encoding='utf-8')
                return response.text

            entries = parse_inventory(fetch(SOURCE, 'estudios-en-detalle.html'))
            rows = []
            for entry in entries:
                time.sleep(0.2)
                rows.append(parse_detail(fetch(entry['url'], f"article-{entry['article_id']}.html"), entry))
        # No output is replaced until all inventory entries have been processed.
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': source_urls,
                'coverage': 'complete current Estudios de Detalle index; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
