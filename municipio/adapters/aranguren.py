"""Aranguren's municipal PGM section, corroborated by its linked BON notice.

This is a snapshot of one instrument, not the complete SIUN planning register.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.aranguren.es/servicios/urbanismo/'
MONTHS = dict(zip('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), range(1, 13)))


def spanish_date(day, month, year):
    return date(int(year), MONTHS[month.lower()], int(day)).isoformat()


def approval(text):
    match = re.search(
        r'Orden Foral\s+\S+/(\d{4})\s*,?\s+de\s+(\d{1,2})\s+de\s+(\w+).*?'
        r'se aprobó definitivamente el expediente del Plan General Municipal de Aranguren',
        text, re.I,
    )
    if not match:
        raise ValueError('Missing explicit Aranguren PGM definitive approval')
    return spanish_date(match[2], match[3], match[1])


class ArangurenAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        sections = soup.select('main #planmunicipal')
        if len(sections) != 1:
            raise ValueError('Expected one municipal PGM section')
        section = sections[0]
        # This section is a single instrument, not the neighbouring news feed.
        for a in section.select('a[href]'):
            if ('next' in a.get('rel', []) or
                    a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'más', 'ver más'}):
                raise ValueError('Unexpected pagination in PGM section; coverage needs review')
        text = section.get_text(' ', strip=True)
        approved = approval(text)
        documents = {}
        notices = set()
        pdfs = set()
        for a in section.select('a[href]'):
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            if parsed.scheme != 'https':
                continue
            if parsed.hostname == 'bon.navarra.es' and re.fullmatch(r'/es/anuncio/-/texto/\d+/\d+/\d+', parsed.path):
                notices.add(url)
                documents.setdefault(url, {'titulo': 'Anuncio BON: normativa y catálogo del PGM', 'url': url, 'procedencia': SOURCE})
            elif parsed.hostname in {'www.navarra.es', 'administracionelectronica.navarra.es'} and '.pdf' in url.lower():
                pdfs.add(url)
                documents.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url, 'procedencia': SOURCE})
        if len(notices) != 1 or not pdfs:
            raise ValueError('Missing or ambiguous PGM notice/documents')
        return {
            'id': 'aranguren-proy-pgm', 'municipio': 'Aranguren', 'codigo_ine': '31023',
            'provincia': 'Navarra', 'titulo': 'Plan General Municipal de Aranguren',
            'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación definitiva',
            'fecha': None, 'fecha_aprob': approved,
            'url': SOURCE, 'url_documento': next(iter(notices)),
            'source': 'ayuntamiento', 'origen': 'seccion_municipal_plan_general',
            'descripcion': text, 'documentos': list(documents.values()),
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'cobertura': 'PGM enlazado por Urbanismo; no incluye modificaciones de SIUN ni del portal de transparencia',
        }

    @staticmethod
    def corroborate(row, html):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('main')
        if main is None:
            raise ValueError('BON notice has no main content')
        text = main.get_text(' ', strip=True)
        if approval(text) != row['fecha_aprob']:
            raise ValueError('Municipal and BON approval dates disagree')
        dates = set()
        for a in main.select('a[href]'):
            if re.search(r'/es/boletin/-/sumario/\d+/\d+$', a['href']):
                match = re.search(r'BOLETÍN Nº\s*\d+\s*-\s*(\d{1,2}) de (\w+) de (\d{4})', a.get_text(' ', strip=True), re.I)
                if match:
                    dates.add(spanish_date(*match.groups()))
        if len(dates) != 1:
            raise ValueError('Missing or ambiguous BON publication date')
        linked = {urljoin(row['url_documento'], a['href']) for a in main.select('a[href]')}
        pdfs = {d['url'] for d in row['documentos'] if '.pdf' in d['url'].lower()}
        if not pdfs.issubset(linked):
            raise ValueError('BON does not link the municipal PGM documents')
        row['fecha_publicacion'] = next(iter(dates))
        row['fecha_publicacion_alcance'] = 'Publicación BON de normativa urbanística y catálogo; no fecha del acuerdo ni del anuncio previo de aprobación'
        row['fechas_procedencia'] = {'fecha_aprob': row['url_documento'], 'fecha_publicacion': row['url_documento']}
        for doc in row['documentos']:
            doc['procedencia_bon'] = row['url_documento']
        return row

    def _fetch(self, url):
        with requests.get(url, timeout=(10, 40), stream=True,
                          headers={'User-Agent': 'municipio-aranguren/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname not in {'www.aranguren.es', 'bon.navarra.es'}:
                raise ValueError('Unexpected source redirect')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 3_000_000:
                    raise ValueError('Source exceeds reviewed response size')
            if self.config.get('evidence_dir'):
                directory = Path(self.config['evidence_dir'])
                directory.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256(url.encode()).hexdigest()[:16]
                (directory / (digest + '.html.gz')).write_bytes(gzip.compress(bytes(content)))
                (directory / (digest + '.json')).write_text(json.dumps({
                    'url': url, 'final_url': response.url, 'status_code': response.status_code,
                    'sha256': hashlib.sha256(content).hexdigest(),
                }, ensure_ascii=False), encoding='utf-8')
            return content.decode('utf-8-sig')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        row = self.parse_inventory(self._fetch(SOURCE))
        row = self.corroborate(row, self._fetch(row['url_documento']))
        return {**self._write(out_jsonl, [row]), 'source_urls': [SOURCE, row['url_documento']],
                'coverage': row['cobertura']}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled',
                'reason': 'No verified granted-licence register; forms excluded'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
