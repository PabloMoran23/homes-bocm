"""Colindres municipal planning-document inventory (not a licence register)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.colindres.es/index.php/normativa/urbanismo/'


def parse_inventory(html: str) -> list[dict]:
    """Resolve Divi's JSON click targets without executing website JavaScript."""
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('[rel~=next], .pagination, .nav-links, .wp-pagenavi') or any(
        a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'más resultados'}
        for a in soup.select('a[href]')
    ):
        raise ValueError('Inventory pagination detected; coverage must be reviewed')
    heading = next((h for h in soup.select('h1') if re.fullmatch(
        r'Plan General de Ordenación Urbana 1964\s*:', h.get_text(' ', strip=True))), None)
    if heading is None:
        raise ValueError('Missing municipal PGOU heading')
    inventory = heading.find_next(class_='et_pb_accordion')
    assignments = re.findall(r'\bvar\s+et_link_options_data\s*=\s*(\[.*?\])\s*;', html, re.S)
    if inventory is None or len(soup.select('.et_pb_accordion')) != 1 or len(assignments) != 1:
        raise ValueError('Missing or ambiguous Divi inventory')
    targets = {}
    for entry in json.loads(assignments[0]):
        key = entry['class']
        if key in targets and targets[key] != entry['url']:
            raise ValueError('Conflicting document target')
        targets[key] = entry['url']
    represented = {c for block in inventory.select('.et_pb_accordion_item') for c in block.get('class', [])}
    if any(c.startswith('et_pb_accordion_item_') and c not in represented for c in targets):
        raise ValueError('Document targets outside the reviewed inventory')
    groups = {}
    for block in inventory.select('.et_pb_accordion_item'):
        title_node = block.select_one('.et_pb_toggle_title')
        if title_node is None:
            raise ValueError('Untitled planning document')
        title = title_node.get_text(' ', strip=True)
        urls = {urljoin(SOURCE, targets[c]) for c in block.get('class', []) if c in targets}
        if len(urls) != 1:
            raise ValueError('Missing or ambiguous planning document URL')
        url = urls.pop()
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'www.colindres.es' or not parsed.path.startswith('/wp-content/uploads/') or not parsed.path.lower().endswith('.pdf') or parsed.query or parsed.fragment:
            raise ValueError('Unexpected document origin or format')
        if title == 'NORMAS URBANÍSTICAS' or title.startswith(('PLANO ', 'DIVISIÓN EN POLÍGONOS')):
            key, record_title = 'pgou-1964', 'Plan General de Ordenación Urbana 1964'
        elif re.match(r'^MODIFIC(?:ACION|ION) PUNTUAL\b', title):
            key = 'mod-' + hashlib.sha256(url.encode()).hexdigest()[:16]
            record_title = title
        else:
            raise ValueError('Unreviewed inventory entry: ' + title)
        group = groups.setdefault(key, {'titulo': record_title, 'docs': {}})
        group['docs'].setdefault(url, {'titulo': title, 'url': url, 'url_procedencia': SOURCE})
    plan = groups.get('pgou-1964')
    if not plan or not any(d['titulo'] == 'NORMAS URBANÍSTICAS' for d in plan['docs'].values()) or not any(d['titulo'].startswith('PLANO ') for d in plan['docs'].values()):
        raise ValueError('Incomplete PGOU document inventory')
    rows = []
    for key, group in groups.items():
        docs = list(group['docs'].values())
        rows.append({
            'id': 'colindres-proy-' + key, 'municipio': 'Colindres',
            'codigo_ine': '39023', 'provincia': 'Cantabria',
            'titulo': group['titulo'], 'tipo': 'planeamiento_urbanistico',
            'url': SOURCE, 'url_documento': docs[0]['url'], 'documentos': docs,
            'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'fase': None,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'cobertura': 'Inventario documental municipal; sin verificación de vigencia jurídica ni fechas de acuerdo. No incluye todo el planeamiento ni obras ni licencias.',
        })
    return rows


class ColindresAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        tmp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE]}

    def backfill_proyectos(self, out_jsonl):
        with requests.get(SOURCE, timeout=40, stream=True, headers={
            'User-Agent': 'municipio-colindres/1.0'
        }) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Planning inventory exceeds response limit')
                chunks.append(chunk)
            content = b''.join(chunks)
        rows = parse_inventory(content.decode('utf-8'))
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo-live.html').write_bytes(content)
        return self._write(out_jsonl, rows)

    def update_proyectos(self, out_jsonl, state_path):
        # Complete replacement: this source is a single unpaginated document index.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
