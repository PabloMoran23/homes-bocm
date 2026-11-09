"""Physical interventions in Ribadesella's official PRTR project inventory.

This is a snapshot of the published inventory, not an execution/approval register.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.ayto-ribadesella.es/proyectos-financiados-en-el-ayuntamiento-de-ribadesella'
CODE = re.compile(r'C\d{2}(?:\.[A-Z0-9]+)+')
INCLUDED = (
    'CIUDADES SALUDABLES', 'RECOGIDA DE BIORRESIDUOS',
    'MEJORA DE LA EFICIENCIA', 'MEJORA DE LA ACCESIBILIDAD',
    'REHABILITACIÓN RESIDENCIAL',
)
EXCLUDED = ('PLAN DE SOSTENIBILIDAD TURÍSTICA', 'COMPRA DE LIBROS', 'AULA MENTOR')


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    for article in soup.select('.journal-content-article'):
        heading = article.select_one('.titulo h2')
        if heading and text(heading) == 'Proyectos Financiados en el Ayuntamiento de Ribadesella':
            articles.extend(article.select('.detalle'))
    if len(articles) != 1:
        raise ValueError('Expected one municipal project inventory article')
    # The reviewed inventory is one complete article. Fail on new pagination.
    for a in soup.select('a[href]'):
        if (set(a.get('rel', [])) & {'next'} or
                re.search(r'^(siguiente|next|siguiente página|›|»)$', text(a), re.I) or
                re.search(r'[?&](?:[^=&]*_cur|page|start)=', a['href'], re.I)):
            raise ValueError('Pagination detected; review traversal before extraction')
    blocks = []
    current = None
    for p in articles[0].find_all('p', recursive=False):
        value = text(p)
        heading = p.find(['b', 'strong'])
        if heading and value == text(heading) and value:
            current = {'title': value, 'parts': [], 'docs': {}}
            blocks.append(current)
        elif current is not None:
            if value:
                current['parts'].append(value)
            for a in p.select('a[href]'):
                target = urljoin(url, a['href'])
                if urlparse(target).scheme in {'http', 'https'}:
                    current['docs'][target] = {'titulo': text(a), 'url': target,
                                               'procedencia': url}
    rows = {}
    for block in blocks:
        title = block['title']
        upper = title.upper()
        if not upper.startswith(INCLUDED + EXCLUDED):
            raise ValueError(f'Unreviewed project section: {title}')
        if not block['parts']:
            raise ValueError(f'Missing project content: {title}')
        code = re.sub(r'\s+', '', block['parts'][0])
        if not CODE.fullmatch(code):
            raise ValueError(f'Missing PRTR reference: {title}')
        if upper.startswith(EXCLUDED):
            continue
        description = '\n\n'.join(block['parts'][1:])
        if not description:
            raise ValueError(f'Missing intervention description: {title}')
        row = {
            'id': 'ribadesella-prtr-' + code.lower(),
            'municipio': 'Ribadesella', 'codigo_ine': '33056', 'provincia': 'Asturias',
            'titulo': title, 'referencia_prtr': code,
            'tipo': 'proyecto de intervención física', 'descripcion': description,
            'url': url, 'inventory_url': url, 'source': 'ayuntamiento',
            'origen': 'inventario_municipal_prtr',
            'documentos': list(block['docs'].values()),
            'geometry_status': 'unavailable', 'publication_ready': False,
        }
        if code in rows and rows[code] != row:
            raise ValueError(f'Conflicting duplicate PRTR reference: {code}')
        rows[code] = row
    if not rows:
        raise ValueError('No physical municipal interventions found')
    return list(rows.values())


def write_rows(path: Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                         encoding='utf-8')
    temporary.replace(path)


class RibadesellaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'municipio-ribadesella/1.0 (public project inventory)',
        })
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(SOURCE).hostname:
            raise ValueError('Unexpected inventory redirect')
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected an HTML inventory')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'prtr-inventory.html').write_bytes(response.content)
        rows = parse_inventory(response.content, response.url)
        write_rows(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [response.url],
                'coverage': 'physical_interventions_in_current_prtr_inventory',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Re-read the complete article; no date cutoff or synthetic incremental state.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        write_rows(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
