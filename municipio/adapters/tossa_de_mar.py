"""Snapshot of Tossa's public technical-project document inventory."""
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

SOURCE = ('https://tossademar.eadministracio.cat/transparency/'
          '51471d1c-4688-4527-a683-90c502316644/')
LIMITATIONS = [
    'Partial coverage: top-level technical-project documents in the municipal '
    'projects-in-processing inventory only; not all planning or public works.',
    'Inventory context does not establish current procedural status, approval, '
    'agreement or publication dates; document creation dates are not used.',
    'No verified project geometry or coordinates; publication_ready is false.',
    'No granted-licence register extracted. Ordinances and procurement excluded.',
    'Document preview links retained; PDF contents are not parsed.',
]


def _norm(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                   if not unicodedata.combining(c))


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content')
    if content is None or 'projectes en tramitacio' not in _norm(content.get_text(' ', strip=True)):
        raise ValueError('Missing municipal projects-in-processing inventory')
    tables = content.select('table.TransparencyListPanel')
    if len(tables) != 1:
        raise ValueError('Missing or ambiguous document table')
    # This inventory currently has no pagination. Fail closed if controls appear:
    # Wicket AJAX navigation must be investigated before claiming a full snapshot.
    for node in content.find_all(True):
        attrs = ' '.join(str(node.get(k, '')) for k in ('class', 'id', 'rel', 'aria-label'))
        label = _norm(node.get_text(' ', strip=True)) if node.name in ('a', 'button') else ''
        if (re.search(r'pagin|navigator|\bnext\b|\bload.more\b', attrs, re.I)
                or label in {'seguent', 'seguent pagina', 'siguiente', 'next', 'mes resultats', 'carrega mes'}):
            raise ValueError('Pagination detected: refusing a truncated inventory')
    records = {}
    seen = set()
    for anchor in tables[0].select('a.gIconLink'):
        label = anchor.get_text(' ', strip=True)
        normalized = _norm(label)
        # Project document titles start PROJECTE; ordinances, forms, tenders and
        # generic navigation never qualify as technical projects.
        if not re.match(r'^projecte(?:[\s_-]|$)', normalized):
            continue
        if re.search(r'\b(licitacio|contractacio|anunci|sol.licitud|formulari)\b', normalized):
            continue
        target = urljoin(source_url, anchor.get('href', ''))
        parsed = urlparse(target)
        if (parsed.scheme != 'https' or parsed.netloc != 'tossademar.eadministracio.cat'
                or not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', parsed.path)
                or parsed.query or parsed.fragment):
            raise ValueError('Project lacks a stable official document preview URL')
        if target in seen:
            continue
        seen.add(target)
        # Group document variants and numbered phases under their named work;
        # retain each unmodified source label and URL below.
        title = re.split(r'_Proj_', label, maxsplit=1, flags=re.I)[0]
        title = re.sub(r'\s*-\s*Fase\s+\d+\s*$', '', title, flags=re.I)
        key = _norm(title).replace('_', ' ')
        key = re.sub(r'[\s-]+', ' ', key).strip()
        if key not in records:
            records[key] = {
                'id': 'tossa-de-mar-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Tossa de Mar', 'codigo_ine': '17202', 'provincia': 'Girona',
                'titulo': title, 'tipo': 'proyecto técnico de obra', 'fase': None,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'source': 'ayuntamiento', 'origen': 'inventario_proyectos_tecnicos',
                'url': source_url, 'inventory_url': source_url,
                'contexto_publicacion': 'Projectes en tramitació (rótulo del inventario)',
                'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'geometry_status': 'unavailable',
            }
        records[key]['documentos'].append({'titulo': label, 'url': target, 'source_url': source_url})
    if not records:
        raise ValueError('No genuine technical-project documents found')
    for row in records.values():
        row['documentos'].sort(key=lambda d: d['url'])
        row['url_documento'] = row['documentos'][0]['url']
    return sorted(records.values(), key=lambda row: row['id'])


class TossaDeMarAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='tossa-de-mar', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.tossademar.cat')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=40, stream=True, headers={
            'User-Agent': 'municipio-tossa-de-mar/1.0 (public project inventory)',
        }) as response:
            response.raise_for_status()
            if response.url != SOURCE:
                raise ValueError('Unexpected inventory redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Inventory response exceeds 3 MB')
                chunks.append(chunk)
            body = b''.join(chunks)
            html = body.decode('utf-8')
        rows = parse_inventory(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'live-inventory.html').write_bytes(body)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows),
                'documents': sum(len(row['documentos']) for row in rows),
                'source_urls': [SOURCE], 'limitations': LIMITATIONS,
                'coverage': 'current top-level technical-project inventory snapshot',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete refresh; no timestamp cursor exists in the source inventory.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
