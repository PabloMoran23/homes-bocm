"""Villacañas: complete Trámites inventory, grouped into its reviewed POM.

The catalogue labels do not match several PDF titles. MAPS describes the actual
plan sheets, visually verified during research, and retains the original labels.
Requires the existing system pdftotext executable for the textual POM documents.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.aytovillacanas.com'
SOURCE = BASE + '/?option=com_content&view=category&id=109'
DOCS = BASE + '/images/estatico/ayuntamiento/urbanismo/'
MAPS = {
    'clasficaci_n.pdf': 'P-1 Clasificación del suelo',
    'calificacion.compressed.pdf': 'P-2 Calificación del suelo',
    'gestion.pdf': 'P-3 Gestión del suelo',
    'abastecimiento.pdf': 'P-5 Red de abastecimiento',
    'saneamiento.pdf': 'P-6 Red de saneamiento',
    'catalogo-bienes.pdf': 'P-7 Catálogo de bienes protegidos, núcleo urbano',
}
TEXTS = {
    'memoriavilcan.pdf': ('Memoria', 'MEMORIA PLAN DE ORDENACION MUNICIPAL'),
    'normasvilcan.pdf': ('Normas urbanísticas', 'NORMAS URBANISTICAS'),
    'anexosvilcan.pdf': ('Anexos normativos', 'ANEXOS NORMATIVOS'),
}
LIMITATIONS = [
    'Cobertura parcial: documento refundido del POM de julio de 2001 y planos publicados en el catálogo actual; no historial completo de modificaciones ni obras.',
    'Los rótulos Memoria, Normas, Anexos y Catálogo del catálogo enlazan planos; se conserva el rótulo y el título real del documento por separado.',
    'Las fechas del catálogo son de publicación de sus fichas, no de aprobación ni publicación oficial del POM; estas últimas no se han verificado.',
    'Sin registro verificado de licencias concedidas ni geometría georreferenciada extraída. Sin coordenadas sustitutas.',
]


def inventory_url(start=0):
    return SOURCE + (f'&start={start}' if start else '')


def parse_inventory(html):
    """Return reviewed map references and all pagination offsets, never news."""
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#contenido.bloginicio')
    if content is None:
        raise ValueError('Missing municipal inventory (login/error/changed markup)')
    counter = content.select_one('.pagination-counter')
    match = re.fullmatch(r'Página\s+(\d+)\s+de\s+(\d+)', counter.get_text(' ', strip=True) if counter else '')
    if not match:
        raise ValueError('Missing explicit pagination coverage')
    page, total = map(int, match.groups())
    if not 1 <= page <= total <= 50:
        raise ValueError('Invalid or oversized pagination; review inventory')
    offsets = {0}
    for link in content.select('.pagination a[href]'):
        href = urlparse(urljoin(BASE, unescape(link['href'])))
        if href.netloc != urlparse(BASE).netloc:
            raise ValueError('Off-site pagination')
        # Joomla renders &amp;start inside the attribute on this site.
        query = parse_qs(href.query)
        if 'start' in query:
            value = query['start'][0]
            if not value.isdigit():
                raise ValueError('Invalid pagination offset')
            offsets.add(int(value))
        elif href.path not in ('/', '') and '/109-' not in href.path:
            raise ValueError('Unknown pagination route')
    docs = []
    for item in content.select('.article'):
        title_node = item.select_one('.article-header h2 a[href]')
        if title_node is None:
            raise ValueError('Inventory item without title')
        title = title_node.get_text(' ', strip=True)
        if not title.endswith('- URBANISMO'):
            continue  # Forms/news from other areas are not plan documents.
        match_id = re.search(r'/article/(\d+)-', title_node['href'])
        stamp = item.select_one('.published time[datetime]')
        published = date.fromisoformat(stamp['datetime'][:10]).isoformat() if stamp else None
        links = item.select('.field-entry.fichero a[href]')
        if not match_id or not links:
            raise ValueError('Urbanismo item without provenance or attachment')
        for link in links:
            url = urljoin(BASE, link['href'])
            filename = urlparse(url).path.rsplit('/', 1)[-1]
            if url != DOCS + filename or filename not in MAPS:
                raise ValueError('Unreviewed urbanismo document; cannot assume it belongs to POM')
            docs.append({
                'url': url, 'titulo': MAPS[filename],
                'procedencia': [{
                    'url': BASE + '/?option=com_content&view=article&id=' + match_id[1],
                    'titulo_catalogo': title, 'fecha_publicacion_ficha': published,
                }],
            })
    return docs, page, total, offsets


def build_project(docs, texts):
    """Validate actual POM content before emitting one instrument, without dates."""
    for filename, (_, marker) in TEXTS.items():
        text = ' '.join(texts[filename].split())
        if marker not in text or not re.search(r'POM\.\s*Villacañas\s+Doc\.\s*Refundido-Julio\s+01\.v1', text):
            raise ValueError('Textual document no longer identifies the reviewed Villacañas POM')
    merged = {}
    for doc in docs:
        if doc['url'] not in merged:
            merged[doc['url']] = {**doc, 'procedencia': list(doc['procedencia'])}
        else:
            for source in doc['procedencia']:
                if source not in merged[doc['url']]['procedencia']:
                    merged[doc['url']]['procedencia'].append(source)
    if set(merged) != {DOCS + name for name in MAPS}:
        raise ValueError('Incomplete reviewed plan-sheet inventory')
    for filename, (title, _) in TEXTS.items():
        merged[DOCS + filename] = {
            'url': DOCS + filename, 'titulo': title,
            'procedencia': [{'url': DOCS + filename, 'descubrimiento': 'PDF oficial localizado mediante índice público del buscador; no enlazado por la ficha actual'}],
        }
    return {
        'id': 'villacanas-pom-refundido-2001', 'municipio': 'Villacañas',
        'codigo_ine': '45185', 'provincia': 'Toledo',
        'titulo': 'Plan de Ordenación Municipal de Villacañas — documento refundido julio 2001',
        'tipo': 'planeamiento_urbanistico', 'fase': None,
        'version_documental': 'Doc.Refundido-Julio 01.v1',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': SOURCE, 'url_documento': DOCS + 'memoriavilcan.pdf',
        'documentos': list(merged.values()),
        'source': 'ayuntamiento', 'origen': 'catalogo_municipal_urbanismo_y_documentos_POM',
        'descripcion': 'Documento refundido del Plan de Ordenación Municipal. Memoria, normas urbanísticas, anexos normativos y planos P-1, P-2, P-3, P-5, P-6 y P-7 agrupados en un instrumento.',
        'cobertura': 'parcial', 'limitaciones': LIMITATIONS,
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'Planos PDF disponibles; sin geometría georreferenciada extraída',
    }


class VillacanasAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []

    def _fetch(self, url, pdf=False):
        with requests.get(url, timeout=(15, 60), stream=True,
                          headers={'User-Agent': 'municipio-villacanas/1.0'}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            limit = 15_000_000 if pdf else 2_000_000
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source response exceeds reviewed size limit')
                chunks.append(chunk)
            data = b''.join(chunks)
        if pdf and not data.startswith(b'%PDF-'):
            raise ValueError('Expected municipal PDF, received error/login content')
        self.source_urls.append(url)
        evidence = self.config.get('evidence_dir')
        if evidence:
            folder = Path(evidence)
            folder.mkdir(parents=True, exist_ok=True)
            filename = urlparse(url).path.rsplit('/', 1)[-1] if pdf else 'inventory-' + hashlib.sha256(url.encode()).hexdigest()[:12] + '.html'
            (folder / filename).write_bytes(data)
        return data

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        pending, seen, pages, docs = {0}, set(), set(), []
        total = None
        while pending:
            offset = min(pending)
            pending.remove(offset)
            if offset in seen:
                continue
            seen.add(offset)
            if len(seen) > 50:
                raise ValueError('Pagination exceeds reviewed bound')
            found, page, count, offsets = parse_inventory(self._fetch(inventory_url(offset)).decode('utf-8'))
            if total is not None and total != count:
                raise ValueError('Inventory pagination changed during snapshot')
            if page in pages:
                raise ValueError('Repeated pagination page; refusing truncated snapshot')
            total = count
            pages.add(page)
            docs.extend(found)
            pending.update(offsets - seen)
        if pages != set(range(1, total + 1)):
            raise ValueError('Missing inventory pages')
        texts = {}
        for filename in TEXTS:
            data = self._fetch(DOCS + filename, pdf=True)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / filename
                path.write_bytes(data)
                result = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                                        check=True, capture_output=True, timeout=45)
                texts[filename] = result.stdout.decode('utf-8')
        row = build_project(docs, texts)
        for doc in row['documentos']:
            if doc['url'] not in self.source_urls:
                self._fetch(doc['url'], pdf=True)
        result = self._write(out_jsonl, [row])
        return {**result, 'inventory_pages': len(pages), 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
