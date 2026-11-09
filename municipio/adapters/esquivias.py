"""Esquivias instruments in the public JCCM PAU register (partial coverage)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://urbanismo.castillalamancha.es/registros/pau-to'
HOST = urlparse(SOURCE).hostname
LIMITATIONS = [
    'Only Esquivias entries in the JCCM Toledo PAU register; not all municipal planning or works.',
    'No verified granted-licence inventory; licences disabled.',
    'No geometry or coordinates; publication_ready=false.',
    'Detail HTML is the source document; no attached technical PDFs exposed in the reviewed PAU ficha.',
    'Register presence does not establish current execution status or continuing validity.',
]


def official_url(url, prefix):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != HOST or not parsed.path.startswith(prefix):
        raise ValueError('Unexpected source URL: ' + url)
    return url


def municipality_filter(html):
    soup = BeautifulSoup(html, 'html.parser')
    options = [o['value'] for o in soup.select('select[name="municipio"] option[value]')
               if o.get_text(strip=True).lstrip('-').strip() == 'Esquivias']
    if len(options) != 1 or not options[0].isdigit():
        raise ValueError('Missing unambiguous Esquivias municipality filter')
    return options[0]


def parse_inventory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.views-table')
    if not table:
        raise ValueError('Missing PAU register table')
    if [th.get_text(' ', strip=True) for th in table.select('thead th')][:2] != ['Denominación', 'Municipio']:
        raise ValueError('Changed PAU register columns')
    entries = {}
    for tr in table.select('tbody tr'):
        cells = tr.select('td')
        if len(cells) != 3 or cells[1].get_text(strip=True) != 'Esquivias':
            raise ValueError('Invalid row or municipality filter not respected')
        a = cells[0].select_one('a[href]')
        if not a or not a.get_text(strip=True):
            raise ValueError('PAU row lacks a named detail link')
        target = official_url(urljoin(url, a['href']), '/registros/pau/')
        entries[target] = a.get_text(' ', strip=True)
    if not entries:
        raise ValueError('No actual Esquivias PAU entries')
    pages = set()
    for a in soup.select('.pager a[href], a[rel="next"]'):
        target = official_url(urljoin(url, a['href']), '/registros/pau-to')
        qs = parse_qs(urlparse(target).query)
        if qs.get('municipio') != parse_qs(urlparse(url).query).get('municipio'):
            raise ValueError('Pagination lost municipality filter')
        pages.add(target)
    return entries, pages


def parse_detail(html, url, expected_title):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.node--type-programa-actuacion-urbanizadora')
    if article is None:
        raise ValueError('Missing PAU detail article')
    heading = article.select_one('h1')
    if not heading or heading.get_text(' ', strip=True) != expected_title:
        raise ValueError('PAU detail title differs from inventory')
    municipalities = [li.get_text(strip=True) for li in article.select('.field--name-municipios-clm li')]
    if municipalities != ['TOLEDO', 'Esquivias']:
        raise ValueError('PAU detail is not Esquivias, Toledo')

    def field(name):
        el = article.select_one('.field--name-' + name + ' .field__item')
        return el.get_text(' ', strip=True) if el else None

    def dated(name):
        el = article.select_one('.field--name-' + name + ' time[datetime]')
        return date.fromisoformat(el['datetime'][:10]).isoformat() if el else None

    documents = {url: {'titulo': expected_title, 'url': url, 'tipo': 'ficha_registro_html'}}
    for a in article.select('a[href]'):
        target = urljoin(url, a['href'])
        if urlparse(target).path.lower().endswith('.pdf'):
            official_url(target, '/sites/default/files/')
            documents[target] = {'titulo': a.get_text(' ', strip=True), 'url': target, 'tipo': 'adjunto'}
    return {
        'id': 'esquivias-pau-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Esquivias', 'provincia': 'Toledo', 'codigo_ine': '45064',
        'titulo': expected_title, 'tipo': 'programa_actuacion_urbanizadora',
        'url': url, 'inventory_url': SOURCE, 'source': 'jccm',
        'origen': 'registro_autonomico_pau_toledo',
        'fecha_aprob': dated('field-fecha-aprobacion'),
        'fecha_publicacion': dated('field-publicacion-docm'),
        'fecha_publicacion_procedencia': 'Publicación en el DOCM (campo de la ficha JCCM)',
        'datos_inscripcion': field('field-datos-inscripcion'),
        'agente_urbanizador': field('field-agente-urbanizador'),
        'superficie_texto': field('field-superficie'), 'uso': field('field-uso'),
        'documentos': list(documents.values()),
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
        'coverage': 'partial_jccm_pau_register',
    }


class EsquiviasAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('evidence_dir')
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-esquivias/1.0 (public planning inventory)'

            def fetch(url):
                official_url(url, '/registros/')
                with session.get(url, timeout=40, stream=True) as response:
                    response.raise_for_status()
                    official_url(response.url, '/registros/')
                    if urlparse(response.url).path != urlparse(url).path or parse_qs(urlparse(response.url).query) != parse_qs(urlparse(url).query):
                        raise ValueError('Unexpected register redirect')
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > 4_000_000:
                            raise ValueError('Register response exceeds 4 MB')
                        chunks.append(chunk)
                    raw = b''.join(chunks)
                    html = raw.decode('utf-8')
                source_urls.append(url)
                if captures:
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(raw)
                return html

            value = municipality_filter(fetch(SOURCE))
            pending = [SOURCE + '?' + urlencode({'municipio': value})]
            seen, entries = set(), {}
            while pending:
                url = pending.pop(0)
                if url in seen:
                    continue
                if len(seen) >= 100:
                    raise ValueError('Pagination exceeds safety bound; no output written')
                seen.add(url)
                found, pages = parse_inventory(fetch(url), url)
                for target, title in found.items():
                    if target in entries and entries[target] != title:
                        raise ValueError('Conflicting PAU titles')
                    entries[target] = title
                pending.extend(sorted(pages - seen))
            rows = [parse_detail(fetch(url), url, title) for url, title in sorted(entries.items())]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'live_records': len(rows), 'source_urls': source_urls,
                'inventory_pages': len(seen), 'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
