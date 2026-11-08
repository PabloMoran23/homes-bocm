"""Municipally linked POUM document inventory; one instrument, multiple stages."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL_SOURCE = 'https://www.montbui.cat/lajuntament/informacio-oficial/normativa/urbanisme/pla-dordenacio-urbanistica-municipal-poum'
SOURCE = 'https://www.poummontbui.com/documentacio/'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def _numeric_date(text):
    match = re.search(r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b', text)
    return date(int(match[3]), int(match[2]), int(match[1])).isoformat() if match else None


def _long_date(text):
    match = re.search(r'\b(\d{1,2}) de (\w+) de (\d{4})\b', text)
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat() if match else None


def _document_url(raw):
    # The official inventory contains literal TABs in two hrefs and HTTP links.
    # Preserve raw href separately; use the municipal site's working HTTPS URL.
    url = urljoin(SOURCE, re.sub(r'[\t\r\n]', '', raw).strip())
    parts = urlsplit(url)
    if parts.hostname not in {'www.montbui.cat', 'montbui.cat', 'www.poummontbui.com'}:
        raise ValueError('Unexpected document host in POUM inventory')
    if parts.scheme not in {'http', 'https'}:
        raise ValueError('Unexpected document scheme')
    return 'https://' + url.split('://', 1)[1]


class SantaMargaridaDeMontbuiAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.montbui.cat')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('article .entry-content')
        if content is None or 'POUM de Santa Margarida de Montbui' not in content.get_text(' ', strip=True):
            raise ValueError('Missing municipal POUM inventory identity/content')
        # This source is a complete single-page document inventory. Fail on
        # pagination rather than silently returning the first page.
        if soup.select('a[rel~=next], .pagination, .nav-links, .page-links') or any(
            a.get_text(' ', strip=True).casefold() in {'següent', 'següents', 'next', 'siguiente'}
            for a in soup.select('a[href]')
        ):
            raise ValueError('POUM inventory now paginated; crawler review required')
        sections = []
        current = {'actualizacion': None, 'paragraphs': [], 'documents': []}
        sections.append(current)
        docs = {}
        for p in content.find_all(['p', 'li']):
            text = p.get_text(' ', strip=True)
            if 'ACTUALITZACIÓ' in text:
                current = {'actualizacion': _long_date(text), 'paragraphs': [], 'documents': []}
                sections.append(current)
            current['paragraphs'].append(text)
            for a in p.select('a[href]'):
                raw = a['href']
                if not urlsplit(raw).path.lower().endswith('.pdf'):
                    continue  # Application forms and navigation are not projects.
                url = _document_url(raw)
                if url in docs:
                    continue
                title = a.get_text(' ', strip=True)
                if title.casefold() == 'aquí':
                    title = text
                doc = {'titulo': title, 'url': url, 'url_original': raw,
                       'source_url': SOURCE, 'seccion_actualizacion': current['actualizacion']}
                docs[url] = doc
                current['documents'].append(doc)
        initial = [s for s in sections if any('Aprovació Inicial del Pla' in p for p in s['paragraphs'])]
        # A later/alternative approval stage needs deliberate semantic review.
        if len(initial) != 1 or 'aprovació definitiva' in content.get_text(' ', strip=True).casefold():
            raise ValueError('Missing or ambiguous reviewed initial-approval stage')
        stage = initial[0]
        narrative = next(p for p in stage['paragraphs'] if 'Aprovació Inicial del Pla' in p)
        agreement = _long_date(narrative)
        certificates = [p for p in stage['paragraphs'] if 'certificat d’acord de Ple de data' in p]
        if not agreement or len(certificates) != 1 or _numeric_date(certificates[0]) != agreement:
            raise ValueError('POUM agreement date is missing or inconsistent')
        if not any('certificat' in d['titulo'] for d in stage['documents']) or not any(
            'Memòria' in d['titulo'] for d in stage['documents']
        ):
            raise ValueError('POUM lacks certificate or plan documents')
        publications = [p for p in stage['paragraphs'] if 'publicació realitzada en el BOPB' in p]
        if len(publications) > 1:
            raise ValueError('Ambiguous BOPB publication date')
        publication = _numeric_date(publications[0]) if publications else None
        return [{
            'id': 'santa-margarida-de-montbui-proy-poum',
            'municipio': 'Santa Margarida de Montbui', 'codigo_ine': '08250',
            'provincia': 'Barcelona',
            'titulo': 'Pla d’Ordenació Urbanística Municipal de Santa Margarida de Montbui (POUM)',
            'tipo': 'POUM', 'fase': 'aprobación inicial',
            'fecha': None, 'fecha_acuerdo': agreement, 'fecha_aprob': agreement,
            'fecha_publicacion': publication, 'fecha_publicacion_fuente': 'BOPB' if publication else None,
            'descripcion': narrative, 'url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_poum', 'source_urls': [MUNICIPAL_SOURCE, SOURCE],
            'documentos': list(docs.values()),
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'No verified project geometry extracted',
            'coverage': 'Single POUM inventory, including earlier stages; not all municipal planning or public works',
        }]

    def _fetch(self, url, capture_name):
        with requests.get(url, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-santa-margarida-de-montbui/1.0')
        }) as response:
            response.raise_for_status()
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected HTML inventory')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 3_000_000:
                    raise ValueError('Source exceeds reviewed size; no truncated extraction')
            if self.config.get('capture_dir'):
                capture = Path(self.config['capture_dir'])
                capture.mkdir(parents=True, exist_ok=True)
                (capture / capture_name).write_bytes(data)
            return data.decode('utf-8')

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        official = BeautifulSoup(self._fetch(MUNICIPAL_SOURCE, 'municipal-poum.html'), 'html.parser')
        if not any(urlsplit(urljoin(MUNICIPAL_SOURCE, a['href'])).hostname == 'www.poummontbui.com'
                   for a in official.select('a[href]')):
            raise ValueError('Municipal page no longer links the POUM portal')
        rows = self.parse_projects(self._fetch(SOURCE, 'poum-documentacio.html'))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [MUNICIPAL_SOURCE, SOURCE],
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot of the single instrument; no time-based filtering.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
