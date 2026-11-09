"""Quart's official transparency inventory: POUM and mobility planning study."""
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

SOURCE = ('https://seu-e.cat/ca/web/quart/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme')
HEADERS = ['Normativa', 'Data de publicació', 'Enllaç', 'Documents', 'Més informació']


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    tables = [t for t in soup.find_all('table')
              if [h.get_text(' ', strip=True) for h in t.select('thead th')] == HEADERS]
    if len(tables) != 1:
        raise ValueError('Quart inventory table missing or ambiguous')
    table = tables[0]
    # All rows are embedded in HTML; DataTables only paginates in the browser.
    # Reject a transition to remote pagination instead of returning a first page.
    for script in soup.find_all('script'):
        code = script.get_text()
        if table.get('id', '__missing__') in code and re.search(
                r'[\"\']?(?:serverSide|bServerSide)[\"\']?\s*:\s*true|'
                r'[\"\']?(?:ajax|sAjaxSource)[\"\']?\s*:', code, re.I):
            raise ValueError('Remote inventory pagination requires investigation')
    if soup.select('a[rel~=next]'):
        raise ValueError('Unexpected next page; inventory may be incomplete')

    records = {}
    for tr in table.select('tbody tr'):
        # The live source omits closing tr tags. Direct cells avoid absorbing
        # following instruments when html.parser preserves nested rows.
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 5:
            raise ValueError('Unexpected Quart inventory row schema')
        title = cells[0].get_text(' ', strip=True)
        if re.match(r"^PLA D['’]ORDENACIÓ URBAN[IÍ]STICA MUNICIPAL\b", title, re.I):
            kind = 'POUM'
        elif re.match(r"^Estudi d['’]ordenació de la mobilitat al municipi de Quart\b", title, re.I):
            kind = 'estudio de movilidad'
        else:
            # Road/tree inventories, forms and unrelated rows are not projects.
            continue
        raw_date = cells[1].get_text(' ', strip=True)
        publication = datetime.strptime(raw_date, '%d-%m-%Y').date().isoformat() if raw_date else None
        documents = []
        for cell, role in ((cells[2], 'referencia'), (cells[3], 'documento')):
            for a in cell.select('a[href]'):
                target = urljoin(SOURCE, a['href'])
                if urlparse(target).scheme != 'https' or urlparse(target).hostname not in {
                    'seu-e.cat', 'www.seu-e.cat', 'www.quart.cat', 'dogc.gencat.cat'
                }:
                    raise ValueError('Unexpected instrument document origin')
                doc = {'titulo': a.get_text(' ', strip=True), 'url': target,
                       'rol': role, 'source_url': SOURCE}
                if doc not in documents:
                    documents.append(doc)
        primary = next((d['url'] for d in documents if d['rol'] == 'documento'), None)
        if not primary:
            raise ValueError('Planning instrument lacks its document')
        description = cells[4].get_text(' ', strip=True)
        key = 'quart-plan-' + hashlib.sha256(primary.encode()).hexdigest()[:16]
        record = {
            'id': key, 'municipio': 'Quart', 'provincia': 'Girona', 'codigo_ine': '17142',
            'titulo': title, 'tipo': kind,
            'fase': 'aprobación definitiva' if 'aprovació definitiva' in description.lower() else None,
            'fecha': None, 'fecha_publicacion': publication,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'fecha_publicacion_provenance': {'url': SOURCE, 'campo': 'Data de publicació'},
            'descripcion': description or None,
            'url': SOURCE, 'url_documento': primary, 'documentos': documents,
            'source': 'ayuntamiento', 'origen': 'inventario_normativa_urbanisme',
            'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'geometry_status': 'unavailable',
        }
        if key in records and records[key] != record:
            raise ValueError('Conflicting entries for one instrument')
        records[key] = record
    if not records:
        raise ValueError('No usable Quart planning instruments in inventory')
    return list(records.values())


class QuartAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.quart.cat')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-quart/1.0')})
        response.raise_for_status()
        if urlparse(response.url).hostname not in {'seu-e.cat', 'www.seu-e.cat'}:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'live-inventory.html').write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'POUM and mobility study in current transparency inventory',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete snapshot; no date watermark drops older, still listed plans.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
