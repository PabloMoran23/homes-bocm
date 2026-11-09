"""Partial official POM document inventory for Casas-Ibáñez (INE 02024)."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://casasibanez.es'
NORMATIVA = BASE + '/normativa-municipal/'
INSTANCIAS = BASE + '/instancias/'
PLAN_LABEL = 'Texto consolidado de las Normas Urbanísticas del Plan de Ordenación Municipal'
MAP_LABEL = 'Plano del Municipio. Plano de SU y SUB. Calificación y alturas'
LIMITATIONS = [
    'Partial POM inventory from Normativa Municipal and Instancias; not a municipal project history.',
    'Informational documents do not establish the complete legally effective planning instrument.',
    'No approval/agreement/publication dates verified; PDF edition and upload dates are not approval dates.',
    'No verified vector geometry or coordinates; the linked map is retained as a document.',
    'Announcement board, plenary minutes, procurement and granted licences are outside this extraction.',
]


def _norm(text: str) -> str:
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    return ' '.join(text.lower().split())


def _page(html: str, heading: str):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None or not any(_norm(h.get_text(' ', strip=True)) == _norm(heading)
                               for h in main.select('h1')):
        raise ValueError(f'Missing official inventory heading: {heading}')
    # These inventories are single static pages. Fail if a paged inventory
    # replaces them, rather than quietly returning its first page.
    if main.select('.pagination, .nav-links, .page-links, [aria-label*="agin"], a[rel~="next"]'):
        raise ValueError('Unexpected inventory pagination; traversal must be reviewed')
    return main


def _document(anchor, inventory: str, role: str) -> dict[str, str]:
    linked = urljoin(inventory, anchor['href'])
    parsed = urlsplit(linked)
    if (parsed.scheme not in ('http', 'https') or parsed.netloc != 'casasibanez.es'
            or not parsed.path.startswith('/wp-content/uploads/')
            or not parsed.path.lower().endswith('.pdf') or parsed.query):
        raise ValueError(f'Unexpected municipal PDF URL: {linked}')
    # The norms inventory still links HTTP. Preserve that source value while
    # fetching the same path over HTTPS, verified live during research.
    target = urlunsplit(('https', parsed.netloc, parsed.path, '', ''))
    return {'titulo': anchor.get_text(' ', strip=True), 'url': target,
            'url_enlace_original': linked, 'inventory_url': inventory, 'rol': role}


def parse_projects(normativa_html: str, instancias_html: str) -> list[dict[str, Any]]:
    normative = _page(normativa_html, 'Normativa Municipal')
    instances = _page(instancias_html, 'Instancias')
    documents: dict[str, dict[str, str]] = {}
    groups = []
    for label in normative.select('li > strong'):
        if _norm(label.get_text(' ', strip=True)) == _norm(PLAN_LABEL):
            groups.append(label.parent)
    if len(groups) != 1:
        raise ValueError('Expected one identifiable consolidated POM document group')
    for anchor in groups[0].select('a[href]'):
        document = _document(anchor, NORMATIVA, 'normas_urbanisticas_consolidadas')
        documents[document['url']] = document
    if not documents:
        raise ValueError('POM group has no documents')
    maps = [a for a in instances.select('a[href]')
            if _norm(a.get_text(' ', strip=True)) == _norm(MAP_LABEL)]
    if not maps:
        raise ValueError('Missing verified POM classification map link')
    for anchor in maps:
        document = _document(anchor, INSTANCIAS, 'plano_clasificacion_calificacion_alturas')
        documents[document['url']] = document
    return [{
        'id': 'casas-ibanez-pom', 'municipio': 'Casas-Ibáñez',
        'codigo_ine': '02024', 'provincia': 'Albacete',
        'titulo': 'Plan de Ordenación Municipal de Casas-Ibáñez (documentación informativa)',
        'tipo': 'Plan de Ordenación Municipal', 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': NORMATIVA, 'url_documento': next(iter(documents)),
        'source_urls': [NORMATIVA, INSTANCIAS], 'documentos': list(documents.values()),
        'source': 'ayuntamiento', 'origen': 'inventario_documental_pom',
        'descripcion': PLAN_LABEL + '; ' + MAP_LABEL + '.',
        'coverage': 'partial_pom_document_inventory', 'limitations': list(LIMITATIONS),
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }]


class CasasIbanezAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug: str, config=None, base_url: str = ''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url: str, *, pdf: bool = False) -> bytes:
        limit = 10_000_000 if pdf else 3_000_000
        with requests.get(url, timeout=(15, 40), stream=True, headers={
            'User-Agent': 'municipio-casas-ibanez/1.0 (public planning inventory)',
        }) as response:
            response.raise_for_status()
            if response.url != url:
                raise ValueError(f'Unexpected source redirect: {response.url}')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > limit:
                    raise ValueError(f'Source exceeds response size limit: {url}')
            data = bytes(content)
            if pdf and not data.startswith(b'%PDF-'):
                raise ValueError(f'Document response is not a PDF: {url}')
            if not pdf and 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError(f'Inventory response is not HTML: {url}')
            return data

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        captures = {'normativa.html': self._fetch(NORMATIVA),
                    'instancias.html': self._fetch(INSTANCIAS)}
        rows = parse_projects(captures['normativa.html'].decode('utf-8'),
                              captures['instancias.html'].decode('utf-8'))
        sources = [NORMATIVA, INSTANCIAS]
        for index, document in enumerate(rows[0]['documentos'], 1):
            captures[f'documento-{index}.pdf'] = self._fetch(document['url'], pdf=True)
            sources.append(document['url'])
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            for name, data in captures.items():
                (folder / name).write_bytes(data)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources,
                'coverage': 'partial_pom_document_inventory',
                'limitations': list(LIMITATIONS), 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Full refresh of both unpaginated inventories; no date watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0,
                'reason': 'No verified granted-licence register; forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
