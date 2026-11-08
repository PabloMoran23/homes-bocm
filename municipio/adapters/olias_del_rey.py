"""Municipal NNSS document inventory; one instrument, no inferred legal status."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.ayuntamientodeoliasdelrey.com/urbanismo/'
TITLE = 'REVISIÓN DE LAS NORMAS SUBSIDIARIAS DE OLÍAS DEL REY (TOLEDO)'
LIMITATIONS = [
    'Cobertura parcial: solo la revisión de NNSS publicada en Urbanismo; no es un histórico completo.',
    'Sin fechas de publicación, acuerdo o aprobación verificadas; la carpeta uploads no es una fecha administrativa.',
    'Sin vigencia ni fase jurídica verificadas, sin geometría; el plano enlazado no se georreferencia.',
    'El portal de transparencia enlazado no se recorre; formularios, ordenanzas y noticias quedan excluidos.',
]


def _norm(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD', text)
                            if not unicodedata.combining(c)).casefold().split())


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('a[rel~=next], .pagination a[href], a.page-numbers[href], link[rel~=next]'):
        raise ValueError('Pagination detected: inventory coverage needs review')
    headings = [h for h in soup.select('h1,h2,h3,h4,h5,h6')
                if _norm(h.get_text(' ', strip=True)) == _norm(TITLE)]
    if not headings:
        raise ValueError('Named municipal NNSS inventory missing')
    documents = {}
    reference_sets = []
    related = set()
    for heading in headings:
        listing = heading.find_next_sibling()
        if listing is None or listing.name != 'ol':
            raise ValueError('NNSS document list missing or changed')
        current = set()
        for a in listing.select('a[href]'):
            title = a.get_text(' ', strip=True)
            url = urljoin(source_url, a['href'])
            parsed = urlparse(url)
            if (parsed.scheme != 'https' or parsed.hostname != urlparse(SOURCE).hostname
                    or not parsed.path.startswith('/wp-content/uploads/')
                    or not parsed.path.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png'))
                    or not title):
                raise ValueError('Unexpected NNSS document link')
            current.add(url)
            documents[url] = {'titulo': title, 'url': url, 'source_url': source_url}
        labels = _norm(' '.join(documents[u]['titulo'] for u in current))
        if not all(word in labels for word in ('definiciones', 'fichas', 'memoria', 'normas urbanisticas', 'plano')):
            raise ValueError('Incomplete NNSS package: required components missing')
        reference_sets.append(current)
        for a in heading.parent.select('a[href]'):
            url = urljoin(source_url, a['href'])
            if (urlparse(url).scheme == 'https'
                    and urlparse(url).hostname == 'oliasdelrey.sedelectronica.es'
                    and urlparse(url).path.startswith('/transparency/')):
                related.add(url)
    # Desktop/mobile copies must agree, rather than silently merging drift.
    if any(urls != reference_sets[0] for urls in reference_sets[1:]):
        raise ValueError('Conflicting duplicate NNSS inventory blocks')
    return [{
        'id': 'olias-del-rey-planeamiento-revision-nnss',
        'municipio': 'Olías del Rey', 'provincia': 'Toledo', 'codigo_ine': '45122',
        'titulo': headings[0].get_text(' ', strip=True),
        'tipo': 'revisión de normas subsidiarias',
        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
        'url': source_url, 'inventory_url': source_url,
        'documentos': [documents[u] for u in sorted(documents)],
        'enlaces_relacionados': sorted(related),
        'descripcion': 'Instrumento publicado en el apartado Normas Subsidiarias de Urbanismo; documentos agrupados según el inventario municipal.',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'fase': None,
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
        'limitaciones': LIMITATIONS,
    }]


class OliasDelReyAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'municipio-olias-del-rey/1.0 (public planning inventory)'})
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE.rstrip('/'):
            raise ValueError('Unexpected municipal inventory redirect')
        rows = parse_inventory(response.text, SOURCE)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'rows': len(rows),
                'source_urls': [SOURCE], 'coverage': 'partial_current_nnss_inventory',
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh of this unpaginated document package; no date-based cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0,
                'reason': 'No verified public register of granted licences; application forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
