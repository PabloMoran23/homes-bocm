"""Municipal planning inventory; one record per plan or numbered amendment."""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://elgoibar.eus/es/servicios/urbanismo/'
SECTIONS = {
    'Plan General de Ordenación Urbana (PGOU)',
    'Planes de Ordenación Pormenorizada',
    'Planes en proceso de tramitación',
}
LIMITATIONS = [
    'Cobertura parcial: inventario municipal de PGOU y ordenación pormenorizada; no registro exhaustivo de obras ni licencias.',
    'PIAU, movilidad, noticias y contratación fuera del alcance.',
    'Fechas de publicación y acuerdo no extraídas de los PDF; permanecen nulas. Las etiquetas documentales no acreditan por sí solas vigencia actual.',
    'Documentos enlazados conservados; el extractor no descarga ni interpreta todos los PDF.',
    'Sin geometría verificada ni coordenadas; planos PDF no vectorizados.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _url(base, href):
    url = urldefrag(urljoin(base, href))[0]
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'elgoibar.eus', 'www.elgoibar.eus'}:
        raise ValueError(f'Unexpected planning source URL: {url}')
    return url


def _main(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if not main:
        raise ValueError('Missing municipal main content')
    # No reviewed page is paginated. Fail on new pagination instead of silently
    # accepting just its first page. Never impose a record-count truncation.
    for a in main.select('a[href]'):
        if ('next' in a.get('rel', []) or
            re.search(r'pagination|page-numbers|next', ' '.join(a.get('class', []))) or
            _text(a).casefold() in {'siguiente', 'hurrengoa', 'next', '»', '›'}):
            raise ValueError('Unreviewed pagination in planning source')
    return main


class ElgoibarAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        main = _main(html)
        found, links = set(), {}
        for panel in main.select('.lsow-panel'):
            heading = panel.select_one('.lsow-panel-title')
            if heading is None or _text(heading) not in SECTIONS:
                continue
            found.add(_text(heading))
            content = panel.select_one('.lsow-panel-content')
            if content is None:
                raise ValueError('Missing planning section content')
            for a in content.select('a[href]'):
                if a['href'].startswith('#'):
                    continue
                url = _url(SOURCE, a['href'])
                if not urlparse(url).path.startswith('/es/'):
                    raise ValueError('Inventory now links directly to documents; review grouping')
                links.setdefault(url, _text(a))
        if found != SECTIONS or not links:
            raise ValueError('Planning inventory missing expected sections or instruments')
        return list(links)

    @staticmethod
    def parse_detail(html, url):
        main = _main(html)
        content = main.select_one('.entry-content')
        heading = main.select_one('h1')
        if content is None or heading is None:
            raise ValueError('Missing plan detail content/title')
        titles = content.select('.lsow-tab-title')
        panes = content.select('.lsow-tab-pane')
        if titles or panes:
            if len(titles) != len(panes) or not titles:
                raise ValueError('Ambiguous planning tab grouping')
            groups = [(_text(t), p) for t, p in zip(titles, panes)]
        else:
            groups = [(_text(heading), content)]
        rows = []
        for title, group in groups:
            if not re.search(r'plan|modificaci', title, re.I):
                raise ValueError('Unrecognised instrument heading')
            docs = {}
            for a in group.select('a[href]'):
                if a['href'].startswith('#'):
                    continue
                doc_url = _url(url, a['href'])
                if not urlparse(doc_url).path.lower().endswith('.pdf'):
                    raise ValueError('New non-PDF plan link requires review')
                doc = docs.setdefault(doc_url, {
                    'url': doc_url, 'titulo': _text(a), 'etiquetas_fuente': [],
                    'url_procedencia': url,
                })
                label = _text(a)
                if label not in doc['etiquetas_fuente']:
                    doc['etiquetas_fuente'].append(label)
            if not docs:
                raise ValueError(f'Instrument lacks documents: {title}')
            # URL plus semantic tab title: independent of document order/count.
            key = url + '\n' + title.casefold()
            rows.append({
                'id': 'elgoibar-proy-' + hashlib.sha256(key.encode()).hexdigest()[:20],
                'municipio': 'Elgoibar', 'codigo_ine': '20032', 'provincia': 'Gipuzkoa',
                'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None,
                'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
                'url_inventario': SOURCE, 'documentos': list(docs.values()),
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            })
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate instrument headings')
        return rows

    def _fetch(self, url):
        time.sleep(.25)
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'municipio-elgoibar/1.0 (public planning inventory)',
        })
        response.raise_for_status()
        if _url(url, response.url) != url or 'html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Unexpected redirect or content type')
        response.encoding = 'utf-8'
        capture_dir = self.config.get('evidence_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        urls = self.parse_inventory(self._fetch(SOURCE))
        rows = []
        for url in urls:
            rows.extend(self.parse_detail(self._fetch(url), url))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Entire current inventory is refreshed, with stable instrument IDs.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
