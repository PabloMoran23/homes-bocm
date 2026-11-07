"""Sonseca's published NNSS inventory; no licence or approval inference."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.sonseca.es/documentos/'
HOSTS = {'www.sonseca.es', 'sonseca.es'}
LIMITATIONS = [
    'Partial coverage: only the NNSS instrument linked by the municipal document inventory.',
    'No complete regional planning register, amendments, works history or granted licences covered.',
    'No verified approval/agreement/publication dates, legal currency or project geometry.',
    'PDF is a scanned document; upload path and PDF creation date are not approval dates.',
]


def _normal(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


def _official(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname in HOSTS


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    if not _official(source_url):
        raise ValueError('Unexpected inventory origin')
    soup = BeautifulSoup(html, 'html.parser')
    # The observed inventory is one static page. Fail explicitly if pagination
    # appears, rather than pretending the first page is a complete snapshot.
    if soup.select('a[rel~=next], .pagination a, a.page-numbers, .nav-links a'):
        raise ValueError('Inventory pagination detected; coverage must be reviewed')
    records = {}
    for card in soup.select('.nectar-hor-list-item'):
        label = card.select_one('.nectar-list-item')
        if label is None:
            continue
        title = label.get_text(' ', strip=True)
        normalized = _normal(title)
        if not re.fullmatch(r'normas subsidiarias de planeamiento urbanistico de sonseca', normalized):
            continue
        documents = []
        for anchor in card.select('a[href]'):
            target = urljoin(source_url, anchor['href'])
            if not _official(target) or not urlparse(target).path.lower().endswith('.pdf'):
                raise ValueError('NNSS card contains an unexpected document URL')
            if target not in documents:
                documents.append(target)
        if not documents:
            raise ValueError('NNSS instrument has no document')
        if normalized not in records:
            records[normalized] = {
                'id': 'sonseca-plan-' + hashlib.sha256(normalized.encode()).hexdigest()[:16],
                'municipio': 'Sonseca', 'provincia': 'Toledo', 'codigo_ine': '45163',
                'titulo': title, 'tipo': 'Normas Subsidiarias de Planeamiento',
                'url': source_url, 'inventory_url': source_url,
                'source': 'ayuntamiento', 'origen': 'inventario_documental_municipal',
                'descripcion': 'Instrumento de planeamiento publicado en el inventario municipal de documentos.',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None,
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'documentos': [], 'coverage': 'partial_current_document_inventory',
            }
        row = records[normalized]
        for target in documents:
            if not any(d['url'] == target for d in row['documentos']):
                row['documentos'].append({'titulo': title, 'url': target, 'source_url': source_url})
        row['url_documento'] = row['documentos'][0]['url']
    if not records:
        raise ValueError('Municipal NNSS inventory missing or markup changed')
    return list(records.values())


class SonsecaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='sonseca', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def _fetch(self, url: str, limit: int) -> tuple[bytes, str, str]:
        if not _official(url):
            raise ValueError('Unexpected source origin')
        # Check each redirect before following it.
        for _ in range(6):
            with requests.get(url, timeout=(15, 60), stream=True, allow_redirects=False,
                              headers={'User-Agent': 'municipio-sonseca/1.0'}) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers['Location'])
                    if not _official(url):
                        raise ValueError('Unexpected source redirect')
                    continue
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_content(65536):
                    data.extend(chunk)
                    if len(data) > limit:
                        raise ValueError('Source exceeds size limit; extraction aborted')
                return bytes(data), url, response.headers.get('Content-Type', '')
        raise ValueError('Too many source redirects')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        body, url, content_type = self._fetch(SOURCE, 5_000_000)
        if 'html' not in content_type.lower():
            raise ValueError('Inventory is not HTML')
        rows = parse_inventory(body.decode('utf-8'), url)
        capture_dir = self.config.get('capture_dir')
        captures = Path(capture_dir) if capture_dir else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'documentos.html').write_bytes(body)
        sources = [url]
        for row in rows:
            for document in row['documentos']:
                data, resolved_url, mime = self._fetch(document['url'], 30_000_000)
                if not data.startswith(b'%PDF-'):
                    raise ValueError('Linked planning document is not a PDF')
                document.update(resolved_url=resolved_url, content_type=mime,
                                sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
                sources.append(document['url'])
                if captures:
                    (captures / (document['sha256'] + '.pdf')).write_bytes(data)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'live_records': len(rows),
                'source_urls': list(dict.fromkeys(sources)), 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'count': 0, 'reason': 'No verified granted-licence register; forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
