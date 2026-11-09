"""Reviewed physical projects in the official, paginated municipal inventory.

The inventory mixes legacy works with social programmes. New unreviewed entries
fail explicitly so that a changed inventory cannot silently lose real projects.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.altsasu.net'
INVENTORY_PATH = '/ayuntamiento/proyectos-y-acciones-municipales/'
SOURCE = BASE + INVENTORY_PATH

# Classification of the discovered inventory, never record payloads. Each record
# still requires a live detail page with the stated physical/planning narrative.
PROJECTS = {
    'actuaciones-en-el-entorno-de-dantzaleku':
        ('obra_publica', 'Proyecto Acondicionamiento Balsa Siets'),
    'plan-de-movilidad': ('plan_movilidad', 'Elaboración Plan de Movilidad'),
    'proyecto-de-ahorro-de-energia-en-el-alumbrado-publico':
        ('obra_publica', 'equipos reductores estabilizadores de cabecera de línea'),
    'piscina-cubierta-en-zelandi':
        ('obra_publica', 'Construcción de una piscina cubierta en el polideportivo Zelandi'),
    'nueva-escuela-de-musica':
        ('obra_publica', 'Proyecto de reforma del antiguo convento de La Compasión'),
}
EXCLUDED = {
    'dantzalku-usolarrian-y-basoitxi-como-area-natural-recreativa': 'Propuesta de declaración de espacio natural, sin obra concreta ni plan urbanístico',
    'mejoras-en-espacios-ajardinados-y-abiertos': 'Contratación de asesoramiento, sin proyecto físico definido',
    'ahorro-y-eficiencia-de-energia': 'Campaña informativa',
    'ordenanza-del-alumbrado-exterior-para-la-proteccion-del-medioambiente': 'Ordenanza general',
    'apuesta-energetica': 'Compromiso de campaña; alude al proyecto de alumbrado ya agrupado',
    'talleres-sobre-coeducacion-a-traves-de-la-expresion-dramatica': 'Talleres educativos',
    'campana-elecciones-profesionales': 'Campaña educativa',
    'agenda-21': 'Estrategia general de sostenibilidad; fuera del alcance físico/urbanístico',
    'igualdad-de-oportunidades-de-mujeres-y-hombres-en-altsasu-i-plan-de-actuacion-municipal-a-medio-plazo-2008-2011': 'Plan social de igualdad',
    'proyectosprogramas-municipales-incorporando-perspectiva-de-genero': 'Programa de perspectiva de género',
    'ii-pacto-por-la-conciliacion-alsasua': 'Pacto social',
    'actividades-de-conciliacion-del-programa-pactos-locales-por-la-conciliacion': 'Actividades de conciliación',
}


def _official(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'www.altsasu.net'
            or parsed.username or parsed.password):
        raise ValueError(f'Unexpected non-municipal URL: {url}')
    return url


def _page_url(href):
    """Normalize WP links that combine /page/N/ and a differing ?paged=M."""
    url = _official(urljoin(SOURCE, href))
    parsed = urlsplit(url)
    suffix = parsed.path.removeprefix(INVENTORY_PATH)
    if not parsed.path.startswith(INVENTORY_PATH):
        raise ValueError(f'Pagination escaped inventory: {url}')
    query = parse_qs(parsed.query)
    if suffix and not (suffix.startswith('page/') and suffix[5:].strip('/').isdigit()):
        raise ValueError(f'Unknown pagination path: {url}')
    value = query.get('paged', [suffix[5:].strip('/') if suffix else '1'])
    if len(value) != 1 or not value[0].isdigit() or int(value[0]) < 1:
        raise ValueError(f'Invalid pagination: {url}')
    page = int(value[0])
    return SOURCE if page == 1 else SOURCE + f'?paged={page}'


class AltsasuAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='altsasu', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        _official(url)
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-altsasu/1.0 (public municipal inventory)',
        })
        response.raise_for_status()
        _official(response.url)
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError(f'Expected HTML: {url}')
        if len(response.content) > 5_000_000:
            raise ValueError('Source exceeds reviewed HTML size; no partial parse')
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (hashlib.sha256(url.encode()).hexdigest()[:20] + '.html')).write_bytes(response.content)
        return response.text

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.select_one('main h2.titulo-listado')
        if not heading or heading.get_text(' ', strip=True) != 'Proyectos y acciones municipales':
            raise ValueError('Municipal project inventory missing or changed')
        entries = {}
        for article in soup.select('main article.entrada'):
            a = article.select_one('.list-title a[href]')
            if not a or not a.get_text(' ', strip=True):
                raise ValueError('Inventory entry lacks a title/link')
            url = _official(urljoin(SOURCE, a['href']))
            if urlsplit(url).query or urlsplit(url).fragment:
                raise ValueError('Unexpected detail identifier')
            entries[url] = a.get_text(' ', strip=True)
        if not entries:
            raise ValueError('Empty inventory; review before replacing snapshot')
        pages = {_page_url(a['href']) for a in soup.select('#paginacion a[href], a.page-numbers[href]')}
        # Detect alternate next links rather than silently ignoring new markup.
        for a in soup.select('main a[href]'):
            if ('next' in a.get('rel', []) or a.get_text(strip=True).lower().startswith('siguiente')):
                pages.add(_page_url(a['href']))
        return entries, pages

    @staticmethod
    def parse_project(html, url, inventory_title):
        slug = urlsplit(url).path.strip('/')
        if slug not in PROJECTS:
            raise ValueError('Unreviewed project')
        kind, required = PROJECTS[slug]
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.select_one('main h2.titulo-single')
        category = soup.select_one('main .categoria_gene')
        body = soup.select_one('main .contenido.content > .mt-3')
        if (not heading or heading.get_text(' ', strip=True) != inventory_title
                or not category or 'Proyectos y acciones municipales' not in category.get_text()
                or not body):
            raise ValueError(f'Detail page missing or changed: {url}')
        description = body.get_text(' ', strip=True)
        if required.casefold() not in description.casefold():
            raise ValueError(f'Physical/planning narrative no longer verified: {url}')
        documents = {}
        for a in body.select('a[href]'):
            doc = urljoin(url, a['href'])
            if urlsplit(doc).path.lower().endswith('.pdf'):
                _official(doc)
                documents.setdefault(doc, {'titulo': a.get_text(' ', strip=True), 'url': doc,
                                           'source_url': url})
        return {
            'id': 'altsasu-proy-' + slug,
            'municipio': 'Altsasu / Alsasua', 'codigo_ine': '31010', 'provincia': 'Navarra',
            'titulo': heading.get_text(' ', strip=True), 'tipo': kind,
            'descripcion': description, 'url': url, 'source': 'ayuntamiento',
            'origen': 'inventario_proyectos_y_acciones_municipales',
            'source_urls': [SOURCE, url], 'documentos': list(documents.values()),
            # No visible publication/agreement dates for these legacy entries.
            # WP migration metadata and document upload paths are not dates of approval.
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'fase': None, 'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'coverage_note': 'Ficha histórica accesible; no acredita vigencia, adjudicación ni ejecución actual.',
        }

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pending, visited, entries, signatures = {SOURCE}, set(), {}, set()
        while pending:
            url = min(pending)
            pending.remove(url)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Inventory exceeds safety limit; refusing truncated output')
            found, pages = self.parse_inventory(self._fetch(url))
            signature = tuple(sorted(found))
            if signature in signatures:
                raise ValueError('Pagination repeats a page; refusing incomplete inventory')
            signatures.add(signature)
            visited.add(url)
            for detail_url, title in found.items():
                if detail_url in entries and entries[detail_url] != title:
                    raise ValueError('Conflicting inventory titles')
                entries[detail_url] = title
            pending.update(pages - visited)
        rows, excluded = [], []
        for url, title in sorted(entries.items()):
            slug = urlsplit(url).path.strip('/')
            if slug in EXCLUDED:
                excluded.append({'url': url, 'reason': EXCLUDED[slug]})
            elif slug in PROJECTS:
                row = self.parse_project(self._fetch(url), url, title)
                row['source_urls'] = sorted(visited) + [url]
                rows.append(row)
            else:
                raise ValueError(f'New inventory entry needs semantic review: {url}')
        if not rows:
            raise ValueError('No verified physical/planning projects in inventory')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_entries': len(entries),
                'inventory_pages': sorted(visited), 'excluded': excluded,
                'source_urls': sorted(visited | {r['url'] for r in rows}),
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh; no invented incremental date cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified licence grants register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
