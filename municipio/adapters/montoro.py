"""Two documented municipal plans; no inference of licences or approval status."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://montoro.es/urbanismo/'


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


def plan_kind(title):
    title = normalized(title)
    if title == 'plan de accion de agenda urbana':
        return 'agenda_urbana'
    if title == 'plan municipal de vivienda y suelo de montoro':
        return 'plan_municipal_vivienda_suelo'
    return None


def official_url(base, href):
    url = urljoin(base, href)
    parts = urlparse(url)
    if parts.scheme != 'https' or parts.hostname not in {'montoro.es', 'www.montoro.es'}:
        raise ValueError(f'Unexpected municipal source: {url}')
    return urlunparse(parts._replace(fragment=''))


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#main-content')
    if main is None:
        raise ValueError('Missing municipal main-content')
    plans = {}
    for a in main.select('a[href]'):
        title = a.get_text(' ', strip=True)
        kind = plan_kind(title)
        if kind:
            target = official_url(url, a['href'])
            plans[(kind, target)] = {'kind': kind, 'titulo': title, 'url': target, 'inventory_url': url}
    pages = set()
    # Only the Urbanismo archive pagination; the news items themselves are not projects.
    for a in main.select('.pagination a[href], a[rel="next"]'):
        target = official_url(url, a['href'])
        if not re.fullmatch(r'/urbanismo/(?:page/\d+/)?', urlparse(target).path):
            raise ValueError(f'Unrecognized inventory pagination: {target}')
        pages.add(urlunparse(urlparse(target)._replace(query='')))
    return list(plans.values()), sorted(pages)


def parse_detail(html, url, expected_kind=None):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#main-content')
    if main is None:
        raise ValueError('Missing plan detail content')
    heading = main.select_one('h1')
    if heading is None or plan_kind(heading.get_text(' ', strip=True)) is None:
        raise ValueError('Detail is not a supported municipal plan')
    if expected_kind and plan_kind(heading.get_text(' ', strip=True)) != expected_kind:
        raise ValueError('Plan detail identity differs from inventory')
    body = main.select_one('.et_pb_post_content')
    if body is None:
        raise ValueError('Missing plan document body')
    docs = {}
    for a in body.select('a[href]'):
        if urlparse(urljoin(url, a['href'])).path.lower().endswith('.pdf'):
            target = official_url(url, a['href'])
            docs[target] = {'titulo': a.get_text(' ', strip=True), 'url': target, 'provenance_url': url}
    if not docs:
        raise ValueError('Plan detail has no municipal PDF documents')
    result = {'documentos': list(docs.values()), 'descripcion': body.get_text(' ', strip=True)}
    meta = soup.select_one('meta[property="article:published_time"]')
    if meta:
        result['fecha_publicacion'] = datetime.fromisoformat(meta['content'].replace('Z', '+00:00')).date().isoformat()
    return result


class MontoroAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(url, timeout=45)
        response.raise_for_status()
        official_url(url, response.url)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
            (directory / name).write_bytes(response.content)
        self.source_urls.append(url)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        pending, visited, fingerprints, plans = [SOURCE], set(), set(), {}
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; MontoroMunicipalInventory/1.0)'
            while pending:
                url = pending.pop(0)
                if url in visited:
                    continue
                if len(visited) >= 100:
                    raise ValueError('Pagination safety bound exceeded; output not written')
                html = self._fetch(session, url)
                # Detect servers returning the first page for every page URL.
                fingerprint = hashlib.sha256(html.encode()).hexdigest()
                if fingerprint in fingerprints:
                    raise ValueError('Repeated inventory page; cannot establish complete pagination')
                fingerprints.add(fingerprint)
                visited.add(url)
                found, pages = parse_inventory(html, url)
                for item in found:
                    key = (item['kind'], item['url'])
                    existing = plans.setdefault(key, {**item, 'inventory_urls': []})
                    if item['inventory_url'] not in existing['inventory_urls']:
                        existing['inventory_urls'].append(item['inventory_url'])
                pending.extend(page for page in pages if page not in visited)
            rows = {}
            for item in plans.values():
                kind, target = item['kind'], item['url']
                row = rows.setdefault(kind, {
                    'id': 'montoro-plan-' + kind, 'municipio': 'Montoro', 'codigo_ine': '14043',
                    'provincia': 'Córdoba', 'titulo': item['titulo'], 'tipo': kind,
                    'url': target, 'source': 'ayuntamiento', 'origen': 'documentos_planes_municipales',
                    'inventory_url': SOURCE, 'documentos': [], 'source_urls': [],
                    'publication_ready': False, 'geometry_status': 'unavailable',
                })
                if urlparse(target).path.lower().endswith('.pdf'):
                    detail = {'documentos': [{'titulo': item['titulo'], 'url': target,
                                             'provenance_url': item['inventory_url'],
                                             'provenance_urls': item['inventory_urls']}]}
                else:
                    detail = parse_detail(self._fetch(session, target), target, expected_kind=kind)
                for doc in detail.pop('documentos'):
                    if doc['url'] not in {d['url'] for d in row['documentos']}:
                        row['documentos'].append(doc)
                row.update(detail)
                row['source_urls'] = sorted(set(row['source_urls'] + item['inventory_urls'] + [target]))
        if not rows:
            raise ValueError('No supported municipal plans found; output not written')
        self._write(out_jsonl, list(rows.values()))
        return {'count': len(rows), 'written': len(rows), 'source_urls': self.source_urls,
                'coverage': 'Agenda Urbana and PMVS documents linked from all Urbanismo archive pages',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Current source snapshot, not a claim of incremental or historical completeness.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
