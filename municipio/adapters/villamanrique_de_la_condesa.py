"""Named projects from the municipal transparency document inventory."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = (
    'https://transparencia.villamanriquedelacondesa.es/es/transparencia/'
    'indicadores-de-transparencia/indicador/Usos-y-destinos-del-suelo-00024/'
)
HOST = urlparse(SOURCE).hostname
DOCUMENT_PREFIX = '/export/sites/villamanriquedelacondesa/es/transparencia/.galleries/'


def normalize(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if unicodedata.category(c) != 'Mn')


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    """One gallery per instrument; never infer approval from attached notices."""
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href]'):
        if a['href'].strip() in {'', '#'}:
            continue
        label = normalize(a.get_text(' ', strip=True) + ' ' + a.get('aria-label', '')
                          + ' ' + a.get('title', ''))
        if (a.find_parent(class_=re.compile(r'pagination|pager', re.I))
                or 'next' in a.get('rel', [])
                or re.search(r'\b(siguiente|next|ultima pagina)\b', label)
                or re.search(r'[?&](?:page|pagina|offset|start)=', a['href'], re.I)):
            raise ValueError('Pagination detected: extend inventory traversal before extraction')

    rows = {}
    for section in soup.select('section.gallery'):
        heading = section.select_one('h4.gallery-title')
        if heading is None:
            continue
        title = heading.get_text(' ', strip=True)
        if not re.match(r'^proyecto (?:de )?actuacion\b', normalize(title)):
            continue
        documents = {}
        for a in section.select('a[href]'):
            url = urljoin(source_url, a['href'])
            parsed = urlparse(url)
            if (parsed.scheme != 'https' or parsed.hostname != HOST
                    or not parsed.path.startswith(DOCUMENT_PREFIX)
                    or not parsed.path.lower().endswith('.pdf')):
                continue
            label = a.get_text(' ', strip=True) or unquote(parsed.path.rsplit('/', 1)[-1])
            documents.setdefault(url, {'titulo': label, 'url': url})
        # An announcement alone does not constitute a project dossier.
        substantive = [d for d in documents.values()
                       if re.search(r'proyecto|memoria', normalize(d['titulo']))]
        if not substantive:
            raise ValueError(f'Project gallery lacks project/memoria document: {title}')
        identity = normalize(title)
        row = {
            'id': 'villamanrique-de-la-condesa-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:20],
            'municipio': 'Villamanrique de la Condesa', 'codigo_ine': '41097',
            'provincia': 'Sevilla', 'titulo': title, 'tipo': 'proyecto_de_actuacion',
            'url': substantive[0]['url'], 'inventory_url': source_url,
            'source': 'ayuntamiento', 'origen': 'inventario_usos_y_destinos_del_suelo',
            'documentos': list(documents.values()),
            'publication_ready': False, 'geometry_status': 'unavailable',
        }
        if identity in rows:
            raise ValueError(f'Duplicate project heading requires review: {title}')
        rows[identity] = row
    if not rows:
        raise ValueError('No supported project galleries found in official inventory')
    return list(rows.values())


def write_rows(path: Path, rows: list[dict]) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    temporary.replace(path)
    return {'count': len(rows), 'written': len(rows)}


class VillamanriqueDeLaCondesaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'municipio-inventory/1.0 (public municipal planning documents)',
        })
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE.rstrip('/'):
            raise ValueError(f'Unexpected inventory redirect: {response.url}')
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Inventory did not return HTML')
        rows = parse_inventory(response.text, response.url)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'usos-y-destinos.html').write_text(response.text, encoding='utf-8')
        return {**write_rows(out_jsonl, rows), 'coverage': 'current_project_document_inventory',
                'source_urls': [response.url], 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full snapshot: the source exposes no reliable modification timestamps.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**write_rows(out_jsonl, []), 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
