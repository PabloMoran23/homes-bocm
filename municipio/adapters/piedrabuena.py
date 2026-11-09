"""Reviewed physical works in the official Piedrabuena news archive.

The archive is traversed completely; semantic coverage is deliberately narrower.
News documents prove physical interventions, not licences or planning approvals.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://piedrabuena.es'
INVENTORY = BASE + '/ayuntamiento/actualidad-municipal'
LIMITATIONS = [
    'Selección temática: rehabilitación de Plaza de Toros, Aula de Naturaleza y Deporte y renovación de agua en cinco calles; no inventario exhaustivo de obras.',
    'Publicaciones informativas municipales; no registro de licencias, acuerdos ni certificaciones de final de obra.',
    'Fechas del CMS son de publicación; no se deducen fechas de aprobación ni coordenadas.',
    'Documentos e imágenes se enlazan; no se interpreta su contenido gráfico ni se garantiza su disponibilidad futura.',
]


def norm(text):
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


def official_url(href, base=BASE):
    parts = urlsplit(urljoin(base, href))
    if parts.scheme not in {'https', 'http'} or parts.hostname not in {'piedrabuena.es', 'www.piedrabuena.es'}:
        raise ValueError('Unexpected source host')
    return requests.utils.requote_uri(urlunsplit(('https', 'piedrabuena.es', parts.path, parts.query, '')))


def scope(title):
    """Conservative, reviewed subjects, not a generic news-to-project classifier."""
    text = norm(title)
    if any(word in text for word in ('licitacion', 'pliego', 'convocatoria', 'adjudica', 'licencia')):
        return None
    if 'taller' in text and 'rehabilitacion de patrimonio' in text and 'clausura' in text:
        return 'rehabilitacion-plaza-toros'
    if 'construccion aula de naturaleza y deporte' == text:
        return 'aula-naturaleza-deporte'
    if 'inicia las obras' in text and 'redes de abastecimiento de agua en cinco nuevas calles' in text:
        return 'renovacion-agua-cinco-calles'
    return None


def parse_inventory(html, url=INVENTORY):
    soup = BeautifulSoup(html, 'html.parser')
    articles = {}
    for anchor in soup.select('h2.article-title a[href]'):
        target = official_url(anchor['href'], url)
        if not re.fullmatch(r'/ayuntamiento/actualidad-municipal/\d+-[^/]+', urlsplit(target).path):
            raise ValueError('Unexpected article URL')
        articles[target] = anchor.get_text(' ', strip=True)
    if not articles:
        raise ValueError('Missing municipal archive articles')
    pagination = []
    for anchor in soup.select('ul.pagination a[href]'):
        target = official_url(anchor['href'], url)
        if urlsplit(target).path != urlsplit(INVENTORY).path:
            raise ValueError('Unexpected pagination path')
        pagination.append(target)
    counts = re.findall(r'Página\s+\d+\s+de\s+(\d+)', soup.get_text(' ', strip=True))
    if not counts:
        raise ValueError('Missing archive page count')
    return articles, list(dict.fromkeys(pagination)), max(map(int, counts))


def parse_work(html, url, subject):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1.article-title')
    body = soup.select_one('[itemprop="articleBody"]')
    published = soup.select_one('time[itemprop="datePublished"][datetime]')
    if not heading or not body or not published:
        raise ValueError('Missing article title, body or publication date')
    title = heading.get_text(' ', strip=True)
    if scope(title) != subject:
        raise ValueError('Detail does not match reviewed work')
    text = body.get_text(' ', strip=True)
    normalized = norm(text)
    required = {
        'rehabilitacion-plaza-toros': ('plaza de toros de piedrabuena', 'rehabilitacion', 'trabajo efectivo'),
        'aula-naturaleza-deporte': ('contruccion del aula de naturaleza y deporte',),
        'renovacion-agua-cinco-calles': ('ha comenzado las obras', 'eloy gonzalo', 'monico sanchez', 'serna', 'general sabariego', 'castillo'),
    }
    if not all(token in normalized for token in required[subject]):
        raise ValueError('Physical intervention not supported by article body')
    publication_date = date.fromisoformat(published['datetime'][:10]).isoformat()
    documents = {url: {'titulo': title, 'url': url, 'tipo': 'noticia_municipal', 'fecha_publicacion': publication_date}}
    for anchor in body.select('a[href]'):
        target = urljoin(url, anchor['href'])
        if urlsplit(target).scheme in {'http', 'https'}:
            documents.setdefault(target, {'titulo': anchor.get_text(' ', strip=True), 'url': target, 'tipo': 'enlace_del_articulo'})
    for img in body.select('img[src]'):
        target = official_url(img['src'], url)
        documents.setdefault(target, {'titulo': img.get('alt', ''), 'url': target, 'tipo': 'imagen_municipal'})
    return {
        'id': 'piedrabuena-' + subject + '-' + publication_date[:4],
        'municipio': 'Piedrabuena', 'provincia': 'Ciudad Real', 'codigo_ine': '13063',
        'titulo': title, 'tipo': 'obra_publica', 'descripcion': text,
        'fecha_publicacion': publication_date, 'url': url, 'inventory_url': INVENTORY,
        'source': 'ayuntamiento', 'origen': 'noticia_municipal_obra_fisica',
        'documentos': list(documents.values()), 'publication_ready': False,
        'geometry_status': 'unavailable',
    }


def group_works(rows):
    """Keep related notices/assets in one subject/year, with per-notice dates."""
    grouped = {}
    for row in sorted(rows, key=lambda item: (item['fecha_publicacion'], item['url'])):
        if row['id'] not in grouped:
            grouped[row['id']] = dict(row, documentos=list(row['documentos']))
            continue
        target = grouped[row['id']]
        urls = {doc['url'] for doc in target['documentos']}
        target['documentos'].extend(doc for doc in row['documentos'] if doc['url'] not in urls)
    return list(grouped.values())


class PiedrabuenaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(url, timeout=40)
        response.raise_for_status()
        if official_url(response.url) != official_url(url):
            raise ValueError('Unexpected source redirect')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            import hashlib
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest() + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        queue, seen, articles, signatures = [INVENTORY], set(), {}, set()
        expected = 0
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0'
            session.mount('https://', HTTPAdapter(max_retries=Retry(
                total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))))
            while queue:
                url = queue.pop(0)
                if url in seen:
                    continue
                if len(seen) >= 2000:
                    raise ValueError('Archive safety bound reached; output not written')
                found, links, count = parse_inventory(self._fetch(session, url), url)
                signature = tuple(sorted(found))
                if signature in signatures:
                    raise ValueError('Archive repeated a page; pagination may be ignored')
                signatures.add(signature)
                seen.add(url)
                articles.update(found)
                expected = max(expected, count)
                queue.extend(link for link in links if link not in seen and link not in queue)
            if len(seen) != expected:
                raise ValueError(f'Incomplete pagination: {len(seen)} of {expected}')
            rows = []
            selected = []
            for url, title in sorted(articles.items()):
                subject = scope(title)
                if subject:
                    rows.append(parse_work(self._fetch(session, url), url, subject))
                    selected.append(url)
        rows = group_works(rows)
        if not rows:
            raise ValueError('No verified physical works found; output not written')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'archive_pages': len(seen),
                'archive_articles': len(articles), 'source_urls': [INVENTORY] + selected,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
