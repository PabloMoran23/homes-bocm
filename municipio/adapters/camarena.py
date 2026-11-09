"""Camarena's public planning document inventory (anonymous Gestiona/Wicket)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'https://camarena.sedelectronica.es'
URBANISMO = HOST + '/transparency/36778a0d-713b-4a3c-a8ba-f9056d4418d6/'
INVENTORY = HOST + '/transparency/bc7f3fd9-4305-42a7-8d98-eeee6b0fd6e8/'


def ajax_url(element, page_url):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing Wicket navigation callback')
    return urljoin(page_url, match[1])


def document_links(soup):
    documents = {}
    for a in soup.select('table a[href]'):
        url = urljoin(INVENTORY, a['href'])
        if re.fullmatch(re.escape(HOST) + r'/preview-document/[0-9a-f-]{36}', url):
            title = a.get_text(' ', strip=True)
            if not title:
                raise ValueError('Unnamed planning document')
            documents[url] = {'titulo': title, 'url': url}
    return documents


def merge_ajax(soup, xml):
    """Apply only HTML component updates, never execute website JavaScript."""
    root = ElementTree.fromstring(xml)
    components = root.findall('component')
    if root.tag != 'ajax-response' or not components:
        raise ValueError('Unexpected pagination response')
    for component in components:
        fragment = BeautifulSoup(component.text or '', 'html.parser')
        old = soup.find(id=component.get('id'))
        if old is not None:
            old.replace_with(fragment)
        else:
            table = soup.find('table')
            if table is None:
                raise ValueError('Missing document table')
            table.append(fragment)
    return soup


def parse_projects(documents):
    groups = {}
    for doc in documents:
        title = doc['titulo']
        match = re.search(r'\b(1986|1990|1993|2000)\b', title)
        if not match or not re.match(r'^(MEMORIA|NORMAS|ORDENANZAS|PLANO|MODIFICACIÓN)', title):
            raise ValueError('Unclassified inventory document: ' + title)
        groups.setdefault(match[1], []).append(doc)
    if not groups:
        raise ValueError('No planning instruments found')
    rows = []
    for year, docs in sorted(groups.items()):
        # Grouping is supported by the municipal titles, not an approval claim.
        if not any('NORMAS SUBSIDIARIAS' in d['titulo'] or 'MODIFICACIÓN' in d['titulo'] for d in docs):
            raise ValueError('Missing named instrument in group ' + year)
        rows.append({
            'id': 'camarena-nnss-' + year, 'municipio': 'Camarena',
            'codigo_ine': '45031', 'provincia': 'Toledo',
            'titulo': ('Normas Subsidiarias de Camarena — ' if year == '1986' else
                       'Modificación de las Normas Subsidiarias de Camarena — ') + year,
            'tipo': 'Normas Subsidiarias' if year == '1986' else 'Modificación de Normas Subsidiarias',
            'anio_documental': int(year), 'url': INVENTORY,
            'source': 'ayuntamiento', 'origen': 'inventario_normativa_urbanistica',
            'documentos': sorted(docs, key=lambda d: d['url']),
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'coverage': 'Inventario documental parcial; sin verificación de vigencia ni aprobación.',
        })
    return rows


class CamarenaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, session, url, **kwargs):
        if urlparse(url).hostname != urlparse(HOST).hostname:
            raise ValueError('Unexpected source host')
        response = session.get(url, timeout=40, **kwargs)
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(HOST).hostname:
            raise ValueError('Unexpected source redirect')
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f'source-{self._capture_index:02d}.txt').write_bytes(response.content)
            self._capture_index += 1
        return response

    def backfill_proyectos(self, out_jsonl: Path):
        self._capture_index = 0
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'
            parent = BeautifulSoup(self._get(session, URBANISMO).content, 'html.parser')
            category = next((a for a in parent.select('a[onclick]')
                             if a.get_text(strip=True).startswith('7.3. NORMATIVA URBANÍSTICA')), None)
            if category is None:
                raise ValueError('Missing municipal planning category')
            count = re.search(r'\(\s*(\d+)\s*\)', category.get_text())
            if not count:
                raise ValueError('Missing inventory count')
            expected = int(count[1])
            soup = BeautifulSoup(self._get(session, INVENTORY).content, 'html.parser')
            if '7.3. NORMATIVA URBANÍSTICA' not in soup.get_text():
                raise ValueError('Wrong inventory page')
            for _ in range(100):
                more = next((b for b in soup.select('button[onclick],a[onclick]')
                             if b.get_text(' ', strip=True) == 'Mostrar más'), None)
                if more is None:
                    break
                before = document_links(soup)
                response = self._get(session, ajax_url(more, INVENTORY),
                                     headers={'Wicket-Ajax': 'true', 'Referer': INVENTORY})
                soup = merge_ajax(soup, response.text)
                if document_links(soup) == before:
                    raise ValueError('Pagination made no progress')
            else:
                raise ValueError('Pagination safety bound reached; refusing partial output')
            documents = list(document_links(soup).values())
            if len(documents) != expected:
                raise ValueError(f'Incomplete inventory: {len(documents)} of {expected}')
            rows = parse_projects(documents)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'documents': len(documents), 'source_urls': [URBANISMO, INVENTORY],
                'coverage': 'complete snapshot of category 7.3, partial municipal coverage', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
