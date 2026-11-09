"""El Carpio (Córdoba): municipal PGOU documentary inventory, partial coverage."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE_URL = (
    'https://ayunelcarpio.es/'
    'transparencia-en-materias-de-urbanismo-obras-publicas-y-medio-ambiente/'
)
LIMITATIONS = [
    'Cobertura parcial: documentos municipales publicados sobre el PGOU; no registro completo de planeamiento u obras.',
    'Documentación histórica disponible actualmente; no acredita vigencia ni aprobación definitiva.',
    'Sin fechas de acuerdo o aprobación extraídas; las fechas en títulos documentales conservan su contexto.',
    'Sin geometrías verificadas ni licencias concedidas; no se consulta el registro interactivo SITU@.',
]
FULL_NAME = re.compile(r'Plan General de Ordenaci[oó]n (?:Urbana|Urban[ií]stica) de El Carpio', re.I)


def parse_inventory(html: str, url: str = SOURCE_URL) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.entry-content')
    if content is None:
        raise ValueError('Missing municipal inventory content')
    # This source is a static inventory. Refuse a partial result if pagination appears.
    if soup.select('a[rel~=next], link[rel~=next], .page-numbers, .pagination, .page-links'):
        raise ValueError('Inventory pagination requires explicit traversal')
    for a in content.select('a[href]'):
        if re.fullmatch(r'(siguiente|next|ver m[aá]s|cargar m[aá]s|\d+)', a.get_text(' ', strip=True), re.I):
            raise ValueError('Inventory pagination requires explicit traversal')
    documents = {}
    title = None
    for a in content.select('a[href]'):
        label = ' '.join(a.get_text(' ', strip=True).split())
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        if (parsed.scheme != 'https' or parsed.hostname not in {'ayunelcarpio.es', 'www.ayunelcarpio.es'}
                or not parsed.path.startswith('/wp-content/uploads/') or not parsed.path.lower().endswith('.pdf')):
            continue
        # Only the reviewed PGOU environmental-notice family belongs to this inventory.
        # Forms, generic SITU@ links, modifications and other instruments are not PGOU documents.
        if re.search(r'solicitud|modelo|licitaci[oó]n|contrataci[oó]n|modificaci[oó]n|plan parcial', label, re.I):
            continue
        full = FULL_NAME.search(label)
        environmental = full and re.search(r'(estudio|impacto).*ambiental', label, re.I)
        announcement = re.fullmatch(r'Anuncio BOJA PGOU(?:\s+\d{1,2}-\d{1,2}-\d{4})?', label, re.I)
        if not (environmental or announcement):
            continue
        if full:
            title = full.group(0)
        documents.setdefault(target, {'titulo': label, 'url': target, 'source_url': url})
    if not documents or title is None:
        raise ValueError('No identifiable municipal PGOU documentary package')
    instrument_key = 'el-carpio:pgou'
    return [{
        'id': 'el-carpio-plan-' + hashlib.sha256(instrument_key.encode()).hexdigest()[:16],
        'municipio': 'El Carpio', 'provincia': 'Córdoba', 'codigo_ine': '14018',
        'titulo': title, 'tipo': 'planeamiento_urbanistico',
        'url': url, 'inventory_url': url, 'source': 'ayuntamiento',
        'origen': 'inventario_documental_pgou', 'documentos': list(documents.values()),
        'coverage': 'partial_document_inventory', 'limitations': LIMITATIONS,
        'publication_ready': False, 'geometry_status': 'unavailable',
    }]


class ElCarpioAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE_URL, timeout=40, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in {'ayunelcarpio.es', 'www.ayunelcarpio.es'}:
            raise ValueError('Unexpected municipal source redirect')
        rows = parse_inventory(response.text, response.url)
        if self.config.get('capture_dir'):
            captures = Path(self.config['capture_dir'])
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'inventory.html').write_text(response.text, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [response.url],
                'coverage': 'partial_document_inventory', 'limitations': LIMITATIONS,
                'publication_ready': False}

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # A complete refresh of this static page; no synthetic incremental dates.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
