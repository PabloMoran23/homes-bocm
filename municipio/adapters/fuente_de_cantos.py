"""Municipal WordPress planning archive; public consultation is not approval."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.fuentedecantos.eu'
API = BASE + '/wp-json/wp/v2/posts'
SEARCH = 'Normas Subsidiarias'
INSTRUMENT = re.compile(
    r'modificación\s+puntual\s+n[º°o.]*\s*(\d+)\s*/\s*(\d{4}).*normas\s+subsidiarias',
    re.I,
)


def official_url(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname == 'www.fuentedecantos.eu'


def parse_posts(posts):
    """One instrument per numbered modification, retaining every source document."""
    grouped = {}
    for post in posts:
        title = BeautifulSoup(post['title']['rendered'], 'html.parser').get_text(' ', strip=True)
        match = INSTRUMENT.search(title)
        if not match:
            continue
        url = post['link']
        if not official_url(url):
            raise ValueError('Unexpected municipal post URL')
        content = BeautifulSoup(post['content']['rendered'], 'html.parser')
        documents = []
        for anchor in content.select('a[href]'):
            target = urljoin(url, anchor['href'])
            if urlparse(target).path.lower().endswith('.pdf') and official_url(target):
                if target not in {d['url'] for d in documents}:
                    documents.append({'titulo': anchor.get_text(' ', strip=True),
                                      'url': target, 'source_url': url})
        if not documents:
            raise ValueError('Planning instrument has no official PDF documents')
        date = post['date'][:10]
        # Validate the CMS publication date, never treat it as an agreement date.
        from datetime import date as calendar_date
        calendar_date.fromisoformat(date)
        key = f'fuente-de-cantos-mp-{int(match[1])}-{match[2]}'
        row = grouped.setdefault(key, {
            'id': key, 'municipio': 'Fuente de Cantos', 'codigo_ine': '06052',
            'provincia': 'Badajoz', 'titulo': title,
            'tipo': 'modificación puntual de normas subsidiarias',
            'url': url, 'source': 'ayuntamiento', 'origen': 'archivo_municipal_planeamiento',
            'inventory_url': API, 'fecha_publicacion': date,
            'documentos': [], 'publicaciones': [],
            'publication_ready': False, 'geometry_status': 'unavailable',
        })
        row['fecha_publicacion'] = min(date, row['fecha_publicacion'])
        publication = {'url': url, 'fecha_publicacion': date, 'titulo': title}
        if publication not in row['publicaciones']:
            row['publicaciones'].append(publication)
        for document in documents:
            if document not in row['documentos']:
                row['documentos'].append(document)
        text = content.get_text(' ', strip=True)
        if re.search(r'trámite de información pública', text, re.I):
            publication['tramite'] = 'información pública'
        # Keep the source description on its publication, without inferred current phase.
        publication['descripcion'] = text
    return sorted(grouped.values(), key=lambda row: row['id'])


class FuenteDeCantosAyuntamientoAdapter(AyuntamientoAdapter):
    def _inventory(self):
        posts, urls, seen = [], [], set()
        page, pages, total = 1, None, None
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'municipal-planning-inventory/1.0'})
            while pages is None or page <= pages:
                response = session.get(API, params={'search': SEARCH, 'per_page': 100,
                                                   'page': page, 'orderby': 'id', 'order': 'asc'},
                                       timeout=45)
                response.raise_for_status()
                if not official_url(response.url):
                    raise ValueError('Unexpected inventory redirect')
                current_pages = int(response.headers['X-WP-TotalPages'])
                current_total = int(response.headers['X-WP-Total'])
                if pages is None:
                    pages, total = current_pages, current_total
                elif (pages, total) != (current_pages, current_total):
                    raise ValueError('Inventory changed during pagination; retry extraction')
                batch = response.json()
                if not isinstance(batch, list) or (page <= pages and not batch):
                    raise ValueError('Invalid or empty inventory page')
                for post in batch:
                    if post['id'] in seen:
                        raise ValueError('Repeated post across inventory pages')
                    seen.add(post['id'])
                posts.extend(batch)
                urls.append(response.url)
                if self.config.get('capture_dir'):
                    capture = Path(self.config['capture_dir'])
                    capture.mkdir(parents=True, exist_ok=True)
                    (capture / f'planning-page-{page}.json').write_text(response.text, encoding='utf-8')
                page += 1
        if len(posts) != total:
            raise ValueError('Incomplete paginated inventory')
        return posts, urls

    def backfill_proyectos(self, out_jsonl: Path):
        posts, urls = self._inventory()
        rows = parse_posts(posts)
        if not rows:
            raise ValueError('No usable named planning instruments found')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                          encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': urls,
                'inventory_posts': len(posts), 'coverage': 'WordPress posts matching Normas Subsidiarias',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
