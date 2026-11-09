"""Municipal planning inventory, with one record per instrument and linked files."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://transparencia.acrespins.es'
SOURCE = BASE + '/planes-urbanisticos/'
LIMITATIONS = [
    'Partial municipal coverage: only the published municipal planning inventory.',
    'Publication, agreement and approval dates are unknown; the inventory year is not a date.',
    'Linked PDF/ZIP/RAR contents are not parsed or georeferenced; attachment availability is not guaranteed.',
    'No granted licence register extracted; no coordinates or project geometry verified.',
]


def _soup(html):
    return BeautifulSoup(html, 'html.parser')


def parse_inventory(html: str) -> list[dict]:
    soup = _soup(html)
    # FacetWP embeds full counts even when no visible pagination control exists.
    match = re.search(r'window\.FWP_JSON\s*=\s*(\{.*?\});', html, re.S)
    if not match:
        raise ValueError('Missing FacetWP coverage metadata')
    pager = json.loads(match[1])['preload_data']['settings']['pager']
    template = soup.select_one('.facetwp-template[data-name="planes_urbansticos"]')
    if template is None:
        raise ValueError('Missing planning inventory')
    blocks = template.select('.fwpl-result')
    if (pager['page'] != 1 or pager['total_pages'] != 1
            or pager['total_rows'] != len(blocks)
            or pager['total_rows_unfiltered'] != len(blocks)):
        raise ValueError('Incomplete or paginated planning inventory; extend crawler')
    rows = {}
    for block in blocks:
        title = block.select_one('.fwpl-item.el-58pul')
        year = block.select_one('.fwpl-item.el-o1n97f')
        links = block.select('a[href]')
        if title is None or len(links) != 1:
            raise ValueError('Changed planning inventory entry')
        title = title.get_text(' ', strip=True)
        url = urljoin(SOURCE, links[0]['href']).split('#')[0]
        if (urlparse(url).netloc != urlparse(BASE).netloc
                or not urlparse(url).path.startswith('/plan-urbanistico/')
                or not re.match(r'^PGOU\b', title)):
            raise ValueError('Unreviewed instrument in planning inventory')
        if url in rows:
            raise ValueError('Duplicate planning instrument')
        rows[url] = {'titulo': title, 'url': url,
                     'anio_fuente': year.get_text(strip=True) if year else None}
    if not rows:
        raise ValueError('No usable planning instruments')
    return list(rows.values())


def parse_detail(html: str, item: dict) -> dict:
    soup = _soup(html)
    content = soup.select_one('[data-elementor-type="single-page"].plan-urbanistico')
    heading = content.select_one('h2') if content else None
    if heading is None or heading.get_text(' ', strip=True) != item['titulo']:
        raise ValueError('Missing or mismatched planning detail')
    documents = {}
    for a in content.select('a[href]'):
        url = urljoin(item['url'], a['href'])
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            raise ValueError('Invalid document scheme')
        if parsed.netloc not in ('transparencia.acrespins.es', 'www.lalcudiadecrespins.es'):
            raise ValueError('Unreviewed document host')
        if not re.search(r'\.(pdf|zip|rar)$', parsed.path, re.I):
            raise ValueError('Unreviewed planning document format')
        container = a.find_parent(class_='e-con-inner')
        label = container.select_one('.elementor-widget-text-editor') if container else None
        title = label.get_text(' ', strip=True) if label else a.get_text(' ', strip=True)
        documents.setdefault(url, {'titulo': title, 'url': url, 'source_url': item['url']})
    if not documents:
        raise ValueError('Planning instrument without source documents')
    return {
        **item,
        'id': 'l-alcudia-de-crespins-proy-' + hashlib.sha256(item['url'].encode()).hexdigest()[:16],
        'municipio': "l'Alcúdia de Crespins", 'codigo_ine': '46020', 'provincia': 'Valencia',
        'tipo': 'PGOU', 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_planes_urbanisticos',
        'source_url': SOURCE, 'documentos': list(documents.values()),
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'coverage': 'partial', 'limitations': LIMITATIONS,
    }


class LAlcudiaDeCrespinsAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-46020/1.0'}) as response:
            response.raise_for_status()
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected municipal HTML')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 5_000_000:
                    raise ValueError('Municipal HTML exceeds size limit')
            if self.config.get('capture_dir'):
                directory = Path(self.config['capture_dir'])
                directory.mkdir(parents=True, exist_ok=True)
                name = 'planes-urbanisticos' if url == SOURCE else urlparse(url).path.strip('/').replace('/', '-')
                (directory / (name + '.html')).write_bytes(body)
            return body.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        inventory = parse_inventory(self._fetch(SOURCE))
        rows = [parse_detail(self._fetch(item['url']), item) for item in inventory]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + [r['url'] for r in rows],
                'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot; no date cursor that could omit undated instruments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
