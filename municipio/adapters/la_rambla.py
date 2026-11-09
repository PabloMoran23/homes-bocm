"""Named planning instruments in La Rambla's official document inventory."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE_URL = 'https://larambla.es/ayuntamiento/documentos/'
SECTIONS = ('Instancias y normas subsidiarias', 'Planos de Información',
            'Planos de Ordenación', 'Documentación PGOU')
LIMITATIONS = [
    'Inventario documental actual de cuatro secciones de Urbanismo; no histórico exhaustivo.',
    'No acredita vigencia, aprobación o ejecución actual de los instrumentos.',
    'Sin fechas de publicación/acuerdo verificadas ni geometrías; no se deducen del CMS o las rutas.',
    'Excluye formularios, plano de avance sin instrumento identificado, parcelario, '
    'plan climático, noticias, contratación y actas generales. No incluye el portal separado del PBOM.',
    'Se conservan enlaces documentales; no se analiza el contenido completo de cada PDF.',
]


def _norm(text: str) -> str:
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().casefold().strip()


def _document_url(href: str, base_url: str) -> str:
    url = urljoin(base_url, href)
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname not in {'larambla.es', 'www.larambla.es'}
            or not parsed.path.startswith('/wp-content/uploads/')
            or not parsed.path.lower().endswith('.pdf') or parsed.username or parsed.password):
        raise ValueError(f'Unexpected planning document URL: {url}')
    return url


def parse_inventory(html: str, base_url: str = SOURCE_URL) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    # This reviewed inventory is unpaginated. A changed pagination contract must
    # fail explicitly, before writing any partial extraction.
    if soup.select('.pagination, .wp-pagenavi, .nav-links, a[rel~=next], link[rel~=next]'):
        raise ValueError('Paginated inventory: crawler must be extended before extraction')
    for a in soup.select('a[href]'):
        if (re.search(r'/page/\d+|[?&](?:paged|page)=\d+', a['href'])
                or _norm(a.get_text(' ', strip=True)) in {'siguiente', 'next', 'entradas mas antiguas'}):
            raise ValueError('Paginated inventory: crawler must be extended before extraction')
    rows: dict[str, dict] = {}
    for section in SECTIONS:
        headings = [h for h in soup.select('h3,h4') if h.get_text(' ', strip=True) == section]
        if len(headings) != 1:
            raise ValueError(f'Missing or ambiguous inventory section: {section}')
        content = headings[0].parent.select_one('.et_pb_toggle_content')
        if content is None:
            raise ValueError(f'Missing inventory content: {section}')
        selected = 0
        for a in content.select('a[href]'):
            title = ' '.join(a.get_text(' ', strip=True).split())
            norm = _norm(title)
            if section != SECTIONS[0]:
                group = 'PGOU'
            elif norm.startswith('adaptacion de las normas subsidiarias a la loua'):
                group = re.split(r'\s+[–—-]\s+', title, maxsplit=1)[0]
            elif re.match(r'^(modificaciones en el pgou|plan parcial sector|aprobacion definitiva modificacion nn\.ss\.|nn\.ss\. la rambla|modificacion estudio de detalle|admision a tramite proyecto de actuacion)(?=\s|$)', norm):
                group = title
            else:
                continue
            url = _document_url(a['href'], base_url)
            key = _norm(group)
            if key not in rows:
                rows[key] = {
                    'id': 'la-rambla-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                    'municipio': 'La Rambla', 'codigo_ine': '14057', 'provincia': 'Córdoba',
                    'titulo': group,
                    'tipo': 'proyecto_actuacion' if 'proyecto de actuacion' in key else 'planeamiento_urbanistico',
                    'url': url, 'inventory_url': base_url, 'source': 'ayuntamiento',
                    'origen': 'inventario_documental_urbanismo', 'documentos': [],
                    'publication_ready': False, 'geometry_status': 'unavailable',
                    'coverage': 'partial_current_document_inventory',
                }
            docs = rows[key]['documentos']
            if url not in {d['url'] for d in docs}:
                docs.append({'titulo': title, 'url': url, 'inventory_url': base_url, 'seccion': section})
            selected += 1
        if not selected:
            raise ValueError(f'No supported planning documents in section: {section}')
    if not rows:
        raise ValueError('No named planning instruments found')
    return list(rows.values())


class LaRamblaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE_URL, timeout=45, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)',
        })
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE_URL.rstrip('/'):
            raise ValueError(f'Unexpected inventory redirect: {response.url}')
        # The municipal WordPress document is UTF-8, regardless of HTTP defaults.
        html = response.content.decode('utf-8')
        rows = parse_inventory(html, response.url)
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory.html').write_text(html, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'live_records': len(rows),
                'source_urls': [SOURCE_URL], 'limitations': LIMITATIONS,
                'coverage': 'partial_current_document_inventory', 'publication_ready': False}

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Re-read the entire current inventory. Stable IDs allow downstream deduplication.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
