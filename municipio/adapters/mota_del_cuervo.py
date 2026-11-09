"""Mota del Cuervo PAUs from the official Castilla-La Mancha public register."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://urbanismo.castillalamancha.es/registros/pau-cu'
HOST = urlparse(SOURCE).hostname
LIMITATIONS = [
    'Cobertura parcial: registro regional de PAUs de Cuenca, filtrado por municipio exacto; no inventario completo de planeamiento u obras.',
    'El listado etiqueta la fecha como constitución; fecha_aprob procede exclusivamente del campo Fecha de aprobación de la ficha.',
    'Sin fechas de publicación/acuerdo, vigencia o ejecución verificadas; sin geometría ni coordenadas.',
    'La ficha observada no enlaza documentos adjuntos; se conserva su URL y cualquier adjunto que aparezca dentro del artículo.',
    'Licencias desactivadas. La web municipal devolvió HTTP 500 por falta del framework Gantry durante la investigación.',
]


def text(element):
    return element.get_text(' ', strip=True) if element else ''


def checked_url(value, base=SOURCE, detail=False):
    url = urljoin(base, value)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != HOST:
        raise ValueError('Unexpected regional register URL: ' + url)
    if detail and not parsed.path.startswith('/registros/pau/'):
        raise ValueError('Unexpected PAU detail path: ' + url)
    return url


def parse_inventory(html, url=SOURCE):
    """Read every table row; retain pagination rather than imposing a row limit."""
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.views-table')
    if table is None:
        raise ValueError('PAU inventory table missing')
    headers = [text(h) for h in table.select('thead th')]
    if headers != ['Denominación', 'Municipio', 'Fecha de constitución']:
        raise ValueError('PAU inventory columns changed')
    entries = []
    for row in table.select('tbody tr'):
        cells = row.find_all('td', recursive=False)
        if len(cells) != 3:
            raise ValueError('Malformed PAU inventory row')
        if text(cells[1]) != 'Mota del Cuervo':
            continue
        a = cells[0].select_one('a[href]')
        if not a or not text(a):
            raise ValueError('Municipal PAU lacks detail link/title')
        entries.append({'titulo': text(a), 'url': checked_url(a['href'], url, detail=True),
                        'fecha_listado_original': text(cells[2]), 'inventory_url': url})
    pages = set()
    for a in soup.select('.pager a[href], a[rel~=next]'):
        target = checked_url(a['href'], url)
        if urlparse(target).path != urlparse(SOURCE).path:
            raise ValueError('Unexpected pagination path')
        pages.add(target.split('#')[0])
    return entries, sorted(pages)


def parse_detail(html, entry):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('main article.node--type-programa-actuacion-urbanizadora')
    if article is None:
        raise ValueError('PAU detail article missing')
    title = text(article.select_one('h1'))
    places = [text(x) for x in article.select('.field--name-municipios-clm li')]
    if title != entry['titulo'] or places != ['CUENCA', 'Mota del Cuervo']:
        raise ValueError('PAU detail identity/municipality mismatch')
    approval = None
    field = article.select_one('.field--name-field-fecha-aprobacion')
    if field:
        if text(field.select_one('.field__label')) != 'Fecha de aprobación':
            raise ValueError('Approval date label changed')
        timestamp = field.select_one('time[datetime]')
        if timestamp is None:
            raise ValueError('Approval field lacks machine-readable date')
        approval = date.fromisoformat(timestamp['datetime'][:10]).isoformat()
    documents = {}
    for a in article.select('a[href]'):
        target = urljoin(entry['url'], a['href'])
        if urlparse(target).scheme == 'https' and (
            '/sites/default/files/' in urlparse(target).path
            or urlparse(target).path.lower().endswith(('.pdf', '.zip'))
        ):
            documents.setdefault(target, {'titulo': text(a), 'url': target})
    registration = text(article.select_one('.field--name-field-datos-inscripcion .field__item'))
    return {
        'id': 'mota-del-cuervo-pau-' + hashlib.sha256(entry['url'].encode()).hexdigest()[:16],
        'municipio': 'Mota del Cuervo', 'provincia': 'Cuenca', 'codigo_ine': '16133',
        'titulo': title, 'tipo': 'programa_actuacion_urbanizadora',
        'url': entry['url'], 'inventory_url': entry['inventory_url'],
        'source': 'jccm', 'organismo_fuente': 'Junta de Comunidades de Castilla-La Mancha',
        'origen': 'registro_regional_pau_cuenca',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': approval,
        'fecha_aprob_fuente': 'Ficha: Fecha de aprobación' if approval else None,
        'fecha_listado_original': entry['fecha_listado_original'],
        'fecha_listado_etiqueta': 'Fecha de constitución',
        'datos_inscripcion_original': registration or None,
        'agente_urbanizador': text(article.select_one('.field--name-field-agente-urbanizador .field__item')) or None,
        'uso_original': text(article.select_one('.field--name-field-uso .field__item')) or None,
        'documentos': list(documents.values()),
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'registro_regional_pau_parcial',
    }


class MotaDelCuervoAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        checked_url(url)
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-mota-del-cuervo/1.0 (public planning register)',
        })
        response.raise_for_status()
        checked_url(response.url)
        if urlparse(response.url).path != urlparse(url).path:
            raise ValueError('Register redirected to a different page')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected HTML register page')
        capture = self.config.get('capture_dir')
        if capture:
            folder = Path(capture)
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (folder / name).write_bytes(response.content)
        self.source_urls.append(url)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        pending, visited, entries = [SOURCE], set(), {}
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 200:
                raise ValueError('Pagination safety bound reached; no partial snapshot written')
            visited.add(url)
            found, pages = parse_inventory(self._fetch(url), url)
            for entry in found:
                previous = entries.get(entry['url'])
                if previous and previous['titulo'] != entry['titulo']:
                    raise ValueError('Conflicting titles for one PAU')
                entries.setdefault(entry['url'], entry)
            pending.extend(p for p in pages if p not in visited)
        if not entries:
            raise ValueError('No verified Mota del Cuervo PAUs in register')
        rows = [parse_detail(self._fetch(url), entry) for url, entry in sorted(entries.items())]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'inventory_pages': len(visited), 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current register snapshot; no guessed incremental watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
