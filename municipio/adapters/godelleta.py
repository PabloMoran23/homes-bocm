"""Public Godelleta planning document inventories, grouped by instrument."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'godelleta.sedelectronica.es'
ROOT = f'https://{HOST}/transparency/91b974bb-49e4-4d13-9c0b-6d47031b3e25/'
INVENTORIES = (
    (f'https://{HOST}/transparency/9938a00f-d636-4ad2-b379-b82959755654/', '7.1.'),
    (f'https://{HOST}/transparency/1345e6e0-114f-4b8e-9726-122966d57941/', '7.3.'),
)
LIMITATIONS = [
    'Partial coverage: only public planning and urban planning regulations inventories (7.1 and 7.3).',
    'Documents represent an instrument, not granted licences, verified current legal force or completed works.',
    'No verified publication/agreement/approval dates or project geometry extracted; document creation dates are not approval dates.',
    'Original document labels can contain numbering errors; inventory title attributes and the correction document are retained.',
    'Other municipal inventories, historical notices and DOGV are not exhaustively crawled.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    if 'Sede Electrónica de Godelleta' not in soup.get_text(' ', strip=True):
        raise ValueError('Unexpected municipality or login/error page')
    table = soup.select_one('table.TransparencyListPanel')
    if table is None:
        raise ValueError('Missing transparency inventory')
    # Never return a first page as if it were the whole inventory. The current
    # source has no pagination; changed/paginated layouts require investigation.
    for node in soup.select('[rel~=next], .pagination, .navigator, .paging, [class*=PagingNavigator]'):
        if 'display:none' not in node.get('style', '').replace(' ', ''):
            raise ValueError('Pagination detected; refusing incomplete snapshot')
    return soup, table


def parse_inventory(html: str, url: str, section: str) -> list[dict]:
    soup, table = _soup(html)
    content = soup.select_one('#content')
    if content is None or section not in content.get_text(' ', strip=True):
        raise ValueError('Unexpected inventory section')
    if table.select('a.exp'):
        raise ValueError('Nested folders require traversal; refusing partial inventory')
    documents = []
    for anchor in table.select('a.gIconLink[href]'):
        target = urljoin(url, anchor['href'])
        parsed = urlparse(target)
        if parsed.scheme != 'https' or parsed.hostname != HOST or not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', parsed.path):
            raise ValueError('Unexpected document link')
        label = anchor.get_text(' ', strip=True)
        title = anchor.get('title', '')
        # Title is the municipal instrument description. Display labels include
        # an old erroneous number and generic names such as "Planos".
        match = re.search(r'MODIFICACI[ÓO]N\s+PUNTUAL\s+N[º°o.]?\s*(\d+)\b', title, re.I)
        documents.append({'url': target, 'titulo': label, 'descripcion_fuente': title,
                          'inventory_url': url, 'instrument_number': match[1] if match else None})
    numbers = {d['instrument_number'] for d in documents if d['instrument_number']}
    if not documents or len(numbers) != 1:
        raise ValueError('Empty or ambiguous instrument inventory')
    # Unlabelled documents can only be attached in a single-instrument folder.
    number = next(iter(numbers))
    for document in documents:
        document['instrument_number'] = number
    return documents


def group_documents(documents: list[dict]) -> list[dict]:
    groups = {}
    for document in documents:
        groups.setdefault(document['instrument_number'], {})[document['url']] = document
    rows = []
    for number, docs in sorted(groups.items()):
        rows.append({
            'id': f'godelleta-pgou-modificacion-{number}',
            'municipio': 'Godelleta', 'codigo_ine': '46136', 'provincia': 'Valencia',
            'titulo': f'Modificación puntual nº {number} del PGOU de Godelleta',
            'tipo': 'modificación puntual del planeamiento general',
            'url': ROOT, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'descripcion': 'Instrumento documentado en los inventarios municipales de planeamiento y normativa urbanística.',
            'documentos': list(docs.values()),
            'source_urls': sorted({d['inventory_url'] for d in docs.values()}),
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False, 'coverage': 'partial_current_document_inventory',
        })
    if not rows:
        raise ValueError('No usable planning instruments')
    return rows


class GodelletaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        captures = self.config.get('capture_dir')
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-godelleta/1.0'

            def fetch(url, name):
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if urlparse(response.url).hostname != HOST or urlparse(response.url).path != urlparse(url).path:
                    raise ValueError('Unexpected inventory redirect')
                if captures:
                    folder = Path(captures)
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / name).write_bytes(response.content)
                source_urls.append(url)
                return response.text

            parent, table = _soup(fetch(ROOT, 'urbanismo.html'))
            counts = {}
            for a in table.select('a.exp'):
                text = a.get_text(' ', strip=True)
                for _, section in INVENTORIES:
                    if text.startswith(section):
                        match = re.search(r'\(\s*(\d+)\s*\)\s*$', text)
                        if match:
                            counts[section] = int(match[1])
            docs = []
            for index, (url, section) in enumerate(INVENTORIES):
                parsed = parse_inventory(fetch(url, f'inventory-{index}.html'), url, section)
                if counts.get(section) != len(parsed):
                    raise ValueError('Parent document count mismatch; possible incomplete inventory')
                docs.extend(parsed)
        rows = group_documents(docs)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'documents': len(docs),
                'source_urls': source_urls, 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
