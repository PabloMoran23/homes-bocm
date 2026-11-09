"""Municipal current and previous urban-planning/public-works inventories."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://bisbalpenedes.com'
SOURCE = BASE + '/web/portfolio/urbanisme/'
ARCHIVE = BASE + '/web/portfolio/urbanisme-actuacions-anteriors/'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
LIMITATIONS = [
    'Partial coverage: municipal Urbanisme and linked Actuacions anteriors inventories only; not a complete historical register.',
    'Phases describe the published notice, not independently verified current legal status. Archive placement does not establish completion.',
    'No verified geometry or coordinates; publication_ready=false. No granted-licence register.',
    'The NSS adaptation links labelled initial and provisional approval point to the same PDF; phase and dates are unconfirmed.',
    'Source document URLs are retained verbatim, including HTTP links, spaces and a malformed .pdff annex link; availability is not guaranteed.',
]


def source_date(text):
    """Only explicit full dates, never upload paths or inferred publication dates."""
    numeric = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', text)
    catalan = re.search(r'\b(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\b', text.lower())
    if numeric:
        day, month, year = map(int, numeric.groups())
    elif catalan and catalan[2] in MONTHS:
        day, month, year = int(catalan[1]), MONTHS[catalan[2]], int(catalan[3])
    else:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _pagination_guard(soup):
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        href = a['href']
        in_inventory = a.find_parent(class_='entry-content') is not None
        in_pagination = a.find_parent(class_=re.compile(r'pagination|page-links')) is not None
        if (('next' in a.get('rel', []) and (in_inventory or in_pagination)) or re.search(r'/page/\d|[?&](?:page|paged)=', href)
                or label in {'next', 'següent', 'següents', 'siguiente', 'següent »'}):
            raise ValueError('Inventory pagination detected; refusing incomplete snapshot')


class LaBisbalDelPenedesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html, source_url):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('.entry-content')
        if not content or not content.find('h2', string=re.compile('Urbanisme, la Bisbal del Penedès')):
            raise ValueError('Missing municipal Urbanisme inventory')
        _pagination_guard(soup)
        rows, current = [], None
        # Flatten the WordPress wrapper groups once: p and li appear in DOM order.
        for block in content.select('p, li'):
            text = block.get_text(' ', strip=True)
            if block.name == 'p' and 'has-background' in block.get('class', []):
                current = None
                if text.startswith(('MODIFICACIÓ PUNTUAL', 'APROVACIÓ INICIAL PROJECTE')):
                    kind = 'proyecto_obra_publica' if text.startswith('APROVACIÓ') else 'modificacion_planeamiento'
                    exp = re.search(r'expedient\s+(\d+/\d{4})', text, re.I)
                    identity = exp[1] if exp else text
                    current = {
                        'id': 'la-bisbal-del-penedes-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
                        'municipio': 'La Bisbal del Penedès', 'provincia': 'Tarragona', 'codigo_ine': '43028',
                        'titulo': text, 'expediente': exp[1] if exp else None,
                        'tipo': kind, 'fase': None, 'fecha': None,
                        'fecha_acuerdo': None, 'fecha_aprob': None, 'fecha_publicacion': None,
                        'url': source_url, 'source': 'ayuntamiento', 'origen': 'inventario_urbanisme',
                        'descripcion': '', 'documentos': [],
                        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                        'geometry_status': 'No verified project geometry in inventory',
                        'cobertura': 'anterior' if source_url == ARCHIVE else 'exposicion_publica',
                    }
                    rows.append(current)
                elif ('has-luminous-vivid-orange-background-color' in block.get('class', [])
                      and text not in {'ACTUACIONS ANTERIORS', 'PAGINA INICIAL URBANISME'}):
                    raise ValueError('Unrecognized instrument heading: ' + text)
                continue
            if current is None:
                continue
            if block.name == 'p' and text:
                current['descripcion'] += ('\n' if current['descripcion'] else '') + text
                if text.startswith('Es fa públic') and re.search(r'aprova(?:t|r)?\s*inicialment', text, re.I):
                    agreement = source_date(text)
                    if agreement is None:
                        raise ValueError('Initial approval narrative has no valid agreement date')
                    current.update(fase='aprobacion_inicial', fecha_acuerdo=agreement, fecha_aprob=agreement)
            if block.name == 'li':
                for a in block.select('a[href]'):
                    url = urljoin(source_url, a['href'])
                    host = urlparse(url).hostname
                    if host not in {'bisbalpenedes.com', 'www.dipta.cat', 'dogc.gencat.cat'}:
                        raise ValueError('Unexpected document host: ' + url)
                    if not (re.search(r'\.pdf', urlparse(url).path, re.I) or host in {'www.dipta.cat', 'dogc.gencat.cat'}):
                        raise ValueError('Unrecognized document link: ' + url)
                    doc = next((d for d in current['documentos'] if d['url'] == url), None)
                    if doc is None:
                        doc = {'titulo': text, 'etiquetas': [], 'url': url, 'source_url': source_url,
                               'fecha_publicacion': None}
                        current['documentos'].append(doc)
                    if text not in doc['etiquetas']:
                        doc['etiquetas'].append(text)
                    # Publication dates only come from explicitly labelled publications.
                    if re.search(r'BOPT|Butlletí Oficial|DOGC|[Dd]iari', text):
                        doc['fecha_publicacion'] = source_date(text)
                    if re.search(r'BOPT|Butlletí Oficial', text) and doc['fecha_publicacion']:
                        current['fecha_publicacion'] = doc['fecha_publicacion']
                        current['fecha_publicacion_fuente'] = url
        if not rows or any(not r['documentos'] for r in rows):
            raise ValueError('Inventory empty or an instrument lacks documents')
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate instrument headings require grouping review')
        return rows

    def _fetch(self, url):
        with requests.get(url, timeout=(10, 45), stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-la-bisbal-del-penedes/1.0')
        }) as response:
            response.raise_for_status()
            if response.url.rstrip('/') != url.rstrip('/'):
                raise ValueError('Unexpected inventory redirect: ' + response.url)
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 3_000_000:
                    raise ValueError('Inventory exceeds 3 MB; refusing truncated extraction')
            html = bytes(data).decode('utf-8')
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / ('anteriors.html' if url == ARCHIVE else 'urbanisme.html')).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        html = self._fetch(SOURCE)
        soup = BeautifulSoup(html, 'html.parser')
        archive_links = {urljoin(SOURCE, a['href']) for a in soup.select('.entry-content a[href]')
                         if 'urbanisme-actuacions-anteriors' in a['href']}
        if archive_links != {ARCHIVE}:
            raise ValueError('Previous-instrument inventory link changed or disappeared')
        rows = self.parse_inventory(html, SOURCE)
        rows.extend(self.parse_inventory(self._fetch(ARCHIVE), ARCHIVE))
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Instrument occurs in both inventories; review merging before writing')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, ARCHIVE],
                'publication_ready': False, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Two nonpaginated live inventories: replace the complete scoped snapshot.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
