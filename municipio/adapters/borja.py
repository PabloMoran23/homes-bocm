"""Borja: named plans with grouped documents in the municipal transparency inventory."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://www.cumpletransparencia.es/borja/Ordenacion/'
          'planes-de-ordenacion-urbana-y-publicacion-del-plan-general-d')
DOCUMENT_HOSTS = {'borja.cumpletransparencia.es', 'www.cumpletransparencia.es'}


def _document_url(href: str) -> str:
    parts = urlsplit(urljoin(SOURCE, href))
    if (parts.scheme not in {'http', 'https'} or parts.hostname not in DOCUMENT_HOSTS
            or not unquote(parts.path).startswith('/Entidades/borja/Ordenacion/')
            or not parts.path.lower().endswith('.pdf') or parts.username or parts.password):
        raise ValueError('Unexpected Borja document URL')
    # The inventory publishes HTTP links; the same documents support verified TLS.
    return urlunsplit(('https', parts.netloc, parts.path, parts.query, ''))


def parse_projects(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('main .mainHtmlContent')
    heading = soup.select_one('main h3')
    if (content is None or heading is None
            or heading.get_text(' ', strip=True) != 'Plan General de Ordenación Urbana'
            or 'Ayuntamiento de Borja' not in soup.get_text(' ', strip=True)):
        raise ValueError('Borja planning inventory missing or changed')
    # This source is a static single-page inventory. Fail explicitly if it gains
    # pagination rather than returning an incomplete first page.
    if soup.select('[rel~=next], .pagination, .pager') or any(
        re.fullmatch(r'(siguiente|next|[»›])', a.get_text(' ', strip=True), re.I)
        for a in soup.select('a[href]')
    ):
        raise ValueError('Pagination detected: Borja inventory traversal must be reviewed')

    updated = soup.select_one('.msgPublicacion')
    rows, assigned = [], set()
    for paragraph in content.find_all('p', recursive=False):
        title = paragraph.get_text(' ', strip=True)
        if not re.match(r'^Plan\b.+\bde Borja$', title):
            continue
        group = paragraph.find_next_sibling()
        if group is None or group.name != 'ul':
            raise ValueError('Named Borja plan has no document group')
        documents, seen = [], set()
        for anchor in group.select('a[href]'):
            url = _document_url(anchor['href'])
            assigned.add(url)
            if url in seen:
                continue
            seen.add(url)
            label = anchor.find_parent('li').get_text(' ', strip=True)
            label = label.replace('(Consultar información)', '').strip()
            documents.append({'titulo': label, 'url': url,
                              'url_original': anchor['href'], 'source_url': SOURCE})
        if not documents:
            raise ValueError('Named Borja plan has no documents')
        rows.append({
            'id': 'borja-plan-' + hashlib.sha256(title.encode()).hexdigest()[:16],
            'municipio': 'Borja', 'provincia': 'Zaragoza', 'codigo_ine': '50055',
            'titulo': title, 'tipo': 'plan integral' if title.startswith('Plan Integral') else 'plan',
            'fase': None, 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'url_documento': documents[0]['url'],
            'documentos': documents, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_planeamiento',
            'fuente_actualizacion_texto': updated.get_text(' ', strip=True) if updated else None,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    all_documents = {_document_url(a['href']) for a in content.select('a[href]')
                     if urlsplit(a['href']).path.lower().endswith('.pdf')}
    if not rows or assigned != all_documents:
        raise ValueError('Empty inventory or ungrouped planning documents; review source')
    if len({row['id'] for row in rows}) != len(rows):
        raise ValueError('Duplicate Borja plan headings')
    return rows


class BorjaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='borja', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.cumpletransparencia.es/borja')

    def _fetch(self, url: str, limit: int) -> bytes:
        with requests.get(url, timeout=(15, 60), stream=True, headers={
            'User-Agent': 'municipio-borja/1.0 (public planning inventory)'
        }) as response:
            response.raise_for_status()
            if urlsplit(response.url)[:3] != urlsplit(url)[:3]:
                raise ValueError('Unexpected source redirect')
            parts, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Borja source exceeds response size limit')
                parts.append(chunk)
            return b''.join(parts)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        html = self._fetch(SOURCE, 2_000_000)
        rows = parse_projects(html.decode('utf-8-sig'))
        captures = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'inventory.html').write_bytes(html)
        urls = [SOURCE]
        for row in rows:
            for doc in row['documentos']:
                data = self._fetch(doc['url'], 25_000_000)
                if not data.startswith(b'%PDF-'):
                    raise ValueError('Borja document is not a PDF')
                doc['sha256'] = hashlib.sha256(data).hexdigest()
                urls.append(doc['url'])
                if captures:
                    (captures / (doc['sha256'] + '.pdf')).write_bytes(data)
        # Write only after the complete inventory and all documents pass checks.
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'source_urls': urls,
                'coverage': 'partial: named plans with direct documents on municipal planning page',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        """Refresh the complete current snapshot; no date-based incremental cutoff."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'count': 0, 'reason': 'No verified public granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
