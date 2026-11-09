"""Document inventories published by Hornachuelos; no licence or approval inference."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://hornachuelos.es'
SOURCES = (
    {'key': 'pgou', 'url': BASE + '/ayuntamiento/urbanismo/pgou/',
     'heading': r'^PLAN GENERAL DE ORDENACIÓN URBANÍSTICA .*HORNACHUELOS \(PGOU\)$',
     'prefix': '/wp-content/uploads/docs/PGOU/', 'tipo': 'planeamiento_urbanistico',
     'required': ('MEMORIA DE ORDENACIÓN', 'NORMATIVA URBANÍSTICA')},

)
LIMITATIONS = [
    'Cobertura parcial: el inventario documental del PGOU, no todos los expedientes u obras.',
    'No se acredita vigencia, concesión, ejecución ni aprobación del instrumento o proyecto.',
    'Sin fechas de publicación o acuerdo verificadas ni coordenadas; no se deducen de nombres o del CMS.',
    'Se conservan los enlaces publicados; no se verifica automáticamente cada archivo adjunto.',
    'Actualización por sustitución de la instantánea completa, sin histórico de bajas.',
]


def parse_inventory(html: str, spec: dict) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content-main')
    if content is None:
        raise ValueError('Missing municipal content container')
    # These are single-page document inventories. Fail on pagination instead of
    # accepting a silently incomplete snapshot after a portal redesign.
    if soup.select('link[rel="next"], a[rel~="next"]') or content.select(
        '.pagination, .page-links, .page-numbers, .nav-links'
    ):
        raise ValueError('Pagination detected; crawler review required')
    for a in content.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', 'más', 'ver más'}:
            raise ValueError('Continuation link detected; crawler review required')
    headings = [h.get_text(' ', strip=True) for h in content.select('h2, p strong')]
    titles = [h for h in headings if re.fullmatch(spec['heading'], h, re.I)]
    if len(set(titles)) != 1:
        raise ValueError('Missing or ambiguous named instrument')
    docs = {}
    for a in content.select('a[href]'):
        target = urljoin(spec['url'], a['href'])
        parts = urlsplit(target)
        if not re.search(r'\.(pdf|zip|rar)$', parts.path, re.I):
            if parts.path.startswith(spec['prefix']):
                raise ValueError('Unreviewed attachment format')
            continue
        if parts.scheme != 'https' or parts.netloc != 'hornachuelos.es' or not parts.path.startswith(spec['prefix']):
            raise ValueError('Unexpected attachment provenance')
        target = urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe='/%'), parts.query, ''))
        title = a.get_text(' ', strip=True)
        if not title:
            raise ValueError('Untitled source document')
        section = 'informacion' if '/informacion/' in parts.path else spec['key']
        docs.setdefault(target, {'titulo': title, 'url': target, 'seccion': section,
                                 'source_url': spec['url']})
    labels = ' '.join(d['titulo'] for d in docs.values())
    if not docs or not all(label.casefold() in labels.casefold() for label in spec['required']):
        raise ValueError('Missing substantive planning/project documents')
    return {
        'id': 'hornachuelos-' + spec['key'], 'municipio': 'Hornachuelos',
        'codigo_ine': '14036', 'provincia': 'Córdoba', 'titulo': titles[0],
        'tipo': spec['tipo'], 'url': spec['url'], 'inventory_url': spec['url'],
        'source': 'ayuntamiento', 'origen': 'inventario_documental_municipal',
        'documentos': list(docs.values()),
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'limitations': LIMITATIONS,
    }


class HornachuelosAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path):
        rows = []
        for spec in SOURCES:
            response = requests.get(spec['url'], timeout=45, headers={
                'User-Agent': 'municipio-hornachuelos/1.0 (public document inventory)'})
            response.raise_for_status()
            if response.url.rstrip('/') != spec['url'].rstrip('/'):
                raise ValueError('Unexpected inventory redirect')
            response.encoding = 'utf-8'
            row = parse_inventory(response.text, spec)
            if self.config.get('capture_dir'):
                capture = Path(self.config['capture_dir'])
                capture.mkdir(parents=True, exist_ok=True)
                (capture / (spec['key'] + '.html')).write_bytes(response.content)
            rows.append(row)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [s['url'] for s in SOURCES],
                'limitations': LIMITATIONS, 'coverage': 'current_pgou_document_inventory'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
