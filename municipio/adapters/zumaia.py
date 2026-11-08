"""Zumaia's public-exposure inventory: planning instruments and urbanisation projects."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://zumaia.eus/es/ayuntamiento/documentos-en-exposicion-publica-1'
LIMITATIONS = [
    'Partial coverage: only supported planning instruments and urbanisation projects in the municipal public-exposure inventory; not a complete current planning register.',
    'The live inventory contains historical notices; closed exposure does not mean definitive approval or completed works.',
    'Publication dates are municipal notice dates. Agreement and approval dates are not extracted from PDFs.',
    'PDF links and their municipal labels are retained; PDF contents and continued download availability are not validated.',
    'No verified instrument geometry or coordinates; publication_ready is false.',
    'Licence applications, activity applications, procurement, ordinances and unrelated notices are excluded; licences disabled.',
]


def _text(node):
    return node.get_text(' ', strip=True)


def _date(value):
    return datetime.strptime(value, '%d/%m/%Y').date().isoformat()


def _kind(title):
    title = title.casefold()
    if 'solicitud' in title or 'licitaci' in title:
        return None
    if 'estudio de detalle' in title:
        return 'estudio_de_detalle'
    if title.startswith('delimitación de unidad de ejecución'):
        return 'delimitacion_unidad_ejecucion'
    if title.startswith('modificación') and 'nnss' in title:
        return 'modificacion_normas_subsidiarias'
    if title.startswith('proyecto de urbanización'):
        return 'proyecto_urbanizacion'
    return None


def _check_pagination(soup):
    for a in soup.select('a[href]'):
        href = a['href']
        if (set(a.get('rel', [])) & {'next', 'prev'}
                or re.search(r'[?&](?:b_start(?::int)?|page|pagenumber)=', href, re.I)
                or _text(a).casefold() in {'siguiente', 'next', 'hurrengoa', '»', '›'}):
            raise ValueError('Inventory pagination detected; traversal must be reviewed before extraction')
    if soup.select('.batching, .pagination, .listingBar'):
        raise ValueError('Unreviewed pagination markup')


class ZumaiaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='zumaia', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://zumaia.eus')

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        _check_pagination(soup)
        core = soup.select_one('#content-core')
        if core is None:
            raise ValueError('Missing public-exposure inventory')
        rows = {}
        # Both tabs are rendered server-side. Their displayed totals guard against
        # silently accepting a partial table or a changed pagination mechanism.
        for tab in ('abiertos', 'cerrados'):
            link = core.select_one(f'a[href="#tab-{tab}"]')
            block = core.select_one(f'#tab-{tab}')
            match = re.search(r'\((\d+)\)', _text(link)) if link else None
            if block is None or match is None:
                raise ValueError('Missing inventory tab or advertised total')
            entries = [tr for tr in block.select('tr') if tr.find('td')]
            if len(entries) != int(match[1]):
                raise ValueError('Inventory row count differs from advertised total')
            for tr in entries:
                cells = tr.find_all('td', recursive=False)
                if len(cells) != 5 or not cells[1].select_one('a[href]'):
                    raise ValueError('Changed inventory row schema')
                a = cells[1].select_one('a[href]')
                title = _text(a)
                kind = _kind(title)
                if kind is None:
                    continue
                url = urldefrag(urljoin(SOURCE, a['href']))[0]
                if not url.startswith(SOURCE + '/') or urlparse(url).query:
                    raise ValueError('Unexpected instrument URL')
                expediente = _text(cells[0])
                if not re.fullmatch(r'\d{4}[A-Z]{4}\d{4}', expediente):
                    raise ValueError('Invalid expediente identifier')
                row = {
                    'id': 'zumaia-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                    'municipio': 'Zumaia', 'provincia': 'Gipuzkoa', 'codigo_ine': '20081',
                    'expediente': expediente, 'titulo': title, 'tipo': kind,
                    'fase': 'aprobación inicial' if 'aprobación inicial' in title.casefold() else None,
                    'fecha': None, 'fecha_publicacion': _date(_text(cells[3])),
                    'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': url, 'source': 'ayuntamiento', 'source_inventory': SOURCE,
                    'origen': 'documentos_en_exposicion_publica',
                    'estado_exposicion': tab, 'lat': None, 'lon': None, 'geometry': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                }
                if url in rows and rows[url] != row:
                    raise ValueError('Conflicting duplicate instrument notice')
                rows[url] = row
        if not rows:
            raise ValueError('No supported planning instruments in inventory')
        return list(rows.values())

    @staticmethod
    def parse_detail(html, row):
        soup = BeautifulSoup(html, 'html.parser')
        core = soup.select_one('#content-core')
        heading = soup.select_one('h1.documentFirstHeading')
        number = core.select_one('#file-number') if core else None
        if (core is None or heading is None or _text(heading) != row['titulo']
                or number is None or _text(number).split()[-1] != row['expediente']):
            raise ValueError('Detail identity differs from inventory')
        dates = {}
        for dt in core.select('.contract-dates dt'):
            dd = dt.find_next_sibling('dd')
            if dd:
                dates[_text(dt)] = _text(dd)
        if _date(dates.get('Fecha publicación', '')) != row['fecha_publicacion']:
            raise ValueError('Detail publication date differs from inventory')
        docs = {}
        for a in core.select('a[href]'):
            url = urldefrag(urljoin(row['url'], a['href']))[0]
            if not re.search(r'\.pdf(?:/|$)', urlparse(url).path, re.I):
                continue
            if urlparse(url).hostname != 'zumaia.eus':
                raise ValueError('Unreviewed external document host')
            label = _text(a)
            dd = a.find_parent('dd')
            if dd and dd.parent.get('class') and 'contract-files' in dd.parent['class']:
                dt = dd.find_previous_sibling('dt')
                if dt:
                    label = _text(dt)
            # Plone links to the same file both via its view and @@download.
            key = url.split('/@@download/', 1)[0]
            doc = docs.setdefault(key, {'titulo': label, 'url': url,
                                        'source_url': row['url'], 'enlaces': []})
            if url not in doc['enlaces']:
                doc['enlaces'].append(url)
            if '/@@download/' in url:
                doc['url'], doc['titulo'] = url, label
        if not docs:
            raise ValueError('Instrument notice has no linked PDF documentation')
        return {**row, 'documentos': list(docs.values())}

    def _fetch(self, url):
        response = requests.get(url, timeout=(15, 75), headers={
            'User-Agent': self.config.get('user_agent', 'municipio-zumaia/1.0')})
        response.raise_for_status()
        if (urlparse(response.url).hostname != 'zumaia.eus'
                or 'text/html' not in response.headers.get('Content-Type', '')):
            raise ValueError('Unexpected source redirect or content type')
        response.encoding = 'utf-8'
        html = response.text
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = 'inventory' if url == SOURCE else url.rsplit('/', 1)[-1]
            (directory / (name + '.html')).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                     for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = self.parse_inventory(self._fetch(SOURCE))
        rows = [self.parse_detail(self._fetch(row['url']), row) for row in rows]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + [r['url'] for r in rows],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot of both tabs; no date cutoff or incremental omission.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
