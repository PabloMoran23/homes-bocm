"""Inventario documental municipal de Beas; no infiere vigencia ni acuerdos."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

INVENTORY_URL = 'https://www.aytobeas.es/es/ayuntamiento/publicaciones-oficiales/Planeamiento-Urbanistico/'
DOCUMENT_ROOT = '/export/sites/beas/es/.galleries/documentos/publicaciones-oficiales/Normativas/Planeamiento_Urbanistico/'
HOST = 'www.aytobeas.es'
LIMITATIONS = [
    'Solo inventario documental municipal de planeamiento; no cobertura exhaustiva de actuaciones ni de fuentes autonómicas.',
    'No se extraen fechas de publicación o acuerdo, vigencia, fase ni geometría de los documentos PDF.',
    'Los años de los títulos son etiquetas del inventario, no fechas de aprobación.',
    'Sin registro verificado de licencias concedidas; licencias desactivadas.',
]


def parse_inventory(html: str, url: str = INVENTORY_URL) -> list[dict]:
    """Agrupa cada galería por carpeta del instrumento, reteniendo todos sus PDF."""
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('.pagination, .pager, a[rel~=next], a[rel~=prev]') or any(
        re.search(r'\b(siguiente|next|página siguiente)\b', a.get_text(' ', strip=True), re.I)
        for a in soup.select('a[href]')
    ):
        raise ValueError('Paginación detectada: revisar cobertura antes de extraer')
    groups = {}
    for gallery in soup.select('.sg-download-gallery'):
        heading = gallery.find('h4')
        if heading is None:
            raise ValueError('Galería sin título')
        title = heading.get_text(' ', strip=True)
        if not re.match(r'^\d+\s+(NNSS|MODIFICACI[OÓ]N|ADP\s+LOUA)\b', title, re.I):
            continue
        documents = []
        folders = set()
        for a in gallery.select('table a[href]'):
            target = urljoin(url, a['href'])
            parsed = urlsplit(target)
            if (parsed.scheme != 'https' or parsed.hostname != HOST
                    or not parsed.path.startswith(DOCUMENT_ROOT)
                    or not parsed.path.lower().endswith('.pdf')):
                raise ValueError(f'Documento fuera del inventario esperado: {target}')
            relative = parsed.path[len(DOCUMENT_ROOT):].split('/')
            if len(relative) != 2 or not relative[0]:
                raise ValueError('Carpeta de instrumento no reconocida')
            folders.add(relative[0])
            label = a.get_text(' ', strip=True)
            if not label:
                raise ValueError('Documento sin título')
            if target not in {d['url'] for d in documents}:
                documents.append({'titulo': label, 'url': target, 'source_url': url})
        if len(folders) != 1 or not documents:
            raise ValueError(f'Galería vacía o mezcla de instrumentos: {title}')
        folder = folders.pop()
        if folder in groups:
            raise ValueError('Instrumento duplicado en varias galerías')
        groups[folder] = {
            'id': 'beas-plan-' + hashlib.sha256(folder.encode()).hexdigest()[:16],
            'titulo': title, 'municipio': 'Beas', 'provincia': 'Huelva',
            'codigo_ine': '21011', 'tipo': 'instrumento de planeamiento urbanístico',
            'url': documents[0]['url'], 'inventory_url': url,
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'documentos': documents, 'source_group': folder,
            'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'inventario_documental_parcial',
        }
    if not groups:
        raise ValueError('Inventario sin instrumentos documentados')
    return list(groups.values())


class BeasAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        # La excepción TLS debe ser explícita en config; no hay fallback silencioso.
        verify = self.config.get('tls_verify', True)
        response = requests.get(INVENTORY_URL, timeout=60, verify=verify,
                                headers={'User-Agent': 'municipio-beas-inventory/1.0'})
        response.raise_for_status()
        if urlsplit(response.url).hostname != HOST or urlsplit(response.url).path != urlsplit(INVENTORY_URL).path:
            raise ValueError('Redirección inesperada del inventario')
        rows = parse_inventory(response.text, response.url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory.html').write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        limitations = list(LIMITATIONS)
        if verify is False:
            limitations.append('Extracción con tls_verify=false explícito por fallo de cadena de certificados; autenticidad TLS no verificada.')
        return {'count': len(rows), 'written': len(rows),
                'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': [response.url], 'limitations': limitations,
                'publication_ready': False, 'coverage': 'inventario_documental_parcial',
                'tls_verified': verify is not False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Instantánea completa del inventario actual, sin filtro temporal.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'Sin registro verificado de concesiones'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
