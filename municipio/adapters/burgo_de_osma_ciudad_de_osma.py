"""Municipal PRTR physical-work inventory; not a licence or procurement feed."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.burgodeosma.com/'
SOURCE = BASE + 'plan-de-recuperacion-transformacion-y-resiliencia/'
WORKS = {
    BASE + 'reforma-de-las-instalaciones-de-alumbrado-publico/': (
        'Reforma de las instalaciones de alumbrado público',
        'renovación de las instalaciones de alumbrado exterior',
    ),
    BASE + 'instalacion-de-generacion-electrica-renovable-para-el-autoconsumo/': (
        'Instalación de generación eléctrica renovable para autoconsumo',
        '6 instalaciones solares fotovoltaicas',
    ),
}
EXCLUDED = {BASE + 'vehiculo-electrico/', BASE + 'accesibilidad-mrr/'}


def _body(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('[data-elementor-type="wp-page"]')
    if body is None:
        raise ValueError('Missing municipal project content (changed markup or error page)')
    if soup.select('a[rel~=next], .page-numbers, .pagination, .nav-links'):
        raise ValueError('Pagination detected: review crawler before returning partial inventory')
    return body


def parse_inventory(html: str) -> list[str]:
    body = _body(html)
    text = body.get_text(' ', strip=True)
    if 'Actuaciones llevadas a cabo por el ayuntamiento' not in text:
        raise ValueError('Missing PRTR municipal works inventory')
    links = set()
    for a in body.select('a[href]'):
        label = a.get_text(' ', strip=True)
        if label == 'Ver actuación' or label == 'ACCESIBILIDAD (MRR)':
            links.add(urljoin(SOURCE, a['href']))
    unknown = links - set(WORKS) - EXCLUDED
    if unknown or not set(WORKS).issubset(links):
        raise ValueError(f'Changed project inventory; review all links: {sorted(links)}')
    return sorted(links & set(WORKS))


def parse_project(html: str, url: str) -> dict[str, Any]:
    title, description_marker = WORKS[url]
    body = _body(html)
    text = body.get_text(' ', strip=True)
    # Require the physical project narrative, not just a title or a tender link.
    for marker in ('OBJETO DEL PROYECTO', 'PROYECTO SUBVENCIONADO',
                   'El Burgo de Osma', description_marker):
        if marker.casefold() not in text.casefold():
            raise ValueError(f'Missing project narrative: {marker}')
    docs = {}
    references = {}
    for a in body.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        label = a.get_text(' ', strip=True) or target
        if parsed.hostname == 'www.burgodeosma.com' and parsed.path.lower().endswith('.pdf'):
            docs[target] = {'titulo': label, 'url': target, 'procedencia': url}
        elif parsed.hostname == 'contrataciondelestado.es':
            references[target] = {'titulo': label, 'url': target, 'procedencia': url}
    return {
        'id': 'burgo-de-osma-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Burgo de Osma-Ciudad de Osma', 'provincia': 'Soria',
        'codigo_ine': '42043', 'titulo': title, 'tipo': 'obra_publica',
        'fase': None, 'fecha': None, 'fecha_publicacion': None,
        'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_prtr',
        'url_inventario': SOURCE, 'descripcion': text,
        'documentos': list(docs.values()), 'referencias_contratacion': list(references.values()),
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'Sin geometría de proyecto verificada',
        'cobertura': 'Obras físicas del inventario municipal PRTR; no inventario completo de obras o planeamiento',
    }


class BurgoDeOsmaCiudadDeOsmaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, session, url):
        response = session.get(url, timeout=40, headers={
            'User-Agent': 'municipio-burgo-de-osma/1.0 (public municipal works research)'})
        response.raise_for_status()
        if urlparse(response.url).hostname != 'www.burgodeosma.com':
            raise ValueError('Unexpected source redirect')
        response.encoding = 'utf-8'
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = 'inventory' if url == SOURCE else urlparse(url).path.strip('/')
            (directory / (name + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            urls = parse_inventory(self._fetch(session, SOURCE))
            rows = [parse_project(self._fetch(session, url), url) for url in urls]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, *urls],
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot of the finite curated inventory; no date cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No granted licence register verified'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
