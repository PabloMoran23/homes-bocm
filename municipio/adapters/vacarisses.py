"""Vacarisses municipal Urbanisme inventory: complete snapshot of linked instruments."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.vacarisses.cat'
SOURCE = BASE + '/ajuntament/normativa/urbanisme'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#readspeakerPage')
    if main is None or main.select_one('h1') is None:
        raise ValueError('Missing municipal content; refusing empty/login snapshot')
    # The current inventory is unpaginated. Fail explicitly if this changes.
    if soup.select('.pagination, .paginacio, .paginator, a[rel~=next], link[rel~=next]'):
        raise ValueError('Pagination detected; crawler requires review before extraction')
    for a in soup.select('a[href]'):
        if text(a).lower() in {'següent', 'seguent', 'siguiente', 'next', '»', '›'}:
            raise ValueError('Pagination link detected')
    return soup, main


def session_date(narrative):
    # Restrict to the governing-body session: Ventayol also quotes 2010/2006 laws.
    match = re.search(r'(?:Junta de Govern Local del|sessió ordinària el(?: dia)?)\s+(\d{1,2}) de (\w+) de (\d{4})', narrative)
    if match is None:
        return None
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


class VacarissesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html):
        _, main = content(html)
        if text(main.select_one('h1')) != 'Urbanisme':
            raise ValueError('Unexpected inventory title')
        urls = {}
        for a in main.select('.widgetMenu a[href]'):
            url = urljoin(SOURCE, a['href'])
            parts = urlsplit(url)
            if (parts.scheme != 'https' or parts.netloc != 'www.vacarisses.cat'
                    or not parts.path.startswith(urlsplit(SOURCE).path + '/') or parts.query or parts.fragment):
                raise ValueError('Unexpected inventory link: ' + url)
            urls[url] = None
        if not urls:
            raise ValueError('No municipal inventory entries')
        return list(urls)

    @staticmethod
    def parse_detail(html, url):
        soup, main = content(html)
        heading = text(main.select_one('h1'))
        body = main.select_one('.ddbbtext')
        narrative = text(body) if body else ''
        if 'va aprovar' not in narrative or 'Junta de Govern Local' not in narrative:
            raise ValueError('No verified instrument approval narrative: ' + url)
        docs = {}
        for a in soup.select('#page-documents a[href]'):
            link = urljoin(url, a['href'])
            if urlsplit(link).netloc != 'www.vacarisses.cat' or not urlsplit(link).path.lower().endswith('.pdf'):
                raise ValueError('Unexpected document link: ' + link)
            label = re.sub(r'\s*\([^()]*[KMGT]?B\)\s*$', '', text(a), flags=re.I)
            docs[link] = {'titulo': label, 'url': link, 'source_url': url}
        if not docs:
            raise ValueError('Instrument lacks document provenance: ' + url)
        # Separate instruments sharing an area; keep announcement and project together.
        if 'Modificació de l\'Estudi de Detall' in narrative:
            groups = [('estudi_detall', heading, list(docs.values()))]
        elif '“PROJECTE DE REPARCEL·LACIÓ' in narrative:
            title = re.search('“([^”]+)”', narrative)[1]
            groups = [('reparcelacion', title, list(docs.values()))]
        else:
            groups = []
            for token, kind, title in [("urbanització", 'urbanizacion', "Projecte d'urbanització"),
                                       ('reparcel·lació', 'reparcelacion', 'Projecte de reparcel·lació')]:
                if token not in narrative:
                    continue
                selected = [d for d in docs.values() if token in d['titulo'].lower()]
                # The single Pou Gran announcement has no instrument in its label.
                if 'reparcel·lació' not in narrative:
                    selected = list(docs.values())
                if not selected:
                    raise ValueError('Instrument missing documents: ' + kind)
                groups.append((kind, title + ' — ' + heading, selected))
        if not groups or {d['url'] for _, _, ds in groups for d in ds} != set(docs):
            raise ValueError('Unclassified documents/instruments: ' + url)
        agreement = session_date(narrative)
        updated = main.select_one('.updated')
        updated_match = re.search(r'(\d{1,2})\.(\d{2})\.(\d{4})', text(updated)) if updated else None
        updated_date = date(int(updated_match[3]), int(updated_match[2]), int(updated_match[1])).isoformat() if updated_match else None
        rows = []
        for kind, title, documents in groups:
            initial = 'va aprovar inicialment' in narrative or any('aprovació inicial' in d['titulo'].lower() for d in documents)
            row = {
                'id': 'vacarisses-proy-' + hashlib.sha256((url + '#' + kind).encode()).hexdigest()[:16],
                'municipio': 'Vacarisses', 'provincia': 'Barcelona', 'codigo_ine': '08291',
                'titulo': title, 'tipo': kind, 'fase': 'aprobación inicial' if initial else None,
                'fecha': None, 'fecha_acuerdo': agreement, 'fecha_aprob': agreement,
                'fecha_publicacion': None, 'fecha_actualizacion_fuente': updated_date,
                'descripcion': narrative, 'url': url, 'documentos': documents,
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_urbanisme',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'geometry_status': 'No verified instrument geometry extracted',
            }
            if '“PROJECTE DE REPARCEL·LACIÓ' in narrative:
                row['source_warning'] = 'Municipal narrative mentions urbanisation works but the quoted instrument title is reparcellation; retained as one reparcellation instrument.'
            rows.append(row)
        return rows

    def _fetch(self, url):
        with requests.get(url, timeout=(10, 45), stream=True,
                          headers={'User-Agent': 'municipio-vacarisses/1.0'}) as response:
            response.raise_for_status()
            if urlsplit(response.url).netloc != 'www.vacarisses.cat':
                raise ValueError('Unexpected redirect away from municipal source')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Municipal HTML exceeds response bound')
                chunks.append(chunk)
            raw = b''.join(chunks)
            html = raw.decode('utf-8')
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (urlsplit(url).path.rsplit('/', 1)[-1] + '.html')).write_bytes(raw)
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        urls = self.parse_inventory(self._fetch(SOURCE))
        rows = []
        for url in urls:
            rows.extend(self.parse_detail(self._fetch(url), url))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + urls,
                'coverage': 'Complete linked Urbanisme inventory; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
