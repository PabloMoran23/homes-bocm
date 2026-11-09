"""Current Sedipualba board: detail studies with explicit expediente identifiers.

This is a current-publication snapshot, not the historical planning register.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://sedeelectronica.beriain.es/tablondeanuncios/'
HOST = urlparse(SOURCE).hostname


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.upper())
                   if not unicodedata.combining(c))


def source_id(url, kind):
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get('id', [])
    if (parsed.scheme != 'https' or parsed.hostname != HOST
            or parsed.path != '/tablondeanuncios/' + kind + '.aspx'
            or len(values) != 1 or not values[0].isdigit()):
        raise ValueError('Unexpected municipal source URL: ' + url)
    return values[0]


def expediente(title):
    if not re.search(r'\bESTUDIO\s+(?:DE\s+)?DETALLE\b', norm(title)):
        return None
    match = re.search(r'\b(\d{4,}[A-Z])\b', norm(title))
    if not match:
        raise ValueError('Detail study without an explicit expediente; review grouping')
    return match[1]


class BeriainAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('#contenido')
        if content is None or 'Anuncios publicados' not in content.get_text(' ', strip=True):
            raise ValueError('Missing public notice inventory')
        # No pager exists in the reviewed source. Fail closed if one appears;
        # never accept an unvisited next page or ASP.NET postback page.
        if content.select('[class*="pager"], [class*="pagin"], [id*="Pager"], [id*="Pagin"]'):
            raise ValueError('Pagination requires review before extraction')
        for node in soup.select('a, input, button, link[rel]'):
            marker = norm(' '.join([node.get_text(' ', strip=True), node.get('title', ''),
                                    node.get('aria-label', ''), node.get('value', '')]))
            target = node.get('href', '') + node.get('onclick', '')
            if (re.search(r'SIGUIENTE|ANTERIOR|NEXT|PREVIOUS|PAGINA\s*\d', marker)
                    or re.search(r'Page\$|[?&](?:page|pagina|pagenumber)=', target, re.I)
                    or 'next' in node.get('rel', [])):
                raise ValueError('Pagination requires review before extraction')
        table = content.select_one('table.gridview')
        if table is None:
            raise ValueError('Missing notice table; review empty or changed inventory')
        rows = {}
        for tr in table.select('tbody tr'):
            cells = tr.find_all('td', recursive=False)
            if len(cells) != 3:
                raise ValueError('Changed inventory row layout')
            title = cells[2].get_text(' ', strip=True)
            code = expediente(title)
            if code is None:
                continue  # Activity licences, tenders, budgets, employment, etc.
            link = cells[0].select_one('a[href]')
            if link is None:
                raise ValueError('Study has no notice URL')
            url = urljoin(SOURCE, link['href'])
            notice_id = source_id(url, 'anuncio')
            dates = re.fullmatch(r'(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})',
                                 cells[1].get_text(' ', strip=True))
            if not dates:
                raise ValueError('Unrecognized public exposure dates')
            rows[notice_id] = {'expediente': code, 'titulo': title, 'url': url,
                              'fecha_publicacion': datetime.strptime(dates[1], '%d/%m/%Y').date().isoformat(),
                              'fin_exposicion': datetime.strptime(dates[2], '%d/%m/%Y').date().isoformat()}
        if not rows:
            raise ValueError('No supported current detail studies; review board')
        return list(rows.values())

    @staticmethod
    def parse_detail(html, notice):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('#leer')
        title = content.select_one('h2') if content else None
        if title is None or norm(title.get_text(' ', strip=True)) != norm(notice['titulo']):
            raise ValueError('Detail does not match inventory title')
        exposure = content.select_one('.fechas-exposicion')
        match = re.search(r'desde el d[ií]a (\d{2}/\d{2}/\d{4})', exposure.get_text(' ', strip=True) if exposure else '', re.I)
        if not match or datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() != notice['fecha_publicacion']:
            raise ValueError('Detail publication date differs from inventory')
        docs = {}
        for block in content.select('.adjunto'):
            link = block.select_one('a.adjunto-descargar[href]')
            label = block.select_one('.adjunto-titulo')
            if link is None or label is None:
                raise ValueError('Changed attachment layout')
            url = urljoin(notice['url'], link['href'])
            doc_id = source_id(url, 'documento')
            docs[doc_id] = {'titulo': label.get_text(' ', strip=True), 'url': url,
                            'url_anuncio': notice['url'], 'fecha_publicacion': notice['fecha_publicacion']}
        if not docs:
            raise ValueError('Detail study lacks source documents')
        return list(docs.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        sources = []
        capture = Path(self.config['evidence_dir']) if self.config.get('evidence_dir') else None
        if capture:
            capture.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-beriain/1.0'

            def fetch(url, name, pdf=False):
                response = session.get(url, timeout=35)
                response.raise_for_status()
                if urlparse(response.url).hostname != HOST:
                    raise ValueError('Unexpected redirect outside municipal board')
                if pdf and not response.content.startswith(b'%PDF-'):
                    raise ValueError('Attachment did not return a PDF')
                sources.append(url)
                if capture:
                    (capture / name).write_bytes(response.content)
                return response.text if not pdf else None

            notices = self.parse_inventory(fetch(SOURCE, 'inventory.html'))
            grouped = {}
            for notice in notices:
                notice_id = source_id(notice['url'], 'anuncio')
                docs = self.parse_detail(fetch(notice['url'], 'notice-' + notice_id + '.html'), notice)
                for doc in docs:
                    fetch(doc['url'], 'document-' + source_id(doc['url'], 'documento') + '.pdf', pdf=True)
                group = grouped.setdefault(notice['expediente'], [])
                group.append({**notice, 'documentos': docs})
        rows = []
        for code, events in sorted(grouped.items()):
            events.sort(key=lambda event: (event['fecha_publicacion'], event['url']))
            latest = events[-1]
            docs = {doc['url']: doc for event in events for doc in event['documentos']}
            rows.append({'id': 'beriain-estudio-detalle-' + code.lower(),
                         'municipio': 'Beriáin', 'provincia': 'Navarra', 'codigo_ine': '31905',
                         'expediente': code, 'titulo': latest['titulo'], 'tipo': 'estudio_de_detalle',
                         'fase': ('aprobación inicial' if 'APROBACION INICIAL' in norm(latest['titulo'])
                                  else 'aprobación definitiva' if 'APROBACION DEFINITIVA' in norm(latest['titulo']) else None),
                         'fecha_publicacion': latest['fecha_publicacion'], 'fecha_acuerdo': None,
                         'fecha_aprob': None, 'url': latest['url'], 'source': 'ayuntamiento',
                         'origen': 'tablon_sede_electronica', 'anuncios': events,
                         'documentos': list(docs.values()), 'lat': None, 'lon': None,
                         'geometry': None, 'geometry_status': 'unavailable', 'publication_ready': False})
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(set(sources)),
                'coverage': 'Current board detail studies with explicit expediente only; no historical coverage'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
