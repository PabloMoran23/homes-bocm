"""Cabrils' current municipal POUM document inventory, as one instrument."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.cabrils.cat/ajuntament/normativa-municipal/poum'
LIMITATIONS = [
    'Partial coverage: current municipal POUM document page only; no historical or amendment inventory.',
    'No verified public register of granted licences; licences disabled.',
    'Agreement, approval and publication dates are not stated on this inventory; left null.',
    'Document contents and geometry are not parsed; no coordinates inferred.',
]


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1')
    blocks = [b for b in soup.select('.ddbbtext')
              if 'documentació relativa al POUM vigent actualment' in b.get_text(' ', strip=True)]
    if not heading or heading.get_text(' ', strip=True) != 'POUM' or len(blocks) != 1:
        raise ValueError('Expected the current Cabrils POUM document inventory')
    block = blocks[0]
    # This source is a single document page. A new pager requires crawler review.
    if soup.select('[rel~=next], .pagination, .paginacio, .pager'):
        raise ValueError('Unexpected pagination: refusing an incomplete POUM inventory')
    docs = {}
    for a in block.select('a[href]'):
        label = a.get_text(' ', strip=True)
        if label.casefold() in {'següent', 'següents', 'siguiente', 'next', 'més', 'veure més'}:
            raise ValueError('Unexpected continuation link in POUM inventory')
        target = urljoin(SOURCE, a['href'])
        parsed = urlsplit(target)
        if (parsed.scheme != 'https' or parsed.netloc != 'www.cabrils.cat'
                or not parsed.path.startswith('/media/repository/POUM/') or not label):
            raise ValueError('Unreviewed link in POUM document inventory: ' + target)
        # Repeated links are documents of this plan, never separate projects.
        if target in docs:
            if label not in docs[target]['titulos_fuente']:
                docs[target]['titulos_fuente'].append(label)
        else:
            docs[target] = {'titulo': label, 'titulos_fuente': [label], 'url': target,
                            'source_url': SOURCE}
    if not any(urlsplit(u).path.endswith('/Normes_urbanistiques.pdf') for u in docs):
        raise ValueError('Missing the principal POUM norms document')
    if len(docs) < 2:
        raise ValueError('Incomplete POUM document inventory')
    updated = soup.select_one('.updated')
    source_updated = None
    if updated:
        value = updated.get_text(' ', strip=True).removeprefix('Darrera actualització:').strip()
        source_updated = datetime.strptime(value, '%d.%m.%Y | %H:%M').date().isoformat()
    return [{
        'id': 'cabrils-proy-' + hashlib.sha256(SOURCE.encode()).hexdigest()[:16],
        'municipio': 'Cabrils', 'codigo_ine': '08030', 'provincia': 'Barcelona',
        'titulo': "Pla d'Ordenació Urbanística Municipal de Cabrils (POUM)",
        'tipo': 'POUM', 'fase': 'vigente',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'fecha_actualizacion_fuente': source_updated,
        'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_documental_poum_vigente',
        'documentos': list(docs.values()),
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'unavailable', 'coverage': 'current_poum_document_inventory',
        'limitations': LIMITATIONS.copy(),
    }]


class CabrilsAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.cabrils.cat')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=35, stream=True,
                          headers={'User-Agent': 'municipio-cabrils/1.0'}) as response:
            response.raise_for_status()
            if response.url.rstrip('/') != SOURCE:
                raise ValueError('Unexpected POUM source redirect')
            if 'text/html' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('POUM source is not HTML')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 2_000_000:
                    raise ValueError('POUM response exceeds reviewed size; refusing truncation')
        html = content.decode('utf-8')
        rows = parse_inventory(html)
        capture = self.config.get('capture_dir')
        if capture:
            capture = Path(capture)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'poum.html').write_text(html, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'documents': len(rows[0]['documentos']), 'limitations': LIMITATIONS.copy(),
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Refresh the complete single-instrument snapshot, including all attachments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': LIMITATIONS[1]}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
