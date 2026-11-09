"""Puig-reig's five municipal transparency document inventories.

A snapshot of listed instruments, not a register of approvals or licences.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.seu-e.cat/ca/web/puig-reig/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/'
INVENTORIES = {
    'planejament-urbanistic': 'planeamiento_urbanistico',
    'projectes-d-urbanitzacio-199': 'proyecto_urbanizacion',
    'projectes-d-obra-local-202': 'obra_publica',
    'projectes-de-reparcel-lacio-198': 'reparcelacion',
    'projectes-d-actuacio-especifica-197': 'actuacion_especifica',
}
LIMITATIONS = [
    'Partial coverage: only the five municipal transparency inventories; not all historical dossiers, RPUC, notices or minutes.',
    'Inventory update dates are page metadata, not publication, agreement or approval dates; those dates remain null.',
    'Phase labels describe the listed document, not a verified current legal status; inventories may lag later agreements.',
    'Linked PDFs and RPUC dossier are retained; their contents, approval dates and geometry are not parsed.',
    'No verified coordinates or project geometry; publication_ready is false. No granted licences extracted.',
]


def _text(node):
    return node.get_text(' ', strip=True)


def _document(url, label, source):
    parsed = urlparse(url)
    valid_pdf = parsed.hostname in {'www.seu-e.cat', 'seu-e.cat'} and parsed.path.startswith('/documents/2846680/')
    valid_rpuc = parsed.hostname == 'dtes.gencat.cat' and parsed.path == '/rpucportal/' and 'consulta/' in parsed.fragment
    if parsed.scheme != 'https' or not (valid_pdf or valid_rpuc):
        raise ValueError(f'Unreviewed document target: {url}')
    return {'titulo': label, 'url': url, 'source_url': source,
            'provenance': 'Enlace del inventario municipal; contenido documental no analizado'}


class PuigReigAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='puig-reig', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.seu-e.cat/ca/web/puig-reig')

    @staticmethod
    def parse_inventory(html: str, inventory: str) -> list[dict]:
        tipo = INVENTORIES[inventory]
        source = BASE + inventory
        soup = BeautifulSoup(html, 'html.parser')
        # Current pages are complete static lists. Fail if pagination appears,
        # rather than returning only the first page of a changed inventory.
        if soup.select('a[rel~=next], .pagination a[href], .pager a[href], .lfr-pagination a[href]'):
            raise ValueError('Pagination detected; crawler must be extended')
        for a in soup.select('a[href]'):
            if re.fullmatch(r'(següent|següents|siguiente|next|›|»)', _text(a), re.I) and a['href'] not in {'', '#'}:
                raise ValueError('Pagination detected; crawler must be extended')
        blocks = [b for b in soup.select('.journal-content-article') if b.select_one('.datatable_info_footer')]
        if len(blocks) != 1:
            raise ValueError('Expected one complete municipal document inventory')
        block = blocks[0]
        footer = _text(block.select_one('.datatable_info_footer'))
        match = re.search(r'Actualització:\s*(\d{2}/\d{2}/\d{4})', footer)
        updated = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None
        rows = {}

        def consume(li):
            own = ' '.join(_text(n) if getattr(n, 'name', None) else str(n).strip()
                           for n in li.contents if getattr(n, 'name', None) not in {'ul', 'ol'})
            title = ' '.join(own.split())
            if title.casefold() == 'plans parcials':
                children = li.select(':scope > ul > li, :scope > ol > li')
                if not children:
                    raise ValueError('Empty planning category')
                for child in children:
                    consume(child)
                return
            if not re.match(r"^(Pla |Modificació POUM |Projecte |Reparcel·lació |PAE )", title):
                raise ValueError(f'Unreviewed inventory entry: {title}')
            docs = {}
            for a in li.select('a[href]'):
                url = urljoin(source, a['href'])
                docs[url] = _document(url, _text(a), source)
            if not docs:
                raise ValueError(f'Instrument without documents: {title}')
            key = title.casefold()
            if key in rows:
                existing = {d['url']: d for d in rows[key]['documentos']}
                existing.update(docs)
                rows[key]['documentos'] = list(existing.values())
                return
            phase = 'aprobación inicial' if any(_text(a).casefold() == 'aprovació inicial' for a in li.select('a')) else None
            rows[key] = {
                'id': 'puig-reig-proy-' + hashlib.sha256((inventory + ':' + key).encode()).hexdigest()[:16],
                'municipio': 'Puig-reig', 'provincia': 'Barcelona', 'codigo_ine': '08175',
                'titulo': title, 'tipo': tipo, 'fase': phase,
                'fase_alcance': 'Etiqueta del documento listado; no acredita el estado vigente',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'fecha_actualizacion_fuente': updated,
                'url': source, 'url_documento': next(iter(docs)), 'documentos': list(docs.values()),
                'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
                'source_entity_type': 'documento',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'coverage': 'Inventario municipal parcial; documentos enlazados sin analizar',
            }

        for li in block.select('ul > li, ol > li'):
            if li.find_parent('li') is None:
                consume(li)
        if not rows:
            raise ValueError('No genuine instruments found in inventory')
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = []
        for inventory in INVENTORIES:
            url = BASE + inventory
            with requests.get(url, timeout=(15, 45), stream=True,
                              headers={'User-Agent': 'municipio-puig-reig/1.0'}) as response:
                response.raise_for_status()
                if urlparse(response.url).hostname not in {'www.seu-e.cat', 'seu-e.cat'}:
                    raise ValueError('Unexpected inventory redirect')
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > 5_000_000:
                        raise ValueError('Inventory exceeds response limit')
                html = content.decode('utf-8')
            rows.extend(self.parse_inventory(html, inventory))
            if self.config.get('capture_dir'):
                capture = Path(self.config['capture_dir'])
                capture.mkdir(parents=True, exist_ok=True)
                (capture / (inventory + '.html')).write_bytes(content)
        # Write only when all five inventories were successfully parsed.
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [BASE + s for s in INVENTORIES],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'Granted licence extraction is outside verified coverage'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
