"""Partial documentary POM inventory, grouped as one municipal planning instrument."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

POM = 'https://aytocabanillas.org/ayuntamiento/normativa/urbanismo/pom/'
TRANSPARENCY = 'https://cabanillasdelcampo.sedelectronica.es/transparency/19e73073-230f-4f4c-bd85-e7ee8099c1b0/'
LIMITATIONS = [
    'Cobertura parcial del POM; no es un inventario exhaustivo de proyectos municipales.',
    'No se recorren las carpetas Wicket: POM 2005, modificaciones aprobadas/en tramitación, planes de desarrollo y especiales.',
    'Los planos y memoria municipales son documentación histórica informativa; no se garantiza su consolidación ni vigencia.',
    'Las fechas de publicación pertenecen a cada anuncio, no a la aprobación del POM; no se extraen fechas de acuerdo.',
    'Sin registro verificado de licencias concedidas ni geometrías vectoriales vinculadas; sin coordenadas.',
]


def _text(node):
    return node.get_text(' ', strip=True)


def _no_pagination(soup):
    for a in soup.select('a[href], button'):
        label = (_text(a) + ' ' + a.get('aria-label', '') + ' ' + a.get('title', '')).lower()
        if (set(a.get('rel', [])) & {'next', 'prev'} or
                re.search(r'\b(siguiente|anterior|next|previous|cargar más|mostrar más)\b', label)):
            raise ValueError('Inventory pagination detected; refusing an incomplete snapshot')
    if soup.select('.pagination, .pager, .page-numbers, .navigator'):
        raise ValueError('Inventory pager detected; review traversal before extracting')


def _publication(title):
    """Only explicitly labelled publication dates, never upload paths or creation dates."""
    tail = title.lower().split('publicación', 1)
    if len(tail) != 2:
        return None
    match = re.search(r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b', tail[1])
    if match:
        return date(int(match[3]), int(match[2]), int(match[1])).isoformat()
    months = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
    match = re.search(r'\b(\d{1,2}) de (' + '|'.join(months) + r') de (\d{4})\b', tail[1])
    if match:
        return date(int(match[3]), months.index(match[2]) + 1, int(match[1])).isoformat()
    return None


class CabanillasDelCampoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(pom_html, transparency_html):
        pom = BeautifulSoup(pom_html, 'html.parser')
        sede = BeautifulSoup(transparency_html, 'html.parser')
        _no_pagination(pom)
        _no_pagination(sede)
        if not any('Plan de Ordenación Municipal' in _text(h) for h in pom.select('h1')):
            raise ValueError('Missing municipal POM heading')
        content = sede.select_one('#content')
        if content is None or 'PLANEAMIENTO Y NORMATIVA' not in _text(content).upper():
            raise ValueError('Missing transparency planning inventory')
        docs = {}
        # Only plan attachments within the two POM sections, excluding site navigation.
        for a in pom.select('#modulo-pom a[href], #modulo-enlace-archivos a[href]'):
            url = urljoin(POM, a['href'])
            if urlparse(url).path.lower().endswith('.pdf'):
                if urlparse(url).hostname != 'aytocabanillas.org':
                    raise ValueError('Unexpected POM attachment host')
                docs[url] = {'titulo': _text(a), 'url': url, 'source_url': POM,
                             'tipo': 'documentacion_pom', 'fecha_publicacion': None}
        if not docs:
            raise ValueError('No actual POM documents found')
        announcements = 0
        for a in content.select('a[href]'):
            url = urljoin(TRANSPARENCY, a['href'])
            if '/preview-document/' not in urlparse(url).path:
                continue
            title = _text(a)
            if ('Texto Refundido' not in title or 'POM' not in title or
                    urlparse(url).hostname != 'cabanillasdelcampo.sedelectronica.es'):
                raise ValueError('Unclassified root document; review grouping before extraction')
            docs[url] = {'titulo': title, 'url': url, 'source_url': TRANSPARENCY,
                         'tipo': 'anuncio_texto_refundido', 'fecha_publicacion': _publication(title)}
            announcements += 1
        if not announcements:
            raise ValueError('No current POM consolidated-text announcements found')
        return [{
            'id': 'cabanillas-del-campo-pom', 'municipio': 'Cabanillas del Campo',
            'provincia': 'Guadalajara', 'codigo_ine': '19058',
            'titulo': 'Plan de Ordenación Municipal de Cabanillas del Campo (POM)',
            'tipo': 'planeamiento_urbanistico', 'url': POM, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_pom', 'source_urls': [POM, TRANSPARENCY],
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'documentos': list(docs.values()),
            'descripcion': 'Instrumento agrupado: planos y memoria del índice municipal y anuncios del texto refundido de sus normas urbanísticas. Fechas de publicación conservadas por documento.',
            'coverage': 'partial', 'limitations': LIMITATIONS,
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False,
        }]

    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-cabanillas-del-campo/1.0 (public planning inventory)'})
        response.raise_for_status()
        if response.url.rstrip('/') != url.rstrip('/'):
            raise ValueError('Unexpected inventory redirect: ' + response.url)
        response.encoding = 'utf-8'
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = self.parse_projects(self._fetch(POM), self._fetch(TRANSPARENCY))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [POM, TRANSPARENCY],
                'limitations': LIMITATIONS, 'coverage': 'partial'}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh of the two finite document indices; no date-based filtering.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
