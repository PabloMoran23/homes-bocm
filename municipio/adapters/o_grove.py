"""O Grove: municipal planning document inventories, grouped by instrument."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

PLANS_URL = 'https://concellodogrove.es/contido.html?id=80&submenu=23'
PXOM_URL = 'https://concellodogrove.es/pxom/pxom.php'


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href], link[href]'):
        if ('next' in a.get('rel', []) or
                a.get_text(' ', strip=True).casefold() in
                {'seguinte', 'siguiente', 'next', 'seguinte »', 'siguiente »'}):
            raise ValueError('Inventory pagination appeared; review crawler before extracting')
    return soup


def _documents(block, source_url, version=None):
    docs = {}
    for a in block.select('a[href], area[href]'):
        href = a['href'].strip()
        if not href or href.startswith('#'):
            continue
        url = urljoin(source_url, href)
        if urlparse(url).scheme not in {'http', 'https'}:
            raise ValueError('Unexpected document scheme')
        # Preserve Drive query/resource keys, folder links and image-map PDFs.
        label = a.get_text(' ', strip=True) or a.get('title') or a.get('alt')
        if label == 'Plano' and a.parent.name == 'li':
            label = a.parent.get_text(' ', strip=True)
        label = label or urlparse(url).path.rsplit('/', 1)[-1]
        if url not in docs:
            docs[url] = {'titulo': label, 'url': url, 'source_url': source_url}
            if version:
                docs[url]['version'] = version
    if not docs:
        raise ValueError('Instrument section has no documents')
    return list(docs.values())


def _record(key, title, source_url, docs):
    return {'id': 'o-grove-plan-' + key, 'municipio': 'O Grove',
            'codigo_ine': '36022', 'provincia': 'Pontevedra', 'titulo': title,
            'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
            'origen': 'inventario_documental_planeamiento', 'url': source_url,
            'documentos': docs, 'geometry_status': 'unavailable',
            'publication_ready': False}


def parse_plans(html, source_url=PLANS_URL):
    soup = _soup(html)
    content = soup.select_one('#content article .texto-longo')
    if content is None:
        raise ValueError('Missing municipal plans inventory')
    pxom = [urljoin(source_url, a['href']) for a in content.select('a[href]')
            if urlparse(urljoin(source_url, a['href'])).path == '/pxom/pxom.php']
    if not pxom:
        raise ValueError('PXOM inventory link disappeared')
    heading = next((p for p in content.select('p') if
                    p.get_text(' ', strip=True).startswith('Plan especial porto do Grove')), None)
    if heading is None:
        raise ValueError('Port planning instrument disappeared')
    block = heading.find_next_sibling()
    if block is None or block.name != 'ol':
        raise ValueError('Missing port plan document list')
    row = _record('porto', heading.get_text(' ', strip=True).rstrip(':'),
                  source_url, _documents(block, source_url))
    return row, pxom[0]


def parse_pxom(html, source_url=PXOM_URL):
    soup = _soup(html)
    main = soup.select_one('#contenido')
    if main is None:
        raise ValueError('Missing PXOM inventory')
    versions = []
    norms = None
    for heading in main.select('h2[id]'):
        button = heading.select_one('button[aria-controls]')
        if button is None:
            raise ValueError('Unrecognized planning section')
        title = button.get_text(' ', strip=True)
        block = main.find(id=button['aria-controls'])
        if block is None:
            raise ValueError('Missing planning documents')
        notes = []
        for sibling in heading.next_siblings:
            if sibling is block:
                break
            if getattr(sibling, 'get_text', None):
                notes.append(sibling.get_text(' ', strip=True))
        description = ' '.join(notes).strip()
        docs = _documents(block, source_url, title)
        if title == 'Normas Subsidiarias de Planeamento':
            norms = _record('normas-subsidiarias', title, source_url, docs)
            norms['descripcion'] = description
            match = re.search(r'Aprobadas (\d{2}-\d{2}-\d{4})', description)
            if match:
                norms['fecha_acuerdo'] = datetime.strptime(match[1], '%d-%m-%Y').date().isoformat()
        elif re.fullmatch(r'PXOM \d{4}', title):
            version = {'titulo': title, 'descripcion': description, 'documentos': docs}
            match = re.search(r'Aprobado provisionalmente polo Pleno do (\d{2}/\d{2}/\d{4})', description)
            if match:
                version['fecha_acuerdo'] = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
                version['fase'] = 'aprobacion_provisional'
            versions.append(version)
        else:
            raise ValueError('Unrecognized planning instrument: ' + title)
    if norms is None or not versions:
        raise ValueError('Incomplete planning inventory')
    versions.sort(key=lambda v: v['titulo'])
    docs = [doc for version in versions for doc in version['documentos']]
    row = _record('pxom', 'Plan Xeral de Ordenación Municipal (PXOM)', source_url, docs)
    row['versiones'] = [{k: v for k, v in version.items() if k != 'documentos'} for version in versions]
    latest = versions[-1]
    row['descripcion'] = latest['titulo'] + ': ' + latest['descripcion']
    for key in ('fecha_acuerdo', 'fase'):
        if key in latest:
            row[key] = latest[key]
    return [norms, row]


class OGroveAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in {'concellodogrove.es', 'www.concellodogrove.es'}:
            raise ValueError('Unexpected municipal inventory redirect')
        response.encoding = 'utf-8'
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / ('pxom.html' if '/pxom/' in response.url else 'plans.html')).write_text(
                response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'coverage': 'municipal_planning_document_inventories'}

    def backfill_proyectos(self, out_jsonl):
        port, pxom_url = parse_plans(self._fetch(PLANS_URL))
        if urlparse(pxom_url).hostname not in {'concellodogrove.es', 'www.concellodogrove.es'}:
            raise ValueError('Unexpected PXOM source')
        rows = [port, *parse_pxom(self._fetch(pxom_url), pxom_url)]
        return self._write(out_jsonl, rows)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
