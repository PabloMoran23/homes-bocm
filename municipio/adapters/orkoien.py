"""Physical lighting projects in Orkoien's municipal PRTR inventory.

The inventory is a current snapshot, not a register of granted licences.
No dates are inferred from WordPress upload paths or HTTP metadata.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.orkoien.com/fondos-europeos-prtr/'
LIMITATIONS = [
    'Cobertura parcial: proyectos físicos de alumbrado con enlace documental en el inventario PRTR municipal; no todo el urbanismo municipal.',
    'Los carteles de modernización digital sin ficha textual se excluyen del ámbito de obras físicas.',
    'Sin registro verificado de licencias concedidas; licencias deshabilitadas.',
    'Sin fechas explícitas de publicación, acuerdo o aprobación ni geometría verificada; no se infieren de las rutas de archivos.',
    'El PDF se conserva y verifica como documento, pero no se interpreta automáticamente su texto ni su estado de ejecución.',
]


def _norm(text):
    return ' '.join(text.split()).casefold()


class OrkoienAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='orkoien', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.orkoien.com')
        self.captures = []

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('main')
        if not main:
            raise ValueError('Missing municipal PRTR main content')
        # This reviewed inventory has no pagination. Fail instead of silently
        # accepting a truncated snapshot if the publisher introduces it.
        if main.select('[rel~=next], .pagination, .nav-links, .page-numbers, [data-next-page]'):
            raise ValueError('PRTR pagination requires review')
        for a in main.select('a[href]'):
            if _norm(a.get_text(' ', strip=True)) in {'next', 'next »', 'siguiente', 'siguiente »', 'cargar más', 'ver más'}:
                raise ValueError('PRTR continuation requires review')
        headings = [h for h in main.select('h2,h3,h4') if _norm(h.get_text(' ', strip=True)) == 'proyectos ayuntamiento de orkoien']
        if len(headings) != 1:
            raise ValueError('Missing or ambiguous municipal project inventory heading')
        nodes = []
        for node in headings[0].next_elements:
            if isinstance(node, Tag) and node.name in {'h2', 'h3', 'h4'}:
                break
            nodes.append(node)
        text = ' '.join(str(n) for n in nodes if isinstance(n, str))
        if 'plan de recuperación' not in _norm(text):
            raise ValueError('Missing PRTR inventory scope description')
        projects = {}
        for a in nodes:
            if not isinstance(a, Tag) or a.name != 'a' or not a.get('href'):
                continue
            title = a.get_text(' ', strip=True)
            url = urldefrag(urljoin(SOURCE, a['href']))[0]
            # Only reviewed physical-work titles are supported. A new inventory
            # link needs explicit review rather than being silently ignored.
            if not re.fullmatch(r'RENOVACIÓN DE ALUMBRADO PÚBLICO EN ORKOIEN\s*[–—-]\s*[IVX]+ FASE\s*-?', title, re.I):
                raise ValueError('Unreviewed PRTR project link: ' + title)
            if urlparse(url).hostname != 'www.orkoien.com' or not urlparse(url).path.lower().endswith('.pdf'):
                raise ValueError('Expected official project PDF: ' + url)
            key = _norm(re.sub(r'[–—-]', ' ', title))
            if key not in projects:
                projects[key] = {
                    'id': 'orkoien-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                    'municipio': 'Orkoien', 'codigo_ine': '31906', 'provincia': 'Navarra',
                    'titulo': title, 'tipo': 'obra_publica', 'fase': None,
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_prtr',
                    'descripcion': 'Proyecto de renovación de alumbrado público incluido en el inventario municipal PRTR. Consultar el documento municipal para el detalle de la actuación.',
                    'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                    'coverage': 'partial',
                }
            docs = projects[key]['documentos']
            if not any(d['url'] == url for d in docs):
                docs.append({'titulo': title, 'url': url, 'source_url': SOURCE,
                             'tipo': 'comunicacion_municipal_proyecto'})
        if not projects:
            raise ValueError('No supported physical projects in PRTR inventory')
        return list(projects.values())

    def _fetch(self, url, pdf=False):
        response = requests.get(url, timeout=(10, 40), stream=True,
                                headers={'User-Agent': 'municipio-orkoien/1.0'})
        with response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'www.orkoien.com':
                raise ValueError('Unexpected source redirect: ' + response.url)
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 12_000_000:
                    raise ValueError('Source exceeds maximum size: ' + url)
            data = bytes(content)
            if pdf and not data.startswith(b'%PDF-'):
                raise ValueError('Source is not a PDF: ' + url)
            digest = hashlib.sha256(data).hexdigest()
            capture = {'url': url, 'final_url': response.url, 'sha256': digest, 'bytes': len(data)}
            if self.config.get('capture_dir'):
                directory = Path(self.config['capture_dir'])
                directory.mkdir(parents=True, exist_ok=True)
                name = hashlib.sha256(url.encode()).hexdigest()[:16] + ('.pdf' if pdf else '.html')
                (directory / name).write_bytes(data)
                capture['file'] = str(directory / name)
            self.captures.append(capture)
            return data if pdf else data.decode(response.encoding or 'utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.captures = []
        rows = self.parse_inventory(self._fetch(SOURCE))
        documents = {}
        for row in rows:
            for doc in row['documentos']:
                if doc['url'] not in documents:
                    data = self._fetch(doc['url'], pdf=True)
                    documents[doc['url']] = hashlib.sha256(data).hexdigest()
                doc['sha256'] = documents[doc['url']]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [c['url'] for c in self.captures],
                'captures': self.captures, 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of this small unpaginated inventory; no date cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
