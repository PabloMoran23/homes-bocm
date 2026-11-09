"""Selected physical works and urban planning from the municipal project catalogue."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.martorelles.cat'
SOURCE = BASE + '/ajuntament/consistori/accio-i-pla-de-govern/plans-projectes-campanyes-programes'
# Deliberately narrow scope: other policy plans and terse work cards are excluded.
SUPPORTED = re.compile(r"^(Projecte |Obres de millora |Substitució de fusteria |Adequació de la (?:xarxa|climatització)|Pla d'Ordenació Urbanística Municipal)")


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#readspeakerPage')
    if content is None or content.select_one('h1') is None:
        raise ValueError('Missing municipal content container')
    return content


def _official(url):
    parsed = urlsplit(url)
    return parsed.scheme == 'https' and parsed.netloc == 'www.martorelles.cat'


class MartorellesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='martorelles', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html):
        content = _soup(html)
        if content.h1.get_text(' ', strip=True) != 'Plans, projectes, campanyes, programes':
            raise ValueError('Unexpected project inventory heading')
        items = content.select('.articlelist .article-item')
        if not items:
            raise ValueError('Empty or changed municipal inventory')
        pages = {SOURCE}
        for a in content.select('.paginacio a[href]'):
            url = urljoin(SOURCE, a['href'])
            parts = urlsplit(url)
            query = parse_qs(parts.query)
            if not _official(url) or parts.path != urlsplit(SOURCE).path or set(query) - {'pag'}:
                raise ValueError('Unrecognized inventory pagination')
            if query and (len(query['pag']) != 1 or not query['pag'][0].isdigit()):
                raise ValueError('Invalid page number')
            pages.add(url)
        totals = {int(m) for m in re.findall(r'(\d+)\s+pàgines', content.get_text(' ', strip=True))}
        if len(totals) > 1:
            raise ValueError('Conflicting page totals')
        if totals:
            total = totals.pop()
            if not 1 <= total <= 100:
                raise ValueError('Inventory exceeds reviewed pagination bound')
            pages.update(SOURCE + f'?pag={n}' for n in range(2, total + 1))
        elif len(pages) > 1:
            raise ValueError('Pagination without explicit total')
        rows = []
        for item in items:
            title = item.select_one('.subtitle')
            if title is None:
                raise ValueError('Inventory item missing title')
            title_text = title.get_text(' ', strip=True)
            if not SUPPORTED.match(title_text):
                continue
            link = title.find_parent('a', href=True)
            d = item.select_one('.date')
            if link is None or d is None:
                raise ValueError('Project missing link or publication date')
            url = urljoin(SOURCE, link['href'])
            if not _official(url) or not url.startswith(SOURCE + '/'):
                raise ValueError('Unexpected project detail URL')
            rows.append({'titulo': title_text, 'url': url,
                         'fecha_publicacion': datetime.strptime(d.get_text(strip=True), '%d/%m/%Y').date().isoformat()})
        return rows, pages

    @staticmethod
    def parse_detail(html, entry):
        content = _soup(html)
        if content.h1.get_text(' ', strip=True) != entry['titulo']:
            raise ValueError('Project detail title differs from inventory')
        body = content.select_one('.ddbbtext')
        if body is None:
            raise ValueError('Project detail lacks content')
        docs = {}
        for a in body.select('a[href]'):
            url = urljoin(entry['url'], a['href'])
            if _official(url) and urlsplit(url).path.startswith('/media/repository/') and urlsplit(url).path.lower().endswith('.pdf'):
                docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                                      'source_url': entry['url']})
        if not docs:
            raise ValueError('Supported project lacks municipal PDF evidence')
        # This municipal page explicitly bundles two distinct school works.
        groups = [('', list(docs.values()))]
        if 'Escola Bressol Municipal Els Cirerers' in entry['titulo']:
            groups = []
            for token, label in [('Exterior', 'transformació exterior'), ('Pati', 'accés al pati')]:
                selected = [d for d in docs.values() if f'_Obres_{token}_' in d['url']]
                if not selected:
                    raise ValueError('School work document grouping changed')
                groups.append((label, selected))
            if sum(len(g[1]) for g in groups) != len(docs):
                raise ValueError('Ungrouped school work document')
        rows = []
        for label, documents in groups:
            identity = entry['url'] + ('#' + label if label else '')
            rows.append({**entry,
                'id': 'martorelles-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
                'municipio': 'Martorelles', 'provincia': 'Barcelona', 'codigo_ine': '08115',
                'titulo': entry['titulo'] + (' — ' + label if label else ''),
                'tipo': 'planeamiento_urbanistico' if entry['titulo'].startswith('Pla d') else 'obra_publica',
                'descripcion': body.get_text(' ', strip=True),
                'documentos': documents, 'source': 'ayuntamiento', 'origen': 'catalogo_municipal_proyectos',
                'source_inventory': SOURCE, 'fecha': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'fase': None, 'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'coverage': 'Selected documented works and urban planning; PDF contents not parsed',
            })
        return rows

    def _fetch(self, url):
        response = requests.get(url, timeout=30, headers={'User-Agent': self.config.get('user_agent', 'municipio-martorelles/1.0')}, stream=True)
        with response:
            response.raise_for_status()
            if not _official(response.url):
                raise ValueError('Source redirected outside municipal host')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Source exceeds response size bound')
                chunks.append(chunk)
            html = b''.join(chunks).decode('utf-8')
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pending, seen, entries = {SOURCE}, set(), {}
        while pending:
            url = sorted(pending)[0]
            pending.remove(url)
            rows, pages = self.parse_inventory(self._fetch(url))
            seen.add(url)
            pending.update(pages - seen)
            if len(seen | pending) > 100:
                raise ValueError('Pagination exceeds bound; no partial output written')
            for row in rows:
                if row['url'] in entries and entries[row['url']] != row:
                    raise ValueError('Conflicting duplicate project')
                entries[row['url']] = row
        if not entries:
            raise ValueError('No supported projects in complete inventory')
        rows = []
        for url, entry in sorted(entries.items()):
            rows.extend(self.parse_detail(self._fetch(url), entry))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_pages': len(seen),
                'source_urls': sorted(seen | set(entries)), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
