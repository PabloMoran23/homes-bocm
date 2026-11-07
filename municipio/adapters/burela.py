"""Burela's municipal planning library; one record per instrument, not per PDF."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://burela.org/es/urbanismo'
MONTHS = {'marzo': 3, 'abril': 4}
LIMITATIONS = [
    'Partial coverage: planning instruments linked by the municipal Urbanismo page only; no comprehensive works or licence register.',
    'Initial modification has no explicit agreement/publication date in the source; its current procedural status is not independently certified.',
    'PDF/ZIP links retained as an inventory; not all document contents or availability are verified.',
    'No verified vector geometry or coordinates; PDF maps are not georeferenced by this adapter.',
]


def official_url(base, href):
    url = urlsplit(urljoin(base, href))
    if url.hostname not in {'burela.org', 'www.burela.org'}:
        raise ValueError('Unexpected nonmunicipal planning source')
    return urlunsplit(('https', 'burela.org', quote(unquote(url.path), safe='/'), url.query, ''))


def checked_soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('.pager, .pagination, a[rel~=next]'):
        raise ValueError('Pagination appeared: review traversal before accepting a partial inventory')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).lower() in {'siguiente', 'seguinte', 'next', '›', '»'}:
            raise ValueError('Uncovered pagination')
    if not soup.select_one('article .field-name-body'):
        raise ValueError('Missing municipal article body')
    return soup


def parse_inventory(html):
    soup = checked_soup(html)
    body = soup.select_one('article .field-name-body')
    sources = {}
    for a in body.select('a[href]'):
        title = a.get_text(' ', strip=True)
        if not re.search(r'pxom|aprobaci[oó]n|plan xeral|plan general', title, re.I):
            continue
        if 'Definitiva' in title:
            kind = 'pxom'
        elif 'Modificación Puntual' in title:
            kind = 'modificacion'
        else:
            raise ValueError('Unrecognized planning instrument: ' + title)
        url = official_url(SOURCE, a['href'])
        if kind in sources and sources[kind] != url:
            raise ValueError('Multiple instruments require explicit grouping review')
        sources[kind] = url
    if set(sources) != {'pxom', 'modificacion'}:
        raise ValueError('Municipal planning inventory changed or is incomplete')
    return sources


def _explicit_date(pattern, text):
    match = re.search(pattern, text, re.I)
    if not match:
        return None
    day, month, year = match.groups()
    return date(int(year), MONTHS[month.lower()], int(day)).isoformat()


def parse_instrument(html, url, kind):
    soup = checked_soup(html)
    article = soup.select_one('article')
    heading = article.select_one('h1')
    body = article.select_one('.field-name-body')
    title = heading.get_text(' ', strip=True) if heading else ''
    paragraphs = [p.get_text(' ', strip=True) for p in body.select('p')]
    narrative = '\n'.join(p for p in paragraphs if p)
    if kind == 'pxom':
        if 'Documento de Aprobación Definitiva' not in title or 'foi aprobado definitivamente' not in narrative:
            raise ValueError('Unverified definitive PXOM narrative')
        approval = _explicit_date(r'Orde de (\d+) de (\w+) de (\d{4})', narrative)
        publication = _explicit_date(r'D\.O\.G\. número \d+, de (\d+) de (\w+) de (\d{4})', narrative)
        norms_publication = _explicit_date(r'B\.O\.P\. número \d+, de (\d+) de (\w+) de (\d{4})', narrative)
        if not all([approval, publication, norms_publication]):
            raise ValueError('Definitive approval/publication dates need review')
        phase = 'aprobación definitiva'
    elif kind == 'modificacion':
        if 'Modificación Puntual' not in title or 'información pública' not in narrative:
            raise ValueError('Unverified initial modification narrative')
        approval = publication = norms_publication = None
        phase = 'aprobación inicial'
    else:
        raise ValueError('Unsupported instrument')
    docs = {}
    for a in body.select('a[href]'):
        if not re.search(r'\.(pdf|zip)(?:$|\?)', a['href'], re.I):
            continue
        doc_url = official_url(url, a['href'])
        label = a.get_text(' ', strip=True)
        if label == 'Descargar' and a.parent:
            label = a.parent.get_text(' ', strip=True)
        doc = docs.setdefault(doc_url, {'url': doc_url, 'url_original': urljoin(url, a['href']),
                                       'titulos_fuente': [], 'source_url': url})
        if label and label not in doc['titulos_fuente']:
            doc['titulos_fuente'].append(label)
    if not docs:
        raise ValueError('Planning instrument lacks document inventory')
    return {
        'id': 'burela-proy-' + kind, 'municipio': 'Burela', 'codigo_ine': '27902',
        'provincia': 'Lugo', 'titulo': title, 'tipo': 'planeamiento_urbanistico',
        'fase': phase, 'fecha': None, 'fecha_aprob': approval, 'fecha_acuerdo': None,
        'fecha_publicacion': publication, 'fecha_publicacion_normativa': norms_publication,
        'fecha_publicacion_tipo': 'DOG, orden de aprobación' if publication else None,
        'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
        'source_inventory': SOURCE, 'descripcion': narrative, 'documentos': list(docs.values()),
        'geometry': None, 'lat': None, 'lon': None, 'geometry_status': 'unavailable',
        'publication_ready': False,
    }


class BurelaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        captures = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        fetched = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-burela/1.0 (public planning inventory)'

            def fetch(url):
                response = session.get(url, timeout=40)
                response.raise_for_status()
                final_url = official_url(url, response.url)
                response.encoding = response.apparent_encoding
                if captures:
                    captures.mkdir(parents=True, exist_ok=True)
                    name = hashlib.sha256(final_url.encode()).hexdigest()[:16] + '.html'
                    (captures / name).write_bytes(response.content)
                fetched.append(final_url)
                return response.text, final_url

            html, _ = fetch(SOURCE)
            sources = parse_inventory(html)
            rows = []
            for kind, url in sources.items():
                html, canonical = fetch(url)
                rows.append(parse_instrument(html, canonical, kind))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': fetched,
                'limitations': LIMITATIONS, 'coverage': 'partial municipal planning library'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
