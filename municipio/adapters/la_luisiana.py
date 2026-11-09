"""La Luisiana: current municipal PGOU document inventory (not licence grants)."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = (
    'https://transparencia.laluisiana.es/es/transparencia/indicadores-de-transparencia/'
    'indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00066'
)
GROUPS = {
    'PGOU': 'PGOU',
    'PLANOS DE INFORMACIÓN': 'PLANOS-DE-INFORMACION',
    'PLANOS DE ORDENACIÓN': 'PLANOS-DE-ORDENACION',
    'PLANOS ESTUDIO DE INUNDABILIDAD': 'PLANOS-ESTUDIO-INUNDABILIDAD',
}
PREFIX = '/export/sites/laluisiana/es/transparencia/.galleries/IND-50-/'


def page_url(url):
    """Only local gallery pagination; page one is the unparameterized inventory."""
    parts = urlsplit(url)
    base = urlsplit(SOURCE)
    if (parts.scheme, parts.netloc, parts.path) != (base.scheme, base.netloc, base.path):
        raise ValueError(f'Unexpected inventory URL: {url}')
    query = []
    for key, value in parse_qsl(parts.query):
        if not key.startswith('pagegalleryfiles-') or not value.isdigit() or int(value) < 1:
            raise ValueError(f'Unknown pagination parameter: {key}={value}')
        if int(value) != 1:
            query.append((key, str(int(value))))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(sorted(query)), ''))


def parse_inventory(html, url=SOURCE):
    """Return reviewed PGOU galleries and all their linked pagination pages."""
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find('h3', string=lambda text: text and text.strip() ==
                        'PLAN GENERAL DE ORDENACIÓN URBANA DE LA LUISIANA')
    if heading is None:
        raise ValueError('Municipal PGOU heading missing')
    documents, pages, seen = {}, set(), set()
    for section in soup.select('section.gallery'):
        title = section.select_one('h4.gallery-title')
        group = title.get_text(' ', strip=True) if title else ''
        if group not in GROUPS:
            continue
        if group in seen:
            raise ValueError(f'Duplicate gallery: {group}')
        seen.add(group)
        links = section.select('table tbody a[href]')
        if not links:
            raise ValueError(f'Empty PGOU gallery: {group}')
        for anchor in links:
            target = urljoin(url, anchor['href'])
            parts = urlsplit(target)
            label = anchor.get_text(' ', strip=True)
            if (parts.scheme != 'https' or parts.netloc != urlsplit(SOURCE).netloc or
                    not parts.path.startswith(PREFIX + GROUPS[group] + '/') or
                    not parts.path.lower().endswith('.pdf') or not label):
                raise ValueError(f'Unexpected PGOU document: {target}')
            documents[target] = {'titulo': label, 'url': target, 'grupo': group,
                                 'inventory_urls': [page_url(url)]}
        for anchor in section.select('.pagination a[href]'):
            if anchor['href'].startswith('#'):
                continue
            pages.add(page_url(urljoin(url, anchor['href'])))
    if seen != set(GROUPS):
        raise ValueError(f'Missing PGOU galleries: {set(GROUPS) - seen}')
    return list(documents.values()), sorted(pages)


class LaLuisianaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        pending, visited, documents = [SOURCE], [], {}
        capture = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-la-luisiana/1.0 (public planning inventory)'
            while pending:
                url = pending.pop(0)
                if url in visited:
                    continue
                if len(visited) >= 100:
                    raise ValueError('Pagination exceeds safety bound; no partial output written')
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if page_url(response.url) != url:
                    raise ValueError('Unexpected inventory redirect')
                response.encoding = 'utf-8'
                docs, pages = parse_inventory(response.text, url)
                if capture:
                    directory = Path(capture)
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / f'live-inventory-{len(visited) + 1}.html').write_text(
                        response.text, encoding='utf-8')
                visited.append(url)
                for doc in docs:
                    if doc['url'] in documents:
                        old = documents[doc['url']]
                        old['inventory_urls'] = sorted(set(old['inventory_urls'] + doc['inventory_urls']))
                    else:
                        documents[doc['url']] = doc
                pending.extend(p for p in pages if p not in visited and p not in pending)
        row = {
            'id': 'la-luisiana-pgou', 'municipio': 'La Luisiana', 'codigo_ine': '41056',
            'provincia': 'Sevilla', 'titulo': 'Plan General de Ordenación Urbana de La Luisiana',
            'tipo': 'planeamiento_urbanistico', 'url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_municipal_pgou', 'documentos': sorted(documents.values(), key=lambda d: d['url']),
            'source_urls': visited, 'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'PGOU municipal publicado; sin determinar vigencia ni estado de aprobación',
        }
        self._write(out_jsonl, [row])
        return {'count': 1, 'written': 1, 'documents': len(documents), 'source_urls': visited,
                'coverage': 'current_pgou_document_inventory', 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                             encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full refresh: inventory has no reliable incremental timestamp.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified licence-grant inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
