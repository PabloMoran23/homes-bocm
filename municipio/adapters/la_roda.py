"""La Roda: municipal POM documents and the PAI's actual building projects."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://laroda.es'
POM = BASE + '/urbanismo/plan-de-ordenacion-municipal/'
PAI = BASE + '/urbanismo/plan-de-actuacion-integrado-de-la-roda/'
SOURCES = (POM, PAI)
LIMITATIONS = [
    'Partial coverage: only the municipal POM document page and PAI building projects; '
    'subsidiary planning rules/modifications and other works are outside this adapter.',
    'POM page retains consultation deadlines from 2021; current approval status is unverified.',
    'No granted-licence register, verified geometry, agreement, approval or publication dates extracted.',
    'Document links are inventoried, not all PDFs downloaded or their contents parsed.',
]


def _content(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    # These are complete, static inventories. Fail if pagination is introduced;
    # returning just the first page would misrepresent coverage.
    if soup.select('a[rel~=next], .page-links, .pagination, .nav-links'):
        raise ValueError('Source now has pagination; complete traversal must be implemented')
    content = soup.select_one('main article .entry-content')
    if content is None:
        raise ValueError('Missing municipal article content')
    return content


def _document(a, source: str, role: str = 'documento'):
    url = urljoin(source, a['href'])
    parts = urlsplit(url)
    if (parts.scheme not in ('http', 'https') or parts.hostname != 'laroda.es'
            or not parts.path.lower().endswith('.pdf')):
        return None
    return {'titulo': a.get_text(' ', strip=True), 'url': url,
            'source_url': source, 'role': role}


def _group_documents(documents):
    grouped = {}
    for doc in documents:
        if doc['url'] not in grouped:
            grouped[doc['url']] = {**doc, 'titulos_fuente': [doc['titulo']]}
        elif doc['titulo'] not in grouped[doc['url']]['titulos_fuente']:
            grouped[doc['url']]['titulos_fuente'].append(doc['titulo'])
    return list(grouped.values())


def _record(title, source, identity, kind, documents):
    return {
        'id': 'la-roda-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
        'municipio': 'La Roda', 'provincia': 'Albacete', 'codigo_ine': '02069',
        'titulo': title, 'tipo': kind, 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': source, 'source': 'ayuntamiento', 'origen': 'inventario_municipal',
        'documentos': _group_documents(documents),
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


def parse_pom(html: str) -> list[dict[str, Any]]:
    content = _content(html)
    if 'Plan de Ordenación Municipal de La Roda' not in content.get_text(' ', strip=True):
        raise ValueError('Missing La Roda POM identity')
    docs = []
    for a in content.select('a[href]'):
        doc = _document(a, POM)
        if doc and urlsplit(doc['url']).path.startswith('/pom/'):
            docs.append(doc)
    # A menu or an appointment form is insufficient evidence of an instrument.
    labels = ' '.join(d['titulo'].casefold() for d in docs)
    if not all(label in labels for label in ('memoria informativa', 'normas urbanísticas')):
        raise ValueError('POM no longer exposes its substantive document inventory')
    row = _record('Plan de Ordenación Municipal de La Roda', POM, POM,
                  'instrumento de planeamiento', docs)
    row['descripcion'] = 'Inventario documental municipal del POM; estado actual de aprobación no verificado.'
    row['estado_fuente'] = next((p.get_text(' ', strip=True) for p in content.select('p')
                                if 'actualmente en tramitación' in p.get_text()), None)
    row['limitaciones'] = LIMITATIONS
    return [row]


def parse_pai(html: str) -> list[dict[str, Any]]:
    content = _content(html)
    sections = []
    current = None
    for node in content.find_all(['h2', 'a']):
        if node.name == 'h2':
            current = {'title': node.get_text(' ', strip=True), 'docs': [], 'links': []}
            sections.append(current)
        elif current is not None and node.has_attr('href'):
            doc = _document(node, PAI)
            if doc:
                current['docs'].append(doc)
            elif urlsplit(urljoin(PAI, node['href'])).hostname == 'contrataciondelestado.es':
                current['links'].append({'titulo': node.get_text(' ', strip=True),
                                         'url': urljoin(PAI, node['href']),
                                         'role': 'licitacion_contexto'})
    rows = []
    for section in sections:
        # Funding resolutions and general PAI material do not create works.
        project_docs = [d for d in section['docs']
                        if d['titulo'].casefold().startswith('proyecto básico y de ejecución')]
        if not project_docs:
            if section['title'].startswith('Centro '):
                raise ValueError('Building section without a substantive project document')
            continue
        # Identity uses the named instrument, not a document version/upload date.
        row = _record(section['title'], PAI, PAI + '#' + section['title'].casefold(),
                      'proyecto de obra pública', section['docs'])
        row['enlaces_relacionados'] = section['links']
        row['descripcion'] = 'Proyecto básico y de ejecución publicado en el inventario municipal del PAI.'
        row['limitaciones'] = LIMITATIONS
        rows.append(row)
    if not rows:
        raise ValueError('No substantive building projects in PAI inventory')
    return rows


class LaRodaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'}) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname != 'laroda.es':
                raise ValueError('Unexpected inventory redirect')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Inventory response is not HTML')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 2_000_000:
                    raise ValueError('Inventory exceeds response size limit')
            html = body.decode('utf-8')
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / ('live-pom.html' if url == POM else 'live-pai.html')).write_bytes(body)
        return html

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = parse_pom(self._fetch(POM)) + parse_pai(self._fetch(PAI))
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES),
                'coverage': 'complete snapshots of two scoped static inventories',
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # No incremental cursor: each update refreshes both complete inventories.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
