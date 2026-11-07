"""Named physical works in the official Jódar publication inventory.

Funding notices support existence of a named project, not licence grants,
project approval dates, execution status or geometry.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.jodar.es/wp-json/wp/v2/posts'
HOSTS = {'www.jodar.es', 'jodar.es'}


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if unicodedata.category(c) != 'Mn')


def parse_posts(posts):
    """Conservative subset: municipal funding narrative naming physical work."""
    grouped = {}
    for post in posts:
        url = post['link']
        if urlparse(url).hostname not in HOSTS:
            raise ValueError('Unexpected publication host')
        soup = BeautifulSoup(post['content']['rendered'], 'html.parser')
        for paragraph in soup.find_all('p'):
            text = paragraph.get_text(' ', strip=True)
            if 'ayuntamiento de jodar' not in _norm(text):
                continue
            # A generic subsidy, procurement title or licence form cannot match.
            match = re.search(r'para el proyecto\s+[“"«]([^”"»]+)[”"»]', text, re.I)
            if not match or 'subvencion' not in _norm(text):
                continue
            title = match[1].strip()
            if not re.search(r'\b(restitucion|rehabilitacion|construccion|pavimentacion|urbanizacion|reforma)\b', _norm(title)):
                continue
            identity = _norm(' '.join(title.split()))
            key = 'jodar-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16]
            published = date.fromisoformat(post['date'][:10]).isoformat()
            documents = [{'titulo': BeautifulSoup(post['title']['rendered'], 'html.parser').get_text(' ', strip=True),
                          'url': url, 'tipo': 'publicación municipal',
                          'fecha_publicacion': published, 'wp_post_id': post['id']}]
            documents.extend({'titulo': a.get_text(' ', strip=True), 'url': a['href'],
                              'tipo': 'enlace documental de la publicación'}
                             for a in soup.select('a[href]')
                             if urlparse(a['href']).scheme in ('http', 'https'))
            if key not in grouped:
                grouped[key] = {
                    'id': key, 'municipio': 'Jódar', 'provincia': 'Jaén',
                    'codigo_ine': '23053', 'titulo': title, 'tipo': 'obra pública',
                    'url': url, 'inventory_url': SOURCE,
                    'source': 'ayuntamiento', 'origen': 'publicaciones_municipales',
                    'fecha_publicacion': published, 'fecha_acuerdo': None,
                    'fecha_aprob': None, 'descripcion': text, 'documentos': [],
                    'lat': None, 'lon': None, 'geometry': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                    'coverage': 'partial_named_physical_projects_in_funding_notices',
                }
            record = grouped[key]
            for document in documents:
                if document['url'] not in {d['url'] for d in record['documentos']}:
                    record['documentos'].append(document)
            if text not in record['descripcion']:
                record['descripcion'] += '\n' + text
    return list(grouped.values())


class JodarAyuntamientoAdapter(AyuntamientoAdapter):
    def fetch_posts(self):
        posts = []
        expected = None
        pages = None
        page = 1
        capture = self.config.get('capture_dir')
        with requests.Session() as session:
            while pages is None or page <= pages:
                response = session.get(SOURCE, params={'per_page': 100, 'page': page},
                                       headers={'User-Agent': 'municipio-jodar/1.0'}, timeout=40)
                response.raise_for_status()
                if urlparse(response.url).hostname not in HOSTS:
                    raise ValueError('Unexpected inventory redirect')
                total = int(response.headers['X-WP-Total'])
                total_pages = int(response.headers['X-WP-TotalPages'])
                if expected is None:
                    expected, pages = total, total_pages
                if (expected, pages) != (total, total_pages):
                    raise ValueError('Inventory changed during pagination; retry snapshot')
                batch = response.json()
                if not isinstance(batch, list) or (not batch and total):
                    raise ValueError('Invalid or empty inventory page')
                if capture:
                    path = Path(capture)
                    path.mkdir(parents=True, exist_ok=True)
                    (path / f'posts-{page}.json').write_text(response.text, encoding='utf-8')
                posts.extend(batch)
                page += 1
        if len(posts) != expected or len({p['id'] for p in posts}) != expected:
            raise ValueError('Incomplete or duplicate paginated inventory')
        return posts

    def backfill_proyectos(self, out_jsonl: Path):
        posts = self.fetch_posts()
        rows = parse_posts(posts)
        if not rows:
            raise ValueError('No usable named physical projects in current inventory')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'inventory_posts': len(posts),
                'source_urls': [SOURCE] + [d['url'] for r in rows for d in r['documentos']],
                'coverage': 'partial_named_physical_projects_in_funding_notices',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
