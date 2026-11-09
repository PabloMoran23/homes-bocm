"""Arboleas: municipal planning document inventory, grouped by instrument."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.arboleas.org/'
SOURCE = BASE + 'index.php?option=com_content&view=section&id=16&Itemid=393&lang=es'


def page_url(view, ident, offset=0):
    params = dict(option='com_content', view=view, id=ident, lang='es')
    if view == 'category':
        params.update(layout='default', limit=50, limitstart=offset)
    return BASE + 'index.php?' + urlencode(params)


def content_id(url, view):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if (parsed.hostname != 'www.arboleas.org' or parsed.path != '/index.php'
            or query.get('option') != ['com_content'] or query.get('view') != [view]):
        raise ValueError(f'Unexpected municipal {view} URL: {url}')
    ident = query.get('id', [''])[0].split(':')[0]
    if not ident.isdigit():
        raise ValueError('Missing numeric content id')
    return ident


def parse_section(html):
    section = BeautifulSoup(html, 'html.parser').select_one('#content .sectionlist')
    if section is None:
        raise ValueError('Missing planning section')
    categories = {}
    for a in section.select('a.category[href]'):
        ident = content_id(urljoin(SOURCE, a['href']), 'category')
        title = a.get_text(' ', strip=True)
        if not re.match(r'^(NNSS|Mod\. Puntual|Adap PGOU|Innovaci[oó]n|Revisi[oó]n)', title, re.I):
            raise ValueError(f'Unreviewed planning category: {title}')
        count = a.parent.select_one('.number')
        match = re.search(r'\d+', count.get_text()) if count else None
        if not match:
            raise ValueError('Category lacks document count')
        categories[ident] = {'id': ident, 'titulo': title, 'expected': int(match[0]),
                             'url': page_url('category', ident)}
    if not categories:
        raise ValueError('Empty planning inventory')
    return list(categories.values())


def parse_category(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    category = soup.select_one('#content .categorylist')
    if category is None:
        raise ValueError('Missing category document table')
    ident = content_id(url, 'category')
    articles = {}
    for a in category.select('td a[href]'):
        target = urljoin(url, a['href'])
        article_id = content_id(target, 'article')
        articles[article_id] = {'titulo': a.get_text(' ', strip=True),
                                'url': page_url('article', article_id)}
    pages = set()
    for a in category.select('.pagination a[href], a[rel="next"][href]'):
        target = urljoin(url, a['href'])
        if content_id(target, 'category') != ident:
            raise ValueError('Pagination changed category')
        query = parse_qs(urlparse(target).query)
        offset = query.get('limitstart', ['0'])[0]
        if not offset.isdigit():
            raise ValueError('Unrecognised pagination offset')
        pages.add(page_url('category', ident, int(offset)))
    return list(articles.values()), sorted(pages)


def parse_documents(html, article_url):
    article = BeautifulSoup(html, 'html.parser').select_one('#content .article')
    if article is None:
        raise ValueError(f'Missing document article: {article_url}')
    if article.select_one('.contenttoc, .pagenavbar, .article-index, .pagination a[href]'):
        raise ValueError('Paginated document article; review before extracting partial content')
    docs = {}
    for a in article.select('a[href]'):
        target = urljoin(article_url, a['href'])
        parsed = urlparse(target)
        # Exclude Joomla's print/PDF rendition of the HTML page and navigation.
        official_document = (parsed.hostname == 'www.arboleas.org' and parsed.path.startswith('/images/')) or (
            parsed.hostname == 'www.juntadeandalucia.es'
            and parsed.path.startswith('/viviendayordenaciondelterritorio/iws/pua_ext/ALMERIA/04017/'))
        if (official_document
                and re.search(r'\.(pdf|zip|rar|docx?|xlsx?|dwg)$', parsed.path, re.I)):
            target = quote(target, safe=':/?=&%+#')
            docs[target] = {'titulo': a.get_text(' ', strip=True) or a.get('title', ''),
                            'url': target, 'source_page': article_url}
    if not docs:
        raise ValueError(f'Article has no source attachments: {article_url}')
    return list(docs.values())


def group_instruments(categories):
    """Category 89's memory names Innovación 14 on its cover (March 2014)."""
    groups = {}
    for cat in categories:
        key = '94' if cat['id'] in {'89', '94'} else cat['id']
        if key not in groups:
            groups[key] = {'id': 'arboleas-planeamiento-' + key, 'municipio': 'Arboleas',
                           'codigo_ine': '04017', 'provincia': 'Almería',
                           'titulo': cat['titulo'], 'tipo': 'planeamiento_urbanistico',
                           'url': cat['url'], 'inventory_url': SOURCE,
                           'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
                           'publication_ready': False, 'geometry_status': 'unavailable',
                           'categorias_fuente': [], 'fichas_documentales': [], 'documentos': []}
        row = groups[key]
        if cat['id'] == key:
            row['titulo'], row['url'] = cat['titulo'], cat['url']
        row['categorias_fuente'].append({'titulo': cat['titulo'], 'url': cat['url']})
        row['fichas_documentales'].extend(cat['articles'])
        row['documentos'].extend(cat['documents'])
    return list(groups.values())


class ArboleasAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = self._session.get(url, timeout=(10, 45))
        response.raise_for_status()
        if urlparse(response.url).hostname != 'www.arboleas.org':
            raise ValueError('Unexpected source redirect')
        capture = self.config.get('capture_dir')
        if capture:
            folder = Path(capture)
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
            (folder / name).write_bytes(response.content)
            self.captures.append({'url': url, 'final_url': response.url, 'file': name,
                                  'status': response.status_code})
        self.source_urls.append(url)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls, self.captures = [], []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-arboleas/1.0 (public planning inventory)'
            session.mount('https://', HTTPAdapter(max_retries=Retry(
                total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])))
            self._session = session
            categories = parse_section(self._fetch(SOURCE))
            for cat in categories:
                pending, visited, articles = [cat['url']], set(), {}
                while pending:
                    url = pending.pop(0)
                    if url in visited:
                        continue
                    visited.add(url)
                    if len(visited) > 500:
                        raise ValueError('Pagination safety limit; output not written')
                    items, pages = parse_category(self._fetch(url), url)
                    articles.update((a['url'], a) for a in items)
                    pending.extend(p for p in pages if p not in visited)
                if len(articles) != cat['expected']:
                    raise ValueError(f"Incomplete category {cat['id']}: {len(articles)} != {cat['expected']}")
                cat['articles'], cat['documents'] = list(articles.values()), []
                for article in cat['articles']:
                    cat['documents'].extend(parse_documents(self._fetch(article['url']), article['url']))
            rows = group_instruments(categories)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'coverage': 'municipal_planning_inventory',
                'document_articles': sum(len(c['articles']) for c in categories),
                'source_urls': self.source_urls, 'captures': self.captures,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh; no date-based incremental omissions.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
