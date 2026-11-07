"""Municipal PGOU documentary inventory, one instrument with all linked documents."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.etxebarri.eus'
AREA = BASE + '/es-ES/Areas-Servicios/Urbanismo-Vivienda/'
SOURCE = AREA.rstrip('/')
LIMITATIONS = [
    'Cobertura parcial: exclusivamente el nuevo PGOU y su inventario documental municipal; no todo el planeamiento ni las obras.',
    'Sin fecha de publicación o acuerdo acreditada; las fechas de talleres y los metadatos web no son aprobaciones.',
    'No se verifica vigencia normativa ni aprobación definitiva del nuevo PGOU.',
    'Sin geometría verificada por instrumento; no se geocodifica ni se inventan coordenadas.',
    'Licencias deshabilitadas: los trámites y solicitudes no acreditan concesiones.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href]'):
        if ('next' in (a.get('rel') or []) or
                a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', 'hurrengoa', 'siguiente página'}):
            if a['href'] not in {'', '#'}:
                raise ValueError('Pagination detected; review inventory before accepting a partial snapshot')
    return soup


def discover(html, page_url, filename):
    links = {urldefrag(urljoin(page_url, a['href']))[0]
             for a in _soup(html).select('a[href]')
             if urlparse(urljoin(page_url, a['href'])).path == urlparse(AREA).path + 'Paginas/' + filename}
    links = {u for u in links if urlparse(u).netloc == urlparse(BASE).netloc and urlparse(u).scheme == 'https'}
    if len(links) != 1:
        raise ValueError(f'Missing or ambiguous municipal inventory link: {filename}')
    return links.pop()


def parse_inventory(html, page_url, plan_url):
    soup = _soup(html)
    blocks = [b for b in soup.select('.ms-rtestate-field')
              if 'Documentación del proceso en las diferentes fases' in b.get_text(' ', strip=True)]
    if len(blocks) != 1 or 'PGOU' not in soup.get_text(' ', strip=True):
        raise ValueError('PGOU documentary inventory missing or changed')
    block = blocks[0]
    documents = {}
    for a in block.select('a[href]'):
        url = urldefrag(urljoin(page_url, a['href']))[0]
        if urlparse(url).path.lower().endswith(('.pdf', '.zip')):
            if not url.startswith(AREA + 'PGOU/'):
                raise ValueError('Document provenance changed; review official source')
            title = a.get_text(' ', strip=True)
            if not title:
                raise ValueError('Document without a label')
            documents.setdefault(url, {'titulo': title, 'url': url, 'source_url': page_url})
    if not documents or not any(d['titulo'].casefold() == 'avance' for d in documents.values()):
        raise ValueError('No substantive PGOU advance document')
    return [{
        'id': 'etxebarri-proy-pgou', 'municipio': 'Etxebarri', 'codigo_ine': '48029',
        'provincia': 'Bizkaia', 'titulo': 'Plan General de Ordenación Urbana de Etxebarri (nuevo PGOU)',
        'tipo': 'planeamiento_urbanistico', 'fecha': None, 'fecha_publicacion': None,
        'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': plan_url, 'source': 'ayuntamiento', 'origen': 'inventario_documental_pgou',
        'source_urls': [plan_url, page_url], 'documentos': list(documents.values()),
        'descripcion': 'Documentación municipal del nuevo PGOU: diagnóstico, avance, planos y evaluación ambiental. La enumeración de fases futuras no acredita su aprobación.',
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False, 'cobertura': 'parcial: nuevo PGOU',
    }]


class EtxebarriAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        with requests.get(url, timeout=35, stream=True,
                          headers={'User-Agent': 'municipio-etxebarri/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).netloc != urlparse(BASE).netloc:
                raise ValueError('Unexpected redirect outside the municipality website')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Source exceeds reviewed response size')
                chunks.append(chunk)
            data = b''.join(chunks)
            html = data.decode('utf-8-sig')
        capture_dir = self.config.get('evidence_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(data)
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        plan_url = discover(self._fetch(SOURCE), SOURCE, 'PGOU-Etxebarri.aspx')
        html = self._fetch(plan_url)
        if 'Plan General de Ordenación Urbana de Etxebarri' not in _soup(html).get_text(' ', strip=True):
            raise ValueError('Municipal PGOU identity missing')
        inventory_url = discover(html, plan_url, 'PGOU-Documentacion.aspx')
        rows = parse_inventory(self._fetch(inventory_url), inventory_url, plan_url)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, plan_url, inventory_url],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
