"""Documented planning instruments in La Muela's public Urbanismo archive."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://lamuela.org/category/urbanismo/'
CONTENT = '.elementor-widget-theme-post-content'
PLANNING = re.compile(
    r'\b(?:modificaci[oó]n.*(?:PGOU|plan general)|plan (?:general|parcial|especial)|'
    r'estudio de detalle|proyecto de (?:urbanizaci[oó]n|reparcelaci[oó]n))\b', re.I
)


def municipal_url(base, href):
    url = urlsplit(urljoin(base, href))
    if url.scheme != 'https' or url.hostname != 'lamuela.org':
        raise ValueError('Unexpected non-municipal source URL')
    return urlunsplit((url.scheme, url.netloc, url.path, url.query, ''))


class LaMuelaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='la-muela', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    @staticmethod
    def parse_inventory(html, page_url=SOURCE):
        soup = BeautifulSoup(html, 'html.parser')
        inventory = soup.select_one('.the7-simple-widget-posts')
        if inventory is None or not inventory.select('article'):
            raise ValueError('Urbanismo archive is missing or empty')
        if inventory.get('data-pagination-mode') != 'standard':
            raise ValueError('Unsupported dynamic pagination; refusing partial inventory')
        notices = []
        for article in inventory.select('article'):
            anchor = article.select_one('a.post-title[href]')
            if anchor is None:
                raise ValueError('Archive article lacks a title link')
            title = anchor.get_text(' ', strip=True)
            if not PLANNING.search(title):
                continue
            # Forms and procurement are not instruments, even with planning words.
            if re.search(r'\b(?:solicitud|modelo|licitaci[oó]n|contrataci[oó]n)\b', title, re.I):
                continue
            time = article.select_one('time[datetime]')
            published = datetime.fromisoformat(time['datetime']).date().isoformat() if time else None
            notices.append({'titulo': title, 'url': municipal_url(page_url, anchor['href']),
                            'fecha_publicacion': published})
        pages = set()
        for a in soup.select('.paginator a[href], .pagination a[href], a.page-numbers[href], a[rel~=next]'):
            if a['href'] in ('', '#'):
                continue
            url = municipal_url(page_url, a['href'])
            if not re.fullmatch(r'/category/urbanismo/(?:page/\d+/)?', urlsplit(url).path):
                raise ValueError('Unexpected archive pagination URL')
            if url != page_url:
                pages.add(url)
        if soup.select('.load-more, .dt-load-more, [data-pagination-mode="load-more"], [data-pagination-mode="ajax"]'):
            raise ValueError('Unsupported load-more pagination')
        return notices, sorted(pages)

    @staticmethod
    def parse_detail(html, notice):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one(CONTENT)
        if content is None:
            raise ValueError('Missing planning detail content')
        text = ' '.join(content.get_text(' ', strip=True).split())
        expediente = re.search(r'Expediente\s+n\s*\.?\s*[º.º°:]*\s*:?\s*(\d+/\d{4})', text, re.I)
        subject = re.search(r'Asunto:\s*(.*?)(?=\s*Se redacta|$)', text, re.I)
        if not expediente or not subject or not PLANNING.search(subject[1]):
            raise ValueError('Planning notice lacks a supported instrument and expediente')
        docs = {}
        for a in content.select('a[href]'):
            if urlsplit(urljoin(notice['url'], a['href'])).path.lower().endswith('.pdf'):
                url = municipal_url(notice['url'], a['href'])
                docs[url] = {'titulo': a.get_text(' ', strip=True), 'url': url,
                             'url_procedencia': notice['url']}
        if not docs:
            raise ValueError('Planning instrument has no source documents')
        return {
            'id': 'la-muela-proy-' + expediente[1].replace('/', '-'),
            'municipio': 'La Muela', 'provincia': 'Zaragoza', 'codigo_ine': '50182',
            'expediente': expediente[1], 'titulo': subject[1].strip(),
            'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': notice['fecha_publicacion'],
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': notice['url'], 'source': 'ayuntamiento',
            'origen': 'archivo_municipal_urbanismo', 'descripcion': text,
            'documentos': list(docs.values()), 'publicaciones': [dict(notice)],
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }

    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-la-muela/1.0'})
        response.raise_for_status()
        municipal_url(url, response.url)
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected municipal HTML source')
        if len(response.content) > 5_000_000:
            raise ValueError('Source response too large; refusing truncated parsing')
        if self.config.get('capture_dir'):
            import hashlib
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pending, visited, notices = [SOURCE], set(), {}
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Archive exceeds safety limit; no partial output written')
            found, pages = self.parse_inventory(self._fetch(url), url)
            visited.add(url)
            for notice in found:
                notices.setdefault(notice['url'], notice)
            pending.extend(page for page in pages if page not in visited)
        rows = {}
        for notice in notices.values():
            row = self.parse_detail(self._fetch(notice['url']), notice)
            if row['id'] in rows:
                previous = rows[row['id']]
                previous['publicaciones'].extend(row['publicaciones'])
                known = {d['url'] for d in previous['documentos']}
                previous['documentos'].extend(d for d in row['documentos'] if d['url'] not in known)
            else:
                rows[row['id']] = row
        if not rows:
            raise ValueError('No documented planning instruments found; review source')
        self._write(out_jsonl, sorted(rows.values(), key=lambda row: row['id']))
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(visited | set(notices)),
                'coverage': 'Partial: documented planning notices in the municipal Urbanismo archive'}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh of the selected archive; no date cursor can drop old updates.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
