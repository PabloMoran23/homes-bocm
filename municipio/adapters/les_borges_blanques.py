"""Snapshot of the municipality's published section 3.1 planning inventory."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.lesborgesblanques.cat/ajuntament/normativa_local'
MUNICIPAL_HOSTS = {'lesborgesblanques.cat', 'www.lesborgesblanques.cat'}


def _url(base, href):
    url = urljoin(base, href)
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in MUNICIPAL_HOSTS | {'dtes.gencat.cat'}:
        raise ValueError('Unexpected inventory document host or protocol')
    return quote(url, safe=":/?#%=&()+,;@")


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.node--type-page')
    body = article.select_one('.field--name-body') if article else None
    if body is None:
        raise ValueError('Missing municipal article body')
    for a in soup.select('a[href]'):
        if ('next' in a.get('rel', []) or
                a.get_text(' ', strip=True).casefold() in {'següent', 'següents', 'siguiente', 'next', '»', '›'}):
            raise ValueError('Pagination detected; refusing incomplete snapshot')
    if soup.select('.pager, nav.pager'):
        raise ValueError('Pagination detected; refusing incomplete snapshot')
    return body


class LesBorgesBlanquesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.lesborgesblanques.cat')

    @staticmethod
    def parse_inventory(html):
        body = _content(html)
        heading = next((h for h in body.select('h3') if h.get_text(' ', strip=True) == '3.1 Normativa urbanística'), None)
        if heading is None:
            raise ValueError('Missing section 3.1 planning inventory')
        rows = {}
        for block in heading.next_siblings:
            if getattr(block, 'name', None) in {'h2', 'h3'}:
                break
            if getattr(block, 'name', None) != 'ul':
                continue
            for li in block.find_all('li', recursive=False):
                text = li.get_text(' ', strip=True)
                if not text:
                    continue
                anchors = li.select('a[href]')
                if len(anchors) != 1:
                    raise ValueError('Changed inventory grouping: expected one instrument link')
                a = anchors[0]
                title = a.get_text(' ', strip=True)
                lower = title.casefold()
                if not lower.startswith(('projecte ', 'aprovació inicial de la ', 'pla de ', 'text refós del pla ', 'reurbanització ', 'conveni urbanístic ', 'modificació ')):
                    raise ValueError('Unreviewed item in planning section: ' + title)
                url = _url(SOURCE, a['href'])
                status = re.search(r'\[(Vigent|En tràmit)\]', text)
                if not status:
                    raise ValueError('Missing explicit source status')
                agreement = re.search(r'acord de JGL de data (\d{1,2})-(\d{1,2})-(\d{4})', title)
                agreed = date(int(agreement[3]), int(agreement[2]), int(agreement[1])).isoformat() if agreement else None
                kind = ('reparcelacion' if 'reparcel·lació' in lower else
                        'obra_publica' if lower.startswith('reurbanització') or 'itinerari per a vianants' in lower else
                        'gestion_urbanistica' if lower.startswith('conveni') else 'planeamiento_urbanistico')
                row = {
                    'id': 'les-borges-blanques-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                    'municipio': 'Les Borges Blanques', 'provincia': 'Lleida', 'codigo_ine': '25058',
                    'titulo': title, 'tipo': kind,
                    'fase': 'aprobación inicial' if lower.startswith('aprovació inicial') else 'aprobación definitiva' if 'aprovat definitivament' in lower else None,
                    'estado_fuente': status[1], 'fecha': None, 'fecha_publicacion': None,
                    'fecha_acuerdo': agreed, 'fecha_aprob': agreed,
                    'url': url, 'source_url': SOURCE, 'source': 'ayuntamiento',
                    'origen': 'inventario_normativa_urbanistica', 'descripcion': text,
                    'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                    'publication_ready': False,
                    'geometry_status': 'No verified geometry extracted; document links only',
                }
                if url in rows and rows[url] != row:
                    raise ValueError('Conflicting duplicate instrument URL')
                rows[url] = row
        if not rows:
            raise ValueError('Empty planning inventory')
        return list(rows.values())

    @staticmethod
    def parse_documents(html, page_url):
        body = _content(html)
        docs = {}
        for a in body.select('a[href]'):
            url = _url(page_url, a['href'])
            if urlsplit(url).path.lower().endswith('.pdf'):
                docs[url] = {'titulo': a.get_text(' ', strip=True), 'url': url, 'source_url': page_url}
        if not docs:
            raise ValueError('Instrument detail page has no source PDFs')
        return list(docs.values())

    def _fetch(self, url):
        with requests.get(url, timeout=35, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-les-borges-blanques/1.0')
        }) as response:
            response.raise_for_status()
            _url(url, response.url)
            if 'html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Expected HTML source')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Source exceeds reviewed HTML size')
                chunks.append(chunk)
            content = b''.join(chunks)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(content)
        return content.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = self.parse_inventory(self._fetch(SOURCE))
        source_urls = [SOURCE]
        for row in rows:
            url = row['url']
            if urlsplit(url).hostname == 'dtes.gencat.cat' or urlsplit(url).path.lower().endswith('.pdf'):
                row['documentos'] = [{'titulo': row['titulo'], 'url': url, 'source_url': SOURCE}]
            else:
                row['documentos'] = self.parse_documents(self._fetch(url), url)
                source_urls.append(url)
            row['url_documento'] = row['documentos'][0]['url']
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': source_urls, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete replacement of this unpaginated inventory; no date watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register; forms excluded'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
