"""Partial inventory of evidenced regional road works in municipal publications."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://abanilla.es/wp-json/wp/v2/posts'
LIMITATIONS = [
    'Cobertura parcial: archivo municipal consultado con search=obras; solo actuaciones viarias con carretera identificada y evidencia textual de ejecución.',
    'No es un registro de expedientes, licencias, ni un inventario exhaustivo de obras o planeamiento.',
    'Las fechas son de publicación del CMS; no se deducen acuerdos, aprobaciones, terminación ni estado actual.',
    'Sin geometría verificada; una carretera puede atravesar varios municipios. Sin coordenadas ni geocodificación.',
    'Se agrupan publicaciones del refuerzo por reciclado del firme de una misma carretera; las demás mantienen identidad documental independiente.',
]


def text(html):
    return BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)


def parse_projects(posts):
    """Require a primary road subject plus execution evidence, not a keyword hit."""
    grouped = {}
    for post in posts:
        title = text(post['title']['rendered'])
        content = post['content']['rendered']
        body = text(content)
        if not re.search(r'carretera|\bRM[-–]', title, re.I):
            continue
        if re.search(r'licitaci[oó]n|prev[eé]|adjudic|anuncio|solicitud', title, re.I):
            continue
        if not re.search(r'visit(?:aron|an|ado|a|ó).*?\bobras?\b|obras? (?:que se est[aá]n realizando|han consistido)|inicia la obra', body, re.I):
            continue
        # The first road named is the subject. Later "otras inversiones" are
        # background, never additional synthetic projects.
        road = re.search(r'\bRM[-–](?:A)?\d+\b', body, re.I)
        if not road:
            continue
        road = road[0].upper().replace('–', '-')
        url = post['link']
        if urlparse(url).hostname not in {'abanilla.es', 'www.abanilla.es'}:
            raise ValueError('Unexpected municipal article host')
        published = datetime.fromisoformat(post['date']).date().isoformat()
        lead = body[:2400].lower()
        # Shared specific method corroborates the two observed RM-414 updates.
        # A road code alone is insufficient to merge different interventions.
        recycled = 'reciclado del firme' in lead and 'emulsión bituminosa' in lead
        identity = road + ':reciclado-firme-emulsion' if recycled else str(post['id'])
        key = 'abanilla-obra-' + hashlib.sha256(identity.encode()).hexdigest()[:16]
        links = []
        for a in BeautifulSoup(content, 'html.parser').select('a[href]'):
            href = a['href']
            if urlparse(href).scheme in {'http', 'https'}:
                links.append({'titulo': a.get_text(' ', strip=True), 'url': href})
        document = {'url': url, 'titulo': title, 'fecha_publicacion': published,
                    'wp_id': post['id'], 'descripcion': body, 'enlaces': links,
                    'inventory_url': SOURCE, 'tipo': 'publicación municipal sobre obra física'}
        if key not in grouped:
            grouped[key] = {
                'id': key, 'municipio': 'Abanilla', 'codigo_ine': '30001',
                'provincia': 'Murcia', 'titulo': title, 'tipo': 'obra viaria',
                'carretera': road, 'url': url, 'source': 'ayuntamiento',
                'origen': 'archivo_noticias_municipal', 'inventory_url': SOURCE,
                'fecha_publicacion': published, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'descripcion': body, 'documentos': [],
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'coverage': 'partial_municipal_road_works_publications',
            }
        row = grouped[key]
        if url not in {d['url'] for d in row['documentos']}:
            row['documentos'].append(document)
        if published > row['fecha_publicacion']:
            row.update(titulo=title, url=url, fecha_publicacion=published, descripcion=body)
    return sorted(grouped.values(), key=lambda r: r['id'])


class AbanillaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        capture_dir = Path(captures) if captures else None
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
        posts, source_urls, seen = [], [], set()
        page, pages, total = 1, None, None
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'
            while pages is None or page <= pages:
                response = session.get(SOURCE, params={'search': 'obras', 'per_page': 100, 'page': page}, timeout=40)
                response.raise_for_status()
                if urlparse(response.url).hostname != 'abanilla.es':
                    raise ValueError('Unexpected inventory redirect')
                page_total = int(response.headers['X-WP-Total'])
                page_count = int(response.headers['X-WP-TotalPages'])
                if pages is None:
                    total, pages = page_total, page_count
                elif (page_total, page_count) != (total, pages):
                    raise ValueError('Inventory changed during pagination; retry snapshot')
                batch = response.json()
                if not isinstance(batch, list) or (page <= pages and not batch):
                    raise ValueError('Invalid inventory page')
                for post in batch:
                    if post['id'] in seen:
                        raise ValueError('Repeated post across inventory pages')
                    seen.add(post['id'])
                posts.extend(batch)
                source_urls.append(response.url)
                if capture_dir:
                    (capture_dir / f'obras-page-{page}.json').write_bytes(response.content)
                page += 1
        if len(posts) != total:
            raise ValueError('Incomplete inventory pagination')
        rows = parse_projects(posts)
        if not rows:
            raise ValueError('No usable road works with execution evidence')
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'live_records': len(rows), 'inventory_posts': len(posts),
                'pages': pages, 'source_urls': source_urls, 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Rebuild the full scoped snapshot so edits and grouped documents survive.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
