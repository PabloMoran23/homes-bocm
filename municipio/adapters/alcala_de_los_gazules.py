"""Current municipal PGOU document inventory; one instrument, many documents."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.alcaladelosgazules.es/index.php/urbanismo/pgou'


def inventory_url(url):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.netloc != urlparse(SOURCE).netloc
            or not (parsed.path == urlparse(SOURCE).path
                    or parsed.path.startswith(urlparse(SOURCE).path + '/'))):
        raise ValueError('Unexpected inventory/document URL: ' + url)
    return url


def all_items_url(url):
    parsed = urlparse(inventory_url(url))
    return urlunparse(parsed._replace(query=urlencode({'limit': 0}), fragment=''))


def parse_inventory(html, url):
    """Parse a complete Phoca category, failing on changed/incomplete markup."""
    soup = BeautifulSoup(html, 'html.parser')
    box = soup.select_one('#phoca-dl-category-box')
    heading = box.select_one('h3.pd-ctitle') if box else None
    if not heading:
        raise ValueError('Missing planning inventory heading')
    selected = box.select_one('select[name="limit"] option[selected]')
    if selected is None or selected.get('value') != '0' or box.select('.pagination a[href]'):
        raise ValueError('Inventory not complete: All selection/pagination changed')
    children = []
    for node in box.select('.pd-subcategory'):
        a, count = node.select_one('a[href]'), node.select_one('small')
        if not a or not count or not re.fullmatch(r'\(\d+\)', count.get_text(strip=True)):
            raise ValueError('Missing category document count')
        children.append({'url': inventory_url(urljoin(url, a['href'])),
                         'titulo': a.get_text(' ', strip=True),
                         'count': int(count.get_text(strip=True)[1:-1])})
    documents = {}
    for a in box.select('.pd-filename a[href]'):
        target = inventory_url(urljoin(url, a['href']))
        download = parse_qs(urlparse(target).query).get('download', [''])[0]
        title = a.get_text(' ', strip=True)
        if not re.fullmatch(r'\d+:[\w-]+', download) or not title:
            raise ValueError('Invalid document entry')
        key = download.split(':', 1)[0]
        doc = {'id_fuente': key, 'titulo': title, 'url': target,
               'inventory_url': url, 'volumen': heading.get_text(' ', strip=True)}
        if key in documents and documents[key] != doc:
            raise ValueError('Conflicting document identity')
        documents[key] = doc
    return heading.get_text(' ', strip=True), children, list(documents.values())


def extract_projects(fetch):
    """fetch(url) returns HTML. Reconcile each listed volume with its count."""
    title, children, documents = parse_inventory(fetch(all_items_url(SOURCE)), all_items_url(SOURCE))
    if not re.fullmatch(r'AVANCE Y DOCUMENTO INICIAL ESTRATEGICO PGOU ALCALA DE LOS GAZULES\. FEBRERO 2020', title):
        raise ValueError('Unrecognized PGOU instrument; review grouping')
    if not children or not documents:
        raise ValueError('Incomplete PGOU inventory')
    seen = {SOURCE}
    source_urls = [all_items_url(SOURCE)]
    for child in children:
        url = child['url']
        if url in seen or not child['titulo'].startswith('VOLUMEN '):
            raise ValueError('Ambiguous volume grouping')
        seen.add(url)
        page_url = all_items_url(url)
        volume, nested, docs = parse_inventory(fetch(page_url), page_url)
        if nested or volume != child['titulo'] or len(docs) != child['count']:
            raise ValueError('Volume incomplete or changed: ' + url)
        documents.extend(docs)
        source_urls.append(page_url)
    if len({d['id_fuente'] for d in documents}) != len(documents):
        raise ValueError('Document repeated across volumes')
    return [{
        'id': 'alcala-de-los-gazules-plan-' + hashlib.sha256(SOURCE.encode()).hexdigest()[:16],
        'municipio': 'Alcalá de los Gazules', 'codigo_ine': '11001', 'provincia': 'Cádiz',
        'titulo': title, 'tipo': 'instrumento de planeamiento urbanístico',
        'fase': 'avance y documento inicial estratégico',
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'periodo_documentacion': 'febrero 2020',
        'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_pgou',
        'source_urls': source_urls, 'documentos': sorted(documents, key=lambda d: int(d['id_fuente'])),
        'publication_ready': False, 'geometry_status': 'unavailable',
        'descripcion': 'Inventario documental municipal del avance del PGOU; no acredita vigencia ni aprobación definitiva.',
    }]


class AlcalaDeLosGazulesAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-inventory/1.0'

            def fetch(url):
                response = session.get(url, timeout=45)
                response.raise_for_status()
                inventory_url(response.url)
                if 'text/html' not in response.headers.get('Content-Type', ''):
                    raise ValueError('Expected HTML inventory')
                if captures:
                    folder = Path(captures)
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
                return response.text

            rows = extract_projects(fetch)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'documents': len(rows[0]['documentos']),
                'source_urls': rows[0]['source_urls'], 'coverage': 'current_pgou_advance_inventory',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full inventory snapshot; no date-based incremental omissions.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
