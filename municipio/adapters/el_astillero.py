"""Official current planning inventory, without inferred dates or geometry."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter

SETTINGS = {'slug': 'el-astillero', 'nombre': 'El Astillero', 'ine': '39008', 'url': 'https://www.astillero.es/content/urbanismo'}
PLAN_TITLE = 'Revisión de las Normas Subsidiarias de Planeamiento Municipal de Astillero'


def discover_sections(html, url):
    content = BeautifulSoup(html, 'html.parser').select_one('.field-name-body')
    if content is None:
        raise ValueError('Urbanism inventory missing')
    sections = {}
    for anchor in content.select('a[href]'):
        target = urljoin(url, anchor['href'])
        path = urlparse(target).path
        if urlparse(target).hostname == urlparse(url).hostname and path in (
            '/content/normas-urbanismo', '/content/anexos-urbanismo', '/content/memoria-urbanismo'
        ):
            sections[path] = target
    if len(sections) != 3:
        raise ValueError('Expected linked norms, annexes and memory inventory')
    return list(sections.values())


def parse_documents(html, url):
    content = BeautifulSoup(html, 'html.parser').select_one('.field-name-body')
    if content is None:
        raise ValueError('Document inventory missing')
    docs = {}
    for anchor in content.select('a[href]'):
        target = urljoin(url, anchor['href'])
        parsed = urlparse(target)
        if parsed.hostname != urlparse(url).hostname or not parsed.path.startswith('/ckfinder/userfiles/files/') or not parsed.path.lower().endswith('.pdf'):
            continue
        title = anchor.get_text(' ', strip=True)
        if title:
            docs[target] = {'titulo': title, 'url': target, 'pagina_inventario': url}
    if not docs:
        raise ValueError('No planning PDF documents in linked section')
    return list(docs.values())


def build_record(documents):
    return {'id': 'el-astillero-plan-' + hashlib.sha256(PLAN_TITLE.encode()).hexdigest()[:16],
            'municipio': SETTINGS['nombre'], 'codigo_ine': SETTINGS['ine'],
            'titulo': PLAN_TITLE, 'tipo': 'instrumento de planeamiento',
            'url': SETTINGS['url'], 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'documentos': list({doc['url']: doc for doc in documents}.values()),
            'publication_ready': False, 'geometry_status': 'unavailable'}


class ElAstilleroAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        def fetch(url):
            response = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'})
            response.raise_for_status()
            if urlparse(response.url).hostname != urlparse(SETTINGS['url']).hostname:
                raise ValueError('Unexpected inventory redirect')
            return response
        response = fetch(SETTINGS['url'])
        documents = []
        for url in discover_sections(response.text, response.url):
            section = fetch(url)
            documents.extend(parse_documents(section.text, section.url))
        rows = [build_record(documents)]
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'publication_ready': False, 'coverage': 'current_document_inventory'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
