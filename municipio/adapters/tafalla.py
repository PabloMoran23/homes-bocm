"""Tafalla's municipal PERI/PMUS document inventory (partial coverage)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

INVENTORY = 'https://www.tafalla.es/ayuntamiento/normativa/normativa-urbanistica/'
SUPPORTED = {'peri-centro-historico': 'planeamiento_urbanistico',
             'plan-de-movilidad-urbana-sostenible': 'plan_movilidad'}
LIMITATIONS = [
    'Only the municipal PERI Centro Histórico and PMUS collections; not a complete SIUN or historical planning register.',
    'No verified approval/agreement/publication dates or legal phase in parsed pages; upload paths are not dates.',
    'No granted licences, procurement notices, news or SUD EAU environmental diagnosis included.',
    'PDF plans retained as documents; no verified vector geometry or coordinates extracted.',
    'Attachment URLs inventoried; not all PDF contents downloaded or interpreted.',
]


def parse_page(html: str, url: str):
    """Extract primary content, never sidebar/breadcrumb links."""
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    content = main.select_one('div.contenido') if main else None
    heading = content.select_one('h2') if content else None
    if not heading:
        raise ValueError(f'Missing municipal content: {url}')
    for a in main.select('a[href]'):
        target = urljoin(url, a['href'])
        if (a.get_text(' ', strip=True).lower() in {'siguiente', 'next', '›', '»'}
                or 'next' in a.get('rel', []) or 'page-numbers' in a.get('class', [])
                or '/page/' in urlparse(target).path or '?paged=' in target):
            raise ValueError(f'Unreviewed pagination: {url}')
    links = {}
    for a in content.select('a[href]'):
        target = urldefrag(urljoin(url, a['href']))[0]
        if urlparse(target).scheme != 'https' or urlparse(target).hostname != 'www.tafalla.es':
            continue
        links.setdefault(target, a.get_text(' ', strip=True))
    return heading.get_text(' ', strip=True), links


def parse_inventory(html: str):
    _, links = parse_page(html, INVENTORY)
    found = {}
    for url, title in links.items():
        path = urlparse(url).path
        slug = path.rstrip('/').rsplit('/', 1)[-1]
        if slug in SUPPORTED and path == urlparse(INVENTORY).path + slug + '/':
            found[url] = {'titulo': title, 'tipo': SUPPORTED[slug]}
    if {urlparse(u).path.rstrip('/').rsplit('/', 1)[-1] for u in found} != set(SUPPORTED):
        raise ValueError('Expected PERI and PMUS collections missing; review inventory')
    return found


class TafallaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-tafalla/1.0'}) as response:
            response.raise_for_status()
            if response.url != url or 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError(f'Unexpected response for {url}')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError(f'HTML response too large: {url}')
                chunks.append(chunk)
            raw = b''.join(chunks)
            if self.config.get('capture_dir'):
                dest = Path(self.config['capture_dir'])
                dest.mkdir(parents=True, exist_ok=True)
                (dest / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(raw)
            return raw.decode('utf-8-sig')

    def backfill_proyectos(self, out_jsonl):
        inventory = parse_inventory(self._fetch(INVENTORY))
        rows, sources = [], [INVENTORY]
        for root, info in inventory.items():
            pending, visited, documents = [root], set(), {}
            while pending:
                url = pending.pop(0)
                if url in visited:
                    continue
                if len(visited) >= 100:
                    raise ValueError('Collection exceeds reviewed traversal bound')
                visited.add(url)
                title, links = parse_page(self._fetch(url), url)
                sources.append(url)
                if url == root and title != info['titulo']:
                    raise ValueError(f'Collection title differs from inventory: {url}')
                children, local_docs = [], 0
                for target, label in links.items():
                    path = urlparse(target).path
                    if path.lower().endswith('.pdf'):
                        local_docs += 1
                        doc = documents.setdefault(target, {'titulo': label, 'url': target, 'source_pages': []})
                        if url not in doc['source_pages']:
                            doc['source_pages'].append(url)
                    elif target.startswith(root) and target != root and target != url:
                        children.append(target)
                if not local_docs and not children:
                    raise ValueError(f'Collection page has no documents or children: {url}')
                pending.extend(u for u in children if u not in visited)
            if not documents:
                raise ValueError(f'Collection has no source PDFs: {root}')
            rows.append({
                'id': 'tafalla-plan-' + hashlib.sha256(root.encode()).hexdigest()[:16],
                'municipio': 'Tafalla', 'codigo_ine': '31227', 'provincia': 'Navarra',
                **info, 'url': root, 'inventory_url': INVENTORY,
                'source': 'ayuntamiento', 'origen': 'inventario_documental_municipal',
                'documentos': list(documents.values()), 'source_pages': sorted(visited),
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None, 'lat': None, 'lon': None,
                'geometry': None, 'geometry_status': 'unavailable',
                'publication_ready': False, 'coverage': 'partial', 'limitations': LIMITATIONS,
            })
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources,
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(out_jsonl, rows):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(output)

    def update_proyectos(self, out_jsonl, state_path):
        # Refresh the whole scoped inventory; no date-based incremental filtering.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
