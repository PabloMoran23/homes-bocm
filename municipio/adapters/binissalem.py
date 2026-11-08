"""Snapshot of Binissalem's official current planning document inventory."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.ajbinissalem.net'
SOURCE = BASE + '/portal-de-transparencia/instruments-de-plantejament-en-vigor/'


def _norm(text: str) -> str:
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', text.lower())
                            if not unicodedata.combining(c)).split())


def _document_url(href: str) -> str:
    parsed = urlparse(urljoin(SOURCE, href))
    if (parsed.scheme != 'https' or parsed.netloc != 'www.ajbinissalem.net'
            or not parsed.path.startswith('/wp-content/uploads/')
            or not unquote(parsed.path).lower().endswith('.pdf') or parsed.query):
        raise ValueError('Unexpected planning document URL: ' + href)
    # Preserve decomposed Unicode filenames: the live server uses those paths.
    return urlunparse(parsed._replace(path=quote(unquote(parsed.path), safe='/'), fragment=''))


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    section = soup.select_one('main section')
    heading = section.select_one('h1') if section else None
    if not heading or _norm(heading.get_text(' ', strip=True)) != 'instruments de planejament en vigor':
        raise ValueError('Expected municipal planning inventory heading missing')
    # The reviewed source is one complete static list. Fail closed on pagination
    # rather than treating its first page as the complete inventory.
    for a in soup.select('a[href]'):
        if (set(a.get('rel', [])) & {'next', 'prev'}
                or _norm(a.get_text(' ', strip=True)) in {'seguent', 'siguiente', 'next', 'anterior', '»', '›'}
                or re.search(r'(?:/page/\d+|[?&](?:page|paged)=\d+)', a['href'])):
            raise ValueError('Paginated inventory requires crawler review')
    if soup.select('.pagination, .page-numbers, .nav-links'):
        raise ValueError('Pagination markup requires crawler review')
    archive = section.select_one('.content ul.archive')
    if archive is None:
        raise ValueError('Planning document archive missing')
    records = {}
    for a in archive.select('a[href]'):
        title = a.get_text(' ', strip=True)
        normalized = _norm(title)
        if re.match(r'^normes subsidiaries(?:\b|$)', normalized):
            instrument, canonical_title = 'nnss', 'Normes subsidiàries'
        else:
            match = re.match(r'^modificacio puntual num\.?\s*(\d+)\b', normalized)
            if not match:
                raise ValueError('Unreviewed archive entry: ' + title)
            instrument = 'modificacio-' + str(int(match[1]))
            canonical_title = 'Modificació puntual núm. ' + str(int(match[1]))
        url = _document_url(a['href'])
        if instrument not in records:
            records[instrument] = {
                'id': 'binissalem-plan-' + instrument,
                'municipio': 'Binissalem', 'codigo_ine': '07008',
                'provincia': 'Illes Balears', 'titulo': canonical_title,
                'tipo': 'normas_subsidiarias' if instrument == 'nnss' else 'modificacion_planeamiento',
                'url': url, 'url_documento': url, 'inventory_url': SOURCE,
                'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
                'clasificacion_fuente': 'Instruments de planejament en vigor',
                # This is the inventory category, not an independently verified
                # approval phase: one linked document says provisional approval.
                'fase': None, 'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'geometry_status': 'unavailable',
                'coverage': 'partial_current_planning_inventory',
            }
        docs = records[instrument]['documentos']
        if not any(doc['url'] == url for doc in docs):
            docs.append({'titulo': title, 'url': url, 'source_url': SOURCE})
    if not records:
        raise ValueError('No named planning instruments in archive')
    return list(records.values())


class BinissalemAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url: str, limit: int) -> bytes:
        # Public municipal sources only; no session, authentication or APIs.
        with requests.get(url, timeout=(10, 60), stream=True,
                          headers={'User-Agent': 'Mozilla/5.0 (compatible; BinissalemInventory/1.0)'}) as response:
            response.raise_for_status()
            if urlparse(response.url).netloc != 'www.ajbinissalem.net':
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source exceeds reviewed response size; no partial extraction')
                chunks.append(chunk)
            content = b''.join(chunks)
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir'])
            path.mkdir(parents=True, exist_ok=True)
            suffix = '.pdf' if content.startswith(b'%PDF-') else '.html'
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + suffix)).write_bytes(content)
        return content

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(output)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = parse_inventory(self._fetch(SOURCE, 2_000_000).decode('utf-8'))
        checked = {}
        for row in rows:
            for doc in row['documentos']:
                if doc['url'] not in checked:
                    content = self._fetch(doc['url'], 40_000_000)
                    if not content.startswith(b'%PDF-'):
                        raise ValueError('Planning attachment does not return a PDF')
                    checked[doc['url']] = hashlib.sha256(content).hexdigest()
                doc['sha256'] = checked[doc['url']]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'documents': len(checked),
                'source_urls': [SOURCE, *checked], 'publication_ready': False,
                'coverage': 'partial_current_planning_inventory'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete snapshot; re-read inventory and verify every attachment.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No usable public register of granted licences verified'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
