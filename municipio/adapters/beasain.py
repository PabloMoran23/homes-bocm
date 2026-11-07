"""Beasain's public DOCman PGOU inventory; one instrument, many documents."""
from __future__ import annotations

import gzip
import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.beasain.eus/es/documentos-plan-general'
LIMITATIONS = [
    'Partial municipal coverage: only the public PGOU document tree, not all urban planning or works.',
    'DOCman datePublished is document publication metadata, not an agreement or approval date.',
    'Folder phase labels describe document versions; no inferred current legal status or approval date.',
    'No verified granted-licence inventory or instrument geometry; licences disabled and coordinates absent.',
    'Document links retained; PDF contents and their legal validity are not interpreted.',
]


def inventory_url(href: str, base: str) -> str:
    url = urldefrag(urljoin(base, href))[0]
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'www.beasain.eus'
            or not (parsed.path == urlparse(SOURCE).path
                    or parsed.path.startswith(urlparse(SOURCE).path + '/'))):
        raise ValueError(f'Unexpected inventory URL: {url}')
    return url


def parse_page(html: str, url: str) -> tuple[list[dict], list[str]]:
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.select_one('.com_docman')
    if root is None or root.select_one('.docman_category') is None:
        raise ValueError(f'Missing DOCman inventory at {url}')
    category = root.select_one('.docman_category').get_text(' ', strip=True)
    documents = []
    for row in root.select('tr.docman_item'):
        anchor = row.select_one('a.docman_track_download[href]')
        if anchor is None or not anchor.get('data-id') or not anchor.get('data-title'):
            raise ValueError('Unrecognized document row')
        target = inventory_url(anchor['href'], url)
        if not urlparse(target).path.endswith('/file'):
            raise ValueError('Unexpected document target')
        published = row.select_one('time[itemprop="datePublished"]')
        raw_date = published.get('datetime') if published else None
        publication = date.fromisoformat(raw_date[:10]).isoformat() if raw_date else None
        documents.append({
            'id': anchor['data-id'], 'titulo': anchor['data-title'], 'url': target,
            'fecha_publicacion': publication, 'source_datePublished': raw_date,
            'inventory_url': url, 'categoria': category,
        })
    children = []
    for anchor in root.select('.koowa_table--categories a[href]'):
        children.append(inventory_url(anchor['href'], url))
    # Follow every numbered/next link, not just the first visible page. An
    # unrecognized form-driven paginator fails instead of returning a prefix.
    for paginator in root.select('.k-pagination, .pagination'):
        links = paginator.select('a[href]')
        for anchor in links:
            if anchor['href'] not in ('', '#'):
                children.append(inventory_url(anchor['href'], url))
        if not links and (paginator.select('input, select, button')
                          or paginator.get_text(' ', strip=True)):
            raise ValueError('Unsupported pagination control')
    return documents, list(dict.fromkeys(children))


class BeasainAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        pending, seen, documents = [SOURCE], set(), {}
        captures = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'
            while pending:
                url = pending.pop(0)
                if url in seen:
                    continue
                if len(seen) >= 250:
                    raise ValueError('Inventory exceeds page guard; no partial output written')
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if response.url != url:
                    raise ValueError(f'Inventory redirected: {url} -> {response.url}')
                if len(response.content) > 5_000_000:
                    raise ValueError('Oversize inventory page')
                page_docs, children = parse_page(response.text, url)
                seen.add(url)
                if captures:
                    name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html.gz'
                    (captures / name).write_bytes(gzip.compress(response.content))
                for doc in page_docs:
                    old = documents.get(doc['id'])
                    if old and (old['url'], old['titulo']) != (doc['url'], doc['titulo']):
                        raise ValueError('Conflicting DOCman document identity')
                    if old:
                        if url not in old['inventory_urls']:
                            old['inventory_urls'].append(url)
                    else:
                        documents[doc['id']] = {**doc, 'inventory_urls': [url]}
                pending.extend(child for child in children if child not in seen)
        if not documents:
            raise ValueError('No PGOU documents; inventory requires review')
        row = {
            'id': 'beasain-pgou', 'municipio': 'Beasain', 'codigo_ine': '20019',
            'provincia': 'Gipuzkoa', 'titulo': 'Plan General de Ordenación Urbana de Beasain (PGOU)',
            'tipo': 'planeamiento_urbanistico', 'url': SOURCE,
            'source': 'ayuntamiento', 'origen': 'inventario_documental_pgou',
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'documentos': sorted(documents.values(), key=lambda d: int(d['id'])),
            'source_urls': sorted(seen), 'limitations': LIMITATIONS,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }
        self._write(out_jsonl, [row])
        return {'status': 'ok', 'live_records': 1, 'documents': len(documents),
                'inventory_pages': len(seen), 'source_urls': sorted(seen),
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
