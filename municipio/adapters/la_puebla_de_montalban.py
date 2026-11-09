"""Partial POM inventory from the official municipal WordPress public API."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.pueblademontalban.com'
API = BASE + '/wp-json/wp/v2/posts'
QUERY = '"plan de ordenación municipal"'
LIMITATIONS = [
    'Cobertura parcial: únicamente el POM documentado en publicaciones municipales; no inventario exhaustivo de obras o planeamiento.',
    'No se acredita aprobación definitiva autonómica ni vigencia actual; la noticia de 2024 refiere trámites pendientes.',
    'La sede anuncia 115 documentos urbanísticos, pero sus callbacks públicos no devolvieron un listado utilizable durante la investigación.',
    'Sin registro verificado de licencias concedidas, geometría ni coordenadas; sin descarga del expediente técnico completo.',
]


def text(html):
    return ' '.join(BeautifulSoup(html, 'html.parser').get_text(' ', strip=True).split())


def publication_date(value):
    # WordPress publication date, never the modified date or a plan agreement.
    return date.fromisoformat(value[:10]).isoformat()


def parse_projects(posts):
    documents = {}
    milestones = []
    contexts = []
    for post in posts:
        url = post['link']
        if urlparse(url).hostname != urlparse(BASE).hostname:
            raise ValueError('Unexpected non-municipal post URL')
        title = text(post['title']['rendered'])
        soup = BeautifulSoup(post['content']['rendered'], 'html.parser')
        body = text(str(soup))
        lower = body.lower()
        title_lower = title.lower()
        kind = None
        agreement = None
        if ('plan de ordenación municipal' in title_lower
                and 'aprobación' in title_lower
                and 'el pleno del ayuntamiento ha aprobado el plan de ordenación municipal' in lower
                and 'a los efectos de su aprobación definitiva' in lower):
            match = re.search(r'pleno extraordinario celebrado[^.]*?(\d{2}/\d{2}/\d{4})', lower)
            if not match:
                raise ValueError('POM agreement narrative lacks an explicit agreement date')
            day, month, year = map(int, match[1].split('/'))
            agreement = date(year, month, day).isoformat()
            kind = 'acuerdo municipal; remisión para aprobación definitiva'
        elif ('plan de ordenación municipal' in title_lower
              and 'información pública' in title_lower
              and 'inicia el período de información pública' in lower
              and 'el documento del pom' in lower):
            kind = 'información pública del POM'
        elif ('plan de ordenación municipal' in lower
              and 'continuar los trámites' in lower and 'cht' in lower):
            # A contextual update is evidence for this POM, never another project.
            kind = 'seguimiento de trámites; no acuerdo de aprobación'
            contexts.append(body)
        if kind is None:
            # Contract signatures, generic meetings and licence forms are not plans.
            continue
        published = publication_date(post['date'])
        document = {
            'url': url, 'titulo': title, 'tipo': kind,
            'fecha_publicacion': published, 'fecha_acuerdo': agreement,
            'api_url': API + '/' + str(int(post['id'])),
            'descripcion': body,
            'enlaces': sorted({a['href'] for a in soup.select('a[href]')
                               if a['href'].startswith(('https://', 'http://'))}),
        }
        if url in documents and documents[url] != document:
            raise ValueError('Conflicting duplicate municipal post')
        documents[url] = document
        if kind.startswith(('acuerdo municipal', 'información pública')):
            milestones.append(document)
    if not milestones:
        raise ValueError('No substantive POM publication found; refusing placeholder')
    ordered = sorted(documents.values(), key=lambda d: (d['fecha_publicacion'], d['url']))
    agreements = [d for d in ordered if d['fecha_acuerdo']]
    primary = agreements[-1] if agreements else sorted(milestones, key=lambda d: d['fecha_publicacion'])[-1]
    return [{
        'id': 'la-puebla-de-montalban-pom',
        'municipio': 'La Puebla de Montalbán', 'codigo_ine': '45136', 'provincia': 'Toledo',
        'titulo': 'Plan de Ordenación Municipal (POM) de La Puebla de Montalbán',
        'tipo': 'Plan de Ordenación Municipal',
        'fase': 'acuerdo municipal; aprobación definitiva no acreditada' if agreements else 'información pública',
        'fecha': None, 'fecha_publicacion': primary['fecha_publicacion'],
        'fecha_acuerdo': primary['fecha_acuerdo'], 'fecha_aprob': None,
        'url': primary['url'], 'source': 'ayuntamiento', 'origen': 'publicaciones_municipales_pom',
        'descripcion': primary['descripcion'], 'documentos': ordered,
        'source_urls': [d['url'] for d in ordered],
        'fecha_ultima_publicacion_fuente': ordered[-1]['fecha_publicacion'],
        'seguimiento': contexts, 'coverage': 'partial_pom_publications',
        'limitations': LIMITATIONS, 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }]


class LaPueblaDeMontalbanAyuntamientoAdapter(AyuntamientoAdapter):
    def fetch_posts(self):
        posts = []
        seen_ids = set()
        urls = []
        expected_pages = expected_total = None
        capture = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-la-puebla-de-montalban/1.0'
            page = 1
            while True:
                response = session.get(API, params={'search': QUERY, 'per_page': 100, 'page': page}, timeout=40)
                response.raise_for_status()
                if urlparse(response.url).hostname != urlparse(BASE).hostname:
                    raise ValueError('Unexpected API redirect')
                pages = int(response.headers['X-WP-TotalPages'])
                total = int(response.headers['X-WP-Total'])
                if expected_pages is None:
                    expected_pages, expected_total = pages, total
                if (pages, total) != (expected_pages, expected_total):
                    raise ValueError('Inventory changed during pagination; retry complete snapshot')
                batch = response.json()
                if not isinstance(batch, list) or not batch:
                    raise ValueError('Empty or invalid POM inventory page')
                for post in batch:
                    if post['id'] in seen_ids:
                        raise ValueError('Repeated post across pages; incomplete pagination')
                    seen_ids.add(post['id'])
                posts.extend(batch)
                urls.append(response.url)
                if capture:
                    folder = Path(capture)
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / f'posts-{page}.json').write_text(response.text, encoding='utf-8')
                if page >= pages:
                    break
                page += 1
        if len(posts) != expected_total:
            raise ValueError('API total does not match retrieved posts')
        return posts, urls

    def backfill_proyectos(self, out_jsonl: Path):
        posts, urls = self.fetch_posts()
        rows = parse_projects(posts)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'live_records': len(rows), 'source_urls': urls + rows[0]['source_urls'],
                'inventory_posts': len(posts), 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full current snapshot; no date filter that could discard older plan documents.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
