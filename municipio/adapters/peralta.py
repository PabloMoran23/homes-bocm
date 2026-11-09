"""Physical projects in Peralta's official European-funds archive (partial coverage)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://aytoperalta.com/fondos-europeos/'


def _text(node):
    return unicodedata.normalize('NFC', node.get_text(' ', strip=True)) if node else ''


def _url(base, href):
    parsed = urlparse(urljoin(base, href))
    if parsed.scheme != 'https' or parsed.netloc != 'aytoperalta.com':
        raise ValueError('Unexpected project/archive URL')
    return urlunparse(parsed._replace(fragment='', query=''))


class PeraltaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='peralta', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://aytoperalta.com')

    @staticmethod
    def parse_inventory(html, page_url=SOURCE):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('main#content')
        if not main or 'Proyectos' not in _text(main.select_one('h1')):
            raise ValueError('Missing municipal project archive')
        entries = {}
        for article in main.select('article'):
            link = article.select_one('h2.entry-title a[href]')
            if not link or not _text(link):
                raise ValueError('Unrecognized archive entry')
            url = _url(page_url, link['href'])
            if not url.startswith(SOURCE) or url == SOURCE:
                raise ValueError('Project outside reviewed archive')
            entries[url] = _text(link)
        if not entries:
            raise ValueError('Empty project inventory requires review')
        pages = set()
        # WordPress numbered/next pagination, including links outside main.
        for link in soup.select('a[href]'):
            href = link['href']
            classes = set(link.get('class', []))
            is_next = ('next' in link.get('rel', []) or 'next' in classes
                       or _text(link).lower().strip(' »›→') in {'siguiente', 'next'})
            is_page = 'page-numbers' in classes or bool(link.find_parent(class_='pagination'))
            if is_next or is_page or re.search(r'/fondos-europeos/page/\d+', href):
                url = _url(page_url, href)
                if url != SOURCE and not re.fullmatch(re.escape(SOURCE) + r'page/[1-9]\d*/?', url):
                    raise ValueError('Unsupported pagination; refusing partial archive')
                if '?' in href:
                    raise ValueError('Query pagination requires review')
                pages.add(url)
        if main.select('[data-next-page], .load-more, .infinite-scroll') or any(
            _text(node).lower() in {'mostrar más', 'cargar más', 'load more'}
            for node in main.select('button, a')
        ):
            raise ValueError('Dynamic pagination requires review')
        return entries, pages

    @staticmethod
    def parse_project(html, url, inventory_title):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('main#content.type-fondos_europeos')
        title = _text(main.select_one('h1.entry-title')) if main else ''
        if not main or title != inventory_title:
            raise ValueError('Project detail does not match inventory')
        post_ids = [c[5:] for c in main.get('class', []) if re.fullmatch(r'post-\d+', c)]
        if len(post_ids) != 1:
            raise ValueError('Missing stable municipal project ID')
        # Do not automatically promote every future archive item into physical works.
        if re.search(r'licitaci[oó]n|contrataci[oó]n|solicitud|formulario|ordenanza', title, re.I):
            raise ValueError('Archive now contains non-project material; review selection')
        if not re.search(r'instalaci[oó]n fotovoltaica|adecuaci[oó]n ambiental|adaptaci[oó]n al riesgo de inundaciones|construcci[oó]n|infraestructura esc[eé]nica', title, re.I):
            raise ValueError('Unreviewed project category')
        content = main.select_one('.page-content')
        if content is None:
            raise ValueError('Project content container disappeared')
        docs = {}
        for a in content.select('a[href]'):
            document_url = urljoin(url, a['href']).split('#')[0]
            parsed = urlparse(document_url)
            if parsed.scheme in {'http', 'https'} and re.search(r'\.(pdf|zip|docx?|xlsx?|odt)$', parsed.path, re.I):
                docs.setdefault(document_url, {'titulo': _text(a), 'url': document_url,
                                               'pagina_origen': url})
        return {
            'id': 'peralta-proy-' + post_ids[0],
            'municipio': 'Peralta / Azkoien', 'codigo_ine': '31202', 'provincia': 'Navarra',
            'titulo': title, 'tipo': 'obra_publica', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_fondos_europeos',
            'source_inventory': SOURCE, 'descripcion': _text(content) or None,
            'documentos': list(docs.values()),
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False,
            'limitaciones': 'Inventario parcial de fondos europeos; sin fechas ni fase verificadas. '
                            'La presencia en el inventario no acredita aprobación ni ejecución.',
        }

    def _fetch(self, url):
        response = requests.get(url, timeout=35, headers={'User-Agent': 'municipio-peralta/1.0'})
        response.raise_for_status()
        if urlparse(response.url).netloc != 'aytoperalta.com':
            raise ValueError('Unexpected source redirect')
        if len(response.content) > 5_000_000:
            raise ValueError('Source response exceeds reviewed size')
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha256(url.encode()).hexdigest()[:16]
            (directory / (key + '.html')).write_bytes(response.content)
        return response.content

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pending, visited, entries = {SOURCE}, set(), {}
        while pending:
            page = sorted(pending)[0]
            pending.remove(page)
            if page in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Pagination safety bound reached; no output written')
            found, pages = self.parse_inventory(self._fetch(page), page)
            visited.add(page)
            for url, title in found.items():
                if url in entries and entries[url] != title:
                    raise ValueError('Conflicting project titles across pages')
                entries[url] = title
            pending.update(pages - visited)
        rows = {}
        for url, title in entries.items():
            row = self.parse_project(self._fetch(url), url, title)
            if row['id'] in rows and rows[row['id']]['url'] != url:
                raise ValueError('Multiple URLs for one project; review canonical grouping')
            rows[row['id']] = row
        self._write(out_jsonl, list(rows.values()))
        return {'status': 'ok', 'rows': len(rows), 'coverage': 'partial: European-funds physical projects',
                'source_urls': sorted(visited | set(entries)), 'inventory_pages': len(visited)}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of this bounded inventory; no timestamp-based omissions.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
