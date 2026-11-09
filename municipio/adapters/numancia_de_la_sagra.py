"""Municipal planning document inventory; no inference of approval or licence grants."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.ayuntamientonumanciadelasagra.com'
SOURCE = BASE + '/informacion-urbanistica/'


def norm(text):
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main .entry-content')
    if main is None:
        raise ValueError('Municipal inventory content missing')
    # This inventory and its document subpages are unpaginated. Refuse a
    # changed pagination contract rather than returning the first page only.
    for a in soup.select('a[href]'):
        if (a.get('rel') and 'next' in a['rel']) or (
            norm(a.get_text(' ', strip=True)) in {'siguiente', 'next', 'cargar mas', 'ver mas'}
            and a['href'] not in {'', '#'}
        ):
            raise ValueError('Unreviewed pagination in municipal inventory')
    if soup.select('.pagination, .page-numbers, .elementor-pagination, [data-next-page]'):
        raise ValueError('Unreviewed pagination in municipal inventory')
    return main


def official_url(href, page):
    url = urljoin(page, href)
    if urlsplit(url).scheme != 'https' or urlsplit(url).netloc != urlsplit(BASE).netloc:
        raise ValueError('Unexpected document host: ' + url)
    return url


def documents(main, page):
    docs = {}
    for a in main.select('a[href]'):
        if not urlsplit(a['href']).path.lower().endswith('.pdf'):
            continue
        url = official_url(a['href'], page)
        col = a.find_parent(class_='elementor-column')
        title = a.get_text(' ', strip=True) or (col.get_text(' ', strip=True) if col else '')
        docs.setdefault(url, {
            'titulo': title or unquote(urlsplit(url).path.rsplit('/', 1)[-1]),
            'url': url, 'url_origen': page,
        })
    return list(docs.values())


class NumanciaDeLaSagraAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        main = content(html)
        drafts = []
        for section in main.select('section.elementor-top-section'):
            text = norm(section.get_text(' ', strip=True))
            # Statutes of conservation entities are not planning projects.
            if 'modificacion puntual n12 nnss' in text:
                docs = documents(section, SOURCE)
                if len(docs) < 4:
                    raise ValueError('MP12 environmental document or technical volumes missing')
                drafts.append(('nnss-mp12', 'Modificación puntual nº 12 de las NNSS',
                               'planeamiento_urbanistico', SOURCE, docs))
            for a in section.select('a[href]'):
                if urlsplit(a['href']).path.lower().endswith('.pdf'):
                    continue
                col = a.find_parent(class_='elementor-column')
                label = norm(col.get_text(' ', strip=True) if col else a.get_text(' ', strip=True))
                if label == 'modificacion plan parcial s-7':
                    drafts.append(('s7-plan-parcial', 'Modificación del plan parcial del sector 7',
                                   'planeamiento_urbanistico', official_url(a['href'], SOURCE), []))
                elif label == 'modificacion proyecto urbanizacion':
                    drafts.append(('s7-urbanizacion', 'Modificación del proyecto de urbanización del sector 7',
                                   'proyecto_urbanizacion', official_url(a['href'], SOURCE), []))
                elif 'modific' in label or 'proyecto' in label:
                    raise ValueError('New instrument link requires parser review: ' + label)
        if {d[0] for d in drafts} != {'nnss-mp12', 's7-plan-parcial', 's7-urbanizacion'} or len(drafts) != 3:
            raise ValueError('Reviewed instrument inventory changed or disappeared')
        return drafts

    @staticmethod
    def parse_detail(html, page):
        docs = documents(content(html), page)
        if not docs:
            raise ValueError('Instrument has no municipal PDF documents')
        return docs

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('evidence_dir')
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-numancia-de-la-sagra/1.0'

            def fetch(url, name):
                response = session.get(url, timeout=40)
                response.raise_for_status()
                official_url(response.url, SOURCE)
                if 'text/html' not in response.headers.get('Content-Type', ''):
                    raise ValueError('Expected municipal HTML inventory')
                source_urls.append(response.url)
                if captures:
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / (name + '.html')).write_bytes(response.content)
                return response.text

            inventory = fetch(SOURCE, 'inventario')
            drafts = self.parse_inventory(inventory)
            # The convention is supporting context for S7, never another project.
            support = [d for d in documents(content(inventory), SOURCE)
                       if 'convenio' in norm(d['titulo']) and 's-7' in norm(d['titulo'])]
            rows = []
            for key, title, kind, page, docs in drafts:
                if page != SOURCE:
                    docs = self.parse_detail(fetch(page, key), page)
                if key == 's7-plan-parcial':
                    docs += [{**d, 'rol': 'propuesta_convenio_contexto_sector7'} for d in support]
                rows.append({
                    'id': self.slug + '-proy-' + key,
                    'municipio': 'Numancia de la Sagra', 'codigo_ine': '45119',
                    'provincia': 'Toledo', 'titulo': title, 'tipo': kind,
                    'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
                    'url': page, 'url_inventario': SOURCE, 'documentos': docs,
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                    'fecha_aprob': None, 'fase': None,
                    'lat': None, 'lon': None, 'geometry': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                    'limitaciones': 'Inventario documental parcial; no acredita aprobación, vigencia ni ejecución. '
                                    'No se usa la fecha de subida del PDF como publicación o acuerdo.',
                })
        return {**self._write(out_jsonl, rows), 'source_urls': source_urls,
                'coverage': 'partial_document_inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
