"""Documented planning instruments in the municipal Joomla article inventory.

This is a partial documentary inventory, not a register of approvals or licences.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.alcaladelvalle.es'
INVENTORY = BASE + '/noticias'
LIMITATIONS = [
    'Cobertura parcial: artículos municipales sobre modificaciones puntuales con PDF enlazados; no inventario completo de planeamiento ni obras.',
    'Los artículos son publicaciones documentales históricas; no acreditan el estado actual ni la aprobación del instrumento.',
    'PBOM provincial en actos preparatorios, documentos pendientes: no incorporado como expediente documental.',
    'Sin registro de licencias concedidas, fechas normalizadas de publicación/acuerdo/aprobación ni geometría verificada.',
]


def official_url(url: str, path_prefix: str) -> str:
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'www.alcaladelvalle.es'
            or not unquote(parsed.path).startswith(unquote(path_prefix))):
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def supported_title(title: str) -> bool:
    return bool(re.search(r'modificaci[oó]n puntual', title, re.I)
                and re.search(r'PGOU|planeamiento urban[ií]stico', title, re.I)
                and not re.search(r'licitaci[oó]n|contrataci[oó]n|modelo|solicitud de licencia', title, re.I))


def parse_inventory(html: str, url: str):
    soup = BeautifulSoup(html, 'html.parser')
    container = soup.select_one('main .com-content-category')
    if container is None or not container.select('th.list-title a[href]'):
        raise ValueError('Municipal article inventory missing or empty')
    counter = container.select_one('.counter')
    match = re.search(r'P[aá]gina\s+(\d+)\s+de\s+(\d+)', counter.get_text(' ', strip=True) if counter else '')
    if not match:
        raise ValueError('Missing pagination counter; cannot prove complete traversal')
    page, total = map(int, match.groups())
    if not 1 <= page <= total:
        raise ValueError('Invalid pagination counter')
    next_link = container.select_one('a.next[href]')
    if (page < total) != bool(next_link):
        raise ValueError('Incomplete or inconsistent pagination')
    next_url = official_url(urljoin(url, next_link['href']), '/noticias') if next_link else None
    entries = {}
    for link in container.select('th.list-title a[href]'):
        title = link.get_text(' ', strip=True)
        if supported_title(title):
            target = official_url(urljoin(url, link['href']), '/noiticias/')
            identity = re.match(r'/noiticias/(\d+)-', urlparse(target).path)
            if not identity:
                raise ValueError('Missing stable municipal article ID')
            entries[identity.group(1)] = {'titulo': title, 'url': target}
    return entries, next_url, page, total


def parse_instrument(html: str, url: str, article_id: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    heading = main.select_one('h1') if main else None
    if heading is None or not supported_title(heading.get_text(' ', strip=True)):
        raise ValueError('Expected named planning instrument missing')
    docs = {}
    for link in main.select('a[href]'):
        target = urljoin(url, link['href'])
        if urlparse(target).path.lower().endswith('.pdf'):
            official_url(target, '/images/Documentacion/')
            docs[target] = {'titulo': link.get_text(' ', strip=True), 'url': target,
                            'source_url': url, 'publisher': 'Ayuntamiento de Alcalá del Valle'}
    if not docs:
        raise ValueError('Planning article has no linked source PDF')
    return {
        'id': 'alcala-del-valle-planeamiento-' + article_id,
        'municipio': 'Alcalá del Valle', 'codigo_ine': '11002', 'provincia': 'Cádiz',
        'titulo': heading.get_text(' ', strip=True), 'tipo': 'planeamiento_urbanistico',
        'url': url, 'inventory_url': INVENTORY, 'source': 'ayuntamiento',
        'origen': 'inventario_documental_municipal', 'documentos': list(docs.values()),
        'coverage': 'partial_documentary_inventory', 'publication_ready': False,
        'geometry_status': 'unavailable',
    }


class AlcalaDelValleAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url: str) -> str:
        official_url(url, '/')
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-alcala-del-valle/1.0 (public planning inventory)'})
        response.raise_for_status()
        official_url(response.url, urlparse(url).path)
        if 'text/html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML municipal source')
        response.encoding = 'utf-8'
        html = response.text
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
            (directory / name).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        url = INVENTORY
        seen, entries = set(), {}
        source_urls = []
        expected_total = None
        while url:
            if url in seen:
                raise ValueError('Pagination cycle')
            seen.add(url)
            source_urls.append(url)
            items, next_url, page, total = parse_inventory(self._fetch(url), url)
            if page != len(seen) or (expected_total is not None and total != expected_total):
                raise ValueError('Pagination skipped a page or changed during extraction')
            expected_total = total
            entries.update(items)
            url = next_url
        if len(seen) != expected_total or not entries:
            raise ValueError('Incomplete inventory or no documented planning instruments')
        rows = []
        for article_id, item in sorted(entries.items()):
            source_urls.append(item['url'])
            rows.append(parse_instrument(self._fetch(item['url']), item['url'], article_id))
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'inventory_pages': len(seen),
                'source_urls': source_urls, 'limitations': LIMITATIONS,
                'coverage': 'partial_documentary_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # A full snapshot also discovers older articles; no date watermark is reliable.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
