"""Municipal Obras EU dossiers, discovered through the public WordPress inventory."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://najera.es'
API = BASE + '/wp-json/wp/v2/pages'
INVENTORY = BASE + '/obras-eu/'
LIMITATIONS = [
    'Partial coverage: public child pages of Obras EU only; not all municipal works or planning.',
    'WordPress publication dates describe dossiers, not work agreements, approvals or completion.',
    'Route and Parque Natural are two interventions grouped in one municipal dossier.',
    'Source contains incomplete editorial fragments and approximate dates; narrative retained without inferring dates or budgets.',
    'No granted licence inventory or verified project geometry; SIU requests returned HTTP 403 during research.',
]


def text(html):
    return BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)


def official_url(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.netloc == 'najera.es'


def wp_date(value):
    # WP date is local publication time. Do not substitute modified or date_gmt.
    if not value or value.startswith('0000-'):
        return None
    return datetime.fromisoformat(value).date().isoformat()


class NajeraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []

    @staticmethod
    def parse_parent(items):
        if len(items) != 1:
            raise ValueError('Expected exactly one Obras EU inventory')
        item = items[0]
        if item.get('slug') != 'obras-eu' or item.get('link') != INVENTORY:
            raise ValueError('Unexpected municipal inventory identity')
        return int(item['id'])

    @staticmethod
    def parse_project(item, parent_id):
        url = item['link']
        if (item.get('parent') != parent_id or item.get('status') != 'publish'
                or not official_url(url) or not urlparse(url).path.startswith('/obras-eu/')
                or url == INVENTORY):
            raise ValueError('Unexpected dossier provenance')
        title = text(item['title']['rendered'])
        soup = BeautifulSoup(item['content']['rendered'], 'html.parser')
        paragraphs = [p.get_text(' ', strip=True) for p in soup.select('p') if p.get_text(strip=True)]
        narrative = '\n'.join(paragraphs)
        # Require a physical subject AND a source statement of execution. Mere
        # plans, forms, tenders, cultural events and funding news are insufficient.
        physical = re.search(r'placas solares|alumbrado|repavimentaci[oó]n|ruta cicloturista', narrative, re.I)
        execution = re.search(r'inici[oó] el proceso de instalaci[oó]n|obras.{0,180}comenzaron|realiz[oó] una serie de obras|comenz[oó] a ejecutar dos obras', narrative, re.I)
        if not title or not physical or not execution or 'Nájera' not in narrative:
            raise ValueError(f'Dossier {item["id"]} lacks verified physical-work narrative; review scope')
        documents = {url: {'titulo': title, 'url': url, 'tipo': 'ficha_municipal_obras'}}
        for a in soup.select('a[href]'):
            href = requests.compat.urljoin(url, a['href'])
            if official_url(href) and urlparse(href).path.lower().endswith('.pdf'):
                documents.setdefault(href, {'titulo': a.get_text(' ', strip=True), 'url': href, 'tipo': 'pdf'})
        return {
            'id': f'najera-obras-eu-{int(item["id"])}',
            'municipio': 'Nájera', 'provincia': 'La Rioja', 'codigo_ine': '26102',
            'titulo': title, 'tipo': 'obra_publica', 'descripcion': narrative,
            'fecha': None, 'fecha_publicacion': wp_date(item.get('date')),
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': url, 'source': 'ayuntamiento', 'origen': 'ficha_municipal_obras_eu',
            'documentos': list(documents.values()),
            'provenance': {'inventory_url': INVENTORY, 'api_url': API,
                           'wordpress_id': item['id'], 'wordpress_parent': parent_id,
                           'publication_field': 'date', 'modified': item.get('modified')},
            'coverage_unit': 'ficha municipal; puede agrupar varias intervenciones',
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }

    def _get(self, session, params):
        response = session.get(API, params=params, timeout=40)
        response.raise_for_status()
        self.source_urls.append(response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / f'live-api-{len(self.source_urls):03}.json').write_text(response.text, encoding='utf-8')
        items = response.json()
        if not isinstance(items, list):
            raise ValueError('WordPress inventory is not a list')
        pages = int(response.headers['X-WP-TotalPages'])
        total = int(response.headers['X-WP-Total'])
        return items, pages, total

    def _inventory(self, session, params):
        items, pages, total = self._get(session, {**params, 'per_page': 100, 'page': 1})
        if pages < 1 or total < 1:
            raise ValueError('Empty inventory requires review')
        for page in range(2, pages + 1):
            extra, current_pages, current_total = self._get(session, {**params, 'per_page': 100, 'page': page})
            if (current_pages, current_total) != (pages, total):
                raise ValueError('Inventory changed during pagination; retry snapshot')
            items.extend(extra)
        if len(items) != total or len({x['id'] for x in items}) != total:
            raise ValueError('Incomplete or duplicate WordPress pagination')
        return items

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-najera/1.0 (public municipal works inventory)'
            parent = self.parse_parent(self._inventory(session, {'slug': 'obras-eu'}))
            children = self._inventory(session, {'parent': parent, 'orderby': 'id', 'order': 'asc'})
            rows = [self.parse_project(item, parent) for item in children]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls + [INVENTORY] + [r['url'] for r in rows],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
