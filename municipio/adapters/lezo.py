"""Municipal PGOU document tree: one record per planning instrument."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


class LezoAyuntamientoAdapter(AyuntamientoAdapter):
    BASE = 'https://azkena.lezo.eus'
    SOURCE = BASE + '/es/plan-general-de-urbanismo'

    @classmethod
    def parse_page(cls, html, url):
        soup = BeautifulSoup(html, 'html.parser')
        article = soup.select_one('article.book')
        heading = soup.select_one('h1.page-header')
        if article is None or heading is None:
            raise ValueError(f'Missing municipal book content: {url}')
        # This inventory is a book tree, not a results search. Never silently
        # accept a newly paginated version of it.
        for a in soup.select('a[href]'):
            if (a.get('rel') and 'next' in a['rel']) or a.find_parent(class_='pager') or a.find_parent(class_='pagination') or a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'hurrengoa', '›', '»'} or re.search(r'[?&]page=', a['href']):
                raise ValueError(f'Pagination requires review: {url}')
        children = {}
        for tile in soup.select('.region-content .azpiorri'):
            a = tile.find_parent('a', href=True)
            if a is None:
                raise ValueError('Book tile without link')
            target = urldefrag(urljoin(url, a['href']))[0]
            if urlparse(target).netloc != urlparse(cls.BASE).netloc:
                raise ValueError('Book child outside municipal source')
            children[target] = tile.get_text(' ', strip=True)
        docs = {}
        for a in article.select('.field--name-body a[href], .field--type-file a[href]'):
            target = urldefrag(urljoin(url, a['href']))[0]
            if urlparse(target).scheme not in {'http', 'https'}:
                raise ValueError('Unexpected document scheme')
            # Retain legacy lezo.net and bulletin URLs exactly as published.
            docs[target] = {'titulo': a.get_text(' ', strip=True), 'url': target, 'source_url': url}
        return {'titulo': heading.get_text(' ', strip=True),
                'texto': article.get_text(' ', strip=True),
                'children': children, 'documentos': list(docs.values())}

    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-lezo/1.0'})
        response.raise_for_status()
        if urlparse(response.url).netloc != urlparse(self.BASE).netloc:
            raise ValueError('Municipal source redirected outside verified host')
        if len(response.content) > 5_000_000:
            raise ValueError('Oversized municipal HTML')
        evidence = self.config.get('capture_dir')
        if evidence:
            folder = Path(evidence)
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (folder / name).write_bytes(response.content)
        self.source_urls.append(url)
        time.sleep(.15)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        tmp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        root = self.parse_page(self._fetch(self.SOURCE), self.SOURCE)
        if 'Plan General' not in root['titulo'] or not root['children']:
            raise ValueError('Planning inventory missing')
        groups = {'pgou': []}
        titles = {'pgou': 'Plan General de Urbanismo de Lezo'}
        urls = {'pgou': self.SOURCE}
        for url, title in root['children'].items():
            if re.search(r'modificaci[oó]n', title, re.I):
                key = urlparse(url).path.rstrip('/').rsplit('/', 1)[-1]
                groups.setdefault(key, []).append(url)
                titles[key], urls[key] = title, url
            elif title in {'Memoria', 'Planos'} or title.startswith('Plan General de Urbanismo de Lezo publicado'):
                groups['pgou'].append(url)
            else:
                raise ValueError(f'Unclassified planning branch: {title}')
        if not groups['pgou']:
            raise ValueError('Missing PGOU documentation')
        rows = []
        owners = {}
        for key, pending in groups.items():
            seen, docs, publication = set(), {}, None
            while pending:
                url = pending.pop(0)
                if url in seen:
                    continue
                if url in owners and owners[url] != key:
                    raise ValueError('Document page belongs to multiple instruments')
                owners[url] = key
                seen.add(url)
                if len(owners) > 150:
                    raise ValueError('Book tree exceeds review bound; output not written')
                page = self.parse_page(self._fetch(url), url)
                pending.extend(page['children'])
                for doc in page['documentos']:
                    docs.setdefault(doc['url'], doc)
                if key == 'pgou' and 'publicado' in page['texto'].lower() and 'Boletín Oficial de Gipuzkoa' in page['texto']:
                    match = re.search(r'(\d{1,2}) de diciembre de (\d{4})', page['texto'])
                    if match:
                        publication = date(int(match[2]), 12, int(match[1])).isoformat()
                if not page['children'] and not page['documentos']:
                    raise ValueError(f'Empty documentation branch: {url}')
            if not docs:
                raise ValueError(f'Instrument without documents: {key}')
            rows.append({'id': 'lezo-proy-' + key, 'municipio': 'Lezo',
                         'codigo_ine': '20053', 'provincia': 'Gipuzkoa',
                         'titulo': titles[key], 'tipo': 'planeamiento_urbanistico',
                         'url': urls[key], 'source': 'ayuntamiento',
                         'origen': 'inventario_municipal_pgou', 'fecha': None,
                         'fecha_publicacion': publication, 'fecha_acuerdo': None,
                         'fecha_aprob': None, 'documentos': list(docs.values()),
                         'source_urls': sorted(seen | {self.SOURCE}),
                         'lat': None, 'lon': None, 'geometry': None,
                         'geometry_status': 'unavailable', 'publication_ready': False})
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': self.source_urls, 'coverage': 'Municipal PGOU book tree only; not all planning or works'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
