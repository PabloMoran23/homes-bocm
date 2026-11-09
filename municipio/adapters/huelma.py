"""Named detailed plans and physical development projects in Diputación's inventory."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://www.dipujaen.es/diputacion/dipujaen/conoce-diputacion/'
          'areas-organismos-empresas/areaF/urbanismo/planeamiento/')
LIMITATIONS = [
    'Cobertura parcial: solo estudios de detalle y proyectos de urbanización, '
    'reparcelación y compensación del inventario provincial; no registro de licencias.',
    'Inventario histórico publicado actualmente; no acredita vigencia ni ejecución de obras.',
    'Fechas y acuerdos conservados en texto_fuente, sin normalización: existen '
    'erratas y filas con fechas o acuerdos repartidos entre varias líneas.',
    'Sin geometría verificada; sin coordenadas ni fechas de aprobación inferidas.',
    'Agrupación por tipo y ámbito literal normalizado; no se equiparan UA y UE ni ámbitos distintos.',
]


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.casefold())
                   if not unicodedata.combining(c))


def inventory_url(html, page_url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    links = {urljoin(page_url, a['href']) for a in soup.select('a[href]')
             if 'desarrollo del planeamiento' in norm(a.get_text(' ', strip=True))}
    if len(links) != 1:
        raise ValueError('Expected one complete provincial planning inventory')
    url = links.pop()
    if urlparse(url).hostname != 'www.dipujaen.es' or not urlparse(url).path.lower().endswith('.pdf'):
        raise ValueError('Unexpected inventory document')
    return url


def parse_inventory(text, document_url):
    """Read the entire Huelma section, across PDF page breaks; fail if unbounded."""
    starts = list(re.finditer(r'MUNICIPIO:\s+044\.\s+HUELMA\b', text))
    if len(starts) != 1:
        raise ValueError('Missing or ambiguous Huelma municipality section')
    section = text[starts[0].end():]
    end = re.search(r'MUNICIPIO:\s+045\.\s+HUESA\b', section)
    if not end:
        raise ValueError('Missing end of Huelma section; refusing partial PDF')
    section = section[:end.start()]
    groups = {}
    current = None
    for line in section.splitlines():
        if re.fullmatch(r'\s*(?:\d{1,2}/\d{1,2}/\d{4}|\d{2}:\d{2}|\d+)\s*', line):
            continue
        # pdftotext -layout preserves the figure in column zero. New figures
        # terminate the preceding block even when excluded from this coverage.
        if line and not line[0].isspace():
            current = None
            cols = re.split(r'\s{2,}', line.strip())
            if len(cols) < 2:
                continue
            figure, scope = cols[:2]
            f = norm(figure)
            if f in ('estudio de detalle', 'estudio detalle'):
                kind = 'Estudio de Detalle'
            elif f in ('proyecto de urbanizacion', 'proyecto urbanizacion', 'modificacion proy. urban.'):
                kind = 'Proyecto de Urbanización' if not f.startswith('modific') else 'Modificación de Proyecto de Urbanización'
            elif f == 'proyecto reparcelacion':
                kind = 'Proyecto de Reparcelación'
            elif f == 'proyecto de compensacion':
                kind = 'Proyecto de Compensación'
            elif f == 'nn.ss.' and norm(scope).startswith(('proyecto urbanizacion', 'proyecto de reparcelacion')):
                kind = ('Proyecto de Urbanización' if norm(scope).startswith('proyecto urbanizacion')
                        else 'Proyecto de Reparcelación')
            else:
                continue
            current = {'tipo': kind, 'scope': scope, 'lines': [line],
                       'scope_column': line.index(scope)}
            groups.setdefault('blocks', []).append(current)
        elif current and line.strip():
            # Remove report footer, page numbers and time; retain every actual
            # table continuation (including later agreement/publication rows).
            current['lines'].append(line)
            indent = len(line) - len(line.lstrip())
            if abs(indent - current['scope_column']) <= 2:
                continuation = re.split(r'\s{2,}', line.strip())[0]
                # A later unlabelled reparcelación row is retained as evidence;
                # it does not rename the preceding detailed plan.
                if not (current['tipo'] == 'Estudio de Detalle'
                        and norm(continuation).startswith('reparcelacion')):
                    current['scope'] += ' ' + continuation
    records = {}
    for block in groups.get('blocks', []):
        scope, kind = block['scope'], block['tipo']
        identity = norm(kind + '|' + ' '.join(scope.split()))
        key = 'huelma-' + hashlib.sha256(identity.encode()).hexdigest()[:16]
        if key not in records:
            records[key] = {
                'id': key, 'municipio': 'Huelma', 'provincia': 'Jaén', 'codigo_ine': '23044',
                'titulo': kind + ' — ' + scope, 'tipo': kind,
                'url': document_url, 'inventory_url': SOURCE,
                'documentos': [{'titulo': 'Desarrollo del Planeamiento de la Provincia',
                                'url': document_url, 'administracion': 'Diputación Provincial de Jaén'}],
                'source': 'diputacion', 'origen': 'inventario_planeamiento_provincial',
                'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'texto_fuente': [],
            }
        records[key]['texto_fuente'].append('\n'.join(block['lines']))
    if not records:
        raise ValueError('No named development projects or detailed plans in Huelma inventory')
    return list(records.values())


class HuelmaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-huelma/1.0 (public planning inventory)'
            page = session.get(SOURCE, timeout=40)
            page.raise_for_status()
            if urlparse(page.url).hostname != 'www.dipujaen.es':
                raise ValueError('Unexpected source redirect')
            url = inventory_url(page.text, page.url)
            pdf = session.get(url, timeout=60)
            pdf.raise_for_status()
            if urlparse(pdf.url).hostname != 'www.dipujaen.es' or not pdf.content.startswith(b'%PDF-'):
                raise ValueError('Inventory is not an official PDF')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'inventory.pdf'
            path.write_bytes(pdf.content)
            result = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                                    check=True, capture_output=True, timeout=60)
        text = result.stdout.decode('utf-8')
        rows = parse_inventory(text, url)
        if capture := self.config.get('capture_dir'):
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'source.html').write_bytes(page.content)
            (directory / 'source.pdf').write_bytes(pdf.content)
            (directory / 'source.txt').write_text(text, encoding='utf-8')
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'source_urls': [SOURCE, url], 'limitations': LIMITATIONS,
                'coverage': 'complete_selected_categories_in_huelma_section', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        Path(out_jsonl).parent.mkdir(parents=True, exist_ok=True)
        Path(out_jsonl).write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
