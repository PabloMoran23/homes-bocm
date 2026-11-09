"""Torrejón del Rey PAUs in the official JCCM register, not a licence register."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://urbanismo.castillalamancha.es'
SOURCE = ROOT + '/registros/pau-gu'
NAME = 'Torrejón del Rey'
LIMITATIONS = [
    'Cobertura parcial: solo PAU inscritos en el registro autonómico de Guadalajara; no inventario municipal completo.',
    'Las fichas registrales no acreditan vigencia, ejecución de obras ni concesión de licencias.',
    'Fecha de aprobación tomada de la ficha, sin inferir aprobación definitiva; publicación DOCM puede corresponder a otro trámite.',
    'Observaciones conservadas literalmente; sus fechas no se convierten en fechas de acuerdo o publicación del instrumento.',
    'Sin geometrías verificadas. El inventario consultado ofrece fichas, no necesariamente documentos técnicos descargables.',
]


def _text(node):
    return node.get_text(' ', strip=True) if node else ''


def municipality_filter(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    options = [o.get('value') for o in soup.select('select[name="municipio"] option')
               if _text(o).lstrip('-').strip() == NAME]
    if len(options) != 1 or not options[0]:
        raise ValueError('Municipality filter not found or ambiguous')
    return str(options[0])


def parse_inventory(html: str, page_url: str) -> tuple[list[str], list[str]]:
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.views-table')
    if table is None:
        raise ValueError('PAU inventory table missing')
    urls = []
    for row in table.select('tbody tr'):
        if _text(row.select_one('td.views-field-municipios-clm')) != NAME:
            raise ValueError('Unexpected municipality in filtered inventory')
        anchor = row.select_one('td.views-field-title a[href]')
        if anchor is None or 'P.A.U.' not in _text(anchor):
            raise ValueError('Missing PAU record link/title')
        url = urljoin(page_url, anchor['href'])
        if urlsplit(url).netloc != urlsplit(ROOT).netloc or not urlsplit(url).path.startswith('/registros/pau/'):
            raise ValueError('Unexpected PAU detail URL')
        urls.append(url)
    if not urls:
        raise ValueError('Empty PAU inventory')
    pages = []
    for anchor in soup.select('.pager a[href], a[rel~="next"]'):
        url = urljoin(page_url, anchor['href'])
        parts = urlsplit(url)
        if (parts.netloc != urlsplit(SOURCE).netloc or parts.path != urlsplit(SOURCE).path
                or parse_qs(parts.query).get('municipio') != parse_qs(urlsplit(page_url).query).get('municipio')):
            raise ValueError('Pagination escaped municipality filter')
        pages.append(url)
    return list(dict.fromkeys(urls)), list(dict.fromkeys(pages))


def parse_project(html: str, url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.node--type-programa-actuacion-urbanizadora')
    if article is None:
        raise ValueError('PAU detail article missing')
    municipalities = [_text(li) for li in article.select('.field--name-municipios-clm li')]
    if municipalities != ['GUADALAJARA', NAME]:
        raise ValueError('PAU detail municipality/province mismatch')
    title = _text(article.select_one('.field--name-title'))
    if 'P.A.U.' not in title:
        raise ValueError('Not an identifiable PAU instrument')

    def field(name):
        return article.select_one('.field--name-' + name + ' .field__item')

    def field_date(name):
        node = field(name)
        if node is None:
            return None
        time = node.select_one('time[datetime]')
        if time is None:
            raise ValueError('Date field without machine-readable date: ' + name)
        return date.fromisoformat(time['datetime'][:10]).isoformat()

    inscription = _text(field('field-datos-inscripcion'))
    if not inscription:
        raise ValueError('PAU registration provenance missing')
    documents = [{'titulo': title, 'url': url, 'tipo': 'ficha_registral'}]
    for a in article.select('a[href]'):
        link = urljoin(url, a['href'])
        if urlsplit(link).scheme in ('http', 'https') and link not in {d['url'] for d in documents}:
            documents.append({'titulo': _text(a), 'url': link, 'tipo': 'enlace_de_la_ficha'})
    node_id = article.get('data-history-node-id')
    identity = node_id if node_id and node_id.isdigit() else hashlib.sha256(url.encode()).hexdigest()[:16]
    observations = _text(field('field-observaciones'))
    return {
        'id': 'torrejon-del-rey-proy-jccm-' + identity,
        'municipio': NAME, 'provincia': 'Guadalajara', 'codigo_ine': '19280',
        'titulo': title, 'tipo': 'Programa de Actuación Urbanizadora',
        'fase': None, 'fecha': None, 'fecha_acuerdo': None,
        'fecha_aprob': field_date('field-fecha-aprobacion'),
        'fecha_publicacion': field_date('field-publicacion-docm'),
        'fecha_publicacion_fuente': 'Publicación en el DOCM (campo de la ficha registral)',
        'agente_urbanizador': _text(field('field-agente-urbanizador')) or None,
        'uso': _text(field('field-uso')) or None,
        'datos_inscripcion': inscription, 'observaciones': observations or None,
        'descripcion': '\n'.join(x for x in [inscription, observations] if x),
        'url': url, 'url_documento': url, 'documentos': documents,
        'source': 'jccm_registro_pau', 'origen': 'registro_autonomico',
        'organismo_fuente': 'Junta de Comunidades de Castilla-La Mancha',
        'source_inventory': SOURCE,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'limitations': LIMITATIONS,
    }


class TorrejonDelReyAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)
        self.source_urls: list[str] = []

    def _fetch(self, session, url):
        with session.get(url, timeout=40, stream=True) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 5_000_000:
                    raise ValueError('Source exceeds response limit; refusing partial extraction')
                chunks.append(chunk)
            content = b''.join(chunks)
            if 'html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Expected HTML source')
            html = content.decode('utf-8-sig')
        self.source_urls.append(url)
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir'])
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(content)
        return html

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        self.source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-torrejon-del-rey/1.0'
            token = municipality_filter(self._fetch(session, SOURCE))
            pending = [SOURCE + '?' + urlencode({'municipio': token})]
            visited, detail_urls = set(), []
            while pending:
                url = pending.pop(0)
                if url in visited:
                    continue
                if len(visited) >= 100:
                    raise ValueError('Pagination safety limit reached; no partial output written')
                visited.add(url)
                links, pages = parse_inventory(self._fetch(session, url), url)
                detail_urls.extend(links)
                pending.extend(p for p in pages if p not in visited)
            rows = {}
            for url in dict.fromkeys(detail_urls):
                row = parse_project(self._fetch(session, url), url)
                if row['id'] in rows and rows[row['id']] != row:
                    raise ValueError('Conflicting duplicate PAU instrument')
                rows[row['id']] = row
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows.values()), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'inventory_pages': len(visited), 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Refresh the complete current register snapshot; no invented incremental dates.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
