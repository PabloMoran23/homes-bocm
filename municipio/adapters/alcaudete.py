"""Alcaudete: named detail studies in the currently linked provincial inventory.

Requires the preinstalled pdftotext executable. No licence or approval inference.
"""
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

INVENTORY = 'https://www.dipujaen.es/diputacion/dipujaen/conoce-diputacion/areas-organismos-empresas/areaF/urbanismo/planeamiento/'
LIMITATIONS = [
    'Cobertura parcial: solo Estudios de Detalle del inventario provincial actualmente enlazado, rotulado octubre 2025; no registro municipal completo ni cobertura posterior garantizada.',
    'La ficha provincial es una fuente secundaria oficial: no se han verificado los acuerdos originales ni la vigencia de los instrumentos.',
    'Fechas y acuerdos conservados en texto de fuente; no se asignan fechas estructuradas de publicación o aprobación. El inventario contiene inconsistencias cronológicas.',
    'Enlaces documentales al inventario PDF y sus páginas; no son documentos técnicos individuales. Sin geometrías ni licencias concedidas.',
]


def inventory_pdf(html: str, url: str = INVENTORY) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href]'):
        if (a.get('rel') and 'next' in a['rel']) or a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'mostrar más'}:
            raise ValueError('Inventory pagination changed; review before extraction')
    links = {urljoin(url, a['href']) for a in soup.select('a[href]')
             if 'Desarrollo del Planeamiento de la Provincia' in a.get_text(' ', strip=True)}
    if len(links) != 1:
        raise ValueError('Expected exactly one provincial development inventory')
    target = links.pop()
    if urlparse(target).hostname != 'www.dipujaen.es' or not urlparse(target).path.lower().endswith('.pdf'):
        raise ValueError('Unexpected inventory document host or format')
    return target


def parse_inventory(text: str, pdf_url: str) -> list[dict]:
    """Read all PDF pages; stop at the next municipality, including La Bobadilla.

    Only explicitly labelled Estudios de Detalle are supported. Text excerpts
    retain chronology verbatim rather than interpreting shifted PDF columns.
    """
    active = False
    ended = False
    current = None
    studies = []
    for page, body in enumerate(text.split('\f'), 1):
        for line in body.splitlines():
            if line.startswith('MUNICIPIO:'):
                if active:
                    ended = True
                    active = False
                    current = None
                if re.fullmatch(r'MUNICIPIO:\s+003\. ALCAUDETE\s*', line):
                    if studies or ended:
                        raise ValueError('Duplicate Alcaudete section')
                    active = True
                continue
            if not active:
                continue
            match = re.match(r'^Estudio de Detalle(\s{2,})(\S.*)', line, re.I)
            if match:
                parts = re.split(r'\s{2,}(?=Ap[.,]?\s*(?:Inicial|definitiva))',
                                 match.group(2).strip(), maxsplit=1, flags=re.I)
                if not parts[0] or len(parts) < 2:
                    raise ValueError('Detail study row layout changed')
                current = {'scope': [parts[0]], 'lines': [line.rstrip()], 'pages': [page],
                           'scope_column': match.start(2)}
                studies.append(current)
            elif line and not line[0].isspace():
                # Another figure, page footer, or heading ends the current row.
                current = None
            elif current and line.strip():
                # Source continuation: scope starts at the same table column;
                # later columns belong to agreements/dates, never to the title.
                indent = len(line) - len(line.lstrip())
                if abs(indent - current['scope_column']) <= 1:
                    current['scope'].append(re.split(r'\s{2,}', line.strip())[0])
                if indent >= current['scope_column'] - 1:
                    current['lines'].append(line.rstrip())
                    if page not in current['pages']:
                        current['pages'].append(page)
    if not ended or not studies:
        raise ValueError('Missing complete Alcaudete section or detail studies')
    rows = {}
    for study in studies:
        scope = re.sub(r'\s+', ' ', ' '.join(study['scope']))
        key = unicodedata.normalize('NFKC', scope).casefold()
        row = rows.setdefault(key, {
            'id': 'alcaudete-ed-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Alcaudete', 'codigo_ine': '23003', 'provincia': 'Jaén',
            'titulo': 'Estudio de Detalle — ' + scope, 'ambito': scope,
            'tipo': 'estudio_de_detalle', 'url': pdf_url,
            'inventory_url': INVENTORY, 'source': 'diputacion_jaen',
            'origen': 'inventario_provincial_planeamiento',
            'documentos': [], 'extractos_fuente': [],
            'publication_ready': False, 'geometry_status': 'unavailable',
        })
        row['extractos_fuente'].append('\n'.join(study['lines']))
        for page in study['pages']:
            doc = {'titulo': 'Inventario provincial de planeamiento, página PDF ' + str(page),
                   'url': pdf_url + '#page=' + str(page), 'pagina_pdf': page,
                   'procedencia': 'Diputación Provincial de Jaén; ficha resumen, no acuerdo original'}
            if doc not in row['documentos']:
                row['documentos'].append(doc)
    return list(rows.values())


class AlcaudeteAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        captures = self.config.get('capture_dir')
        capture_dir = Path(captures) if captures else None
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-alcaudete/1.0 (public planning inventory)'

            def fetch(url):
                response = session.get(url, timeout=(15, 90))
                response.raise_for_status()
                if urlparse(response.url).hostname != 'www.dipujaen.es':
                    raise ValueError('Unexpected source redirect')
                source_urls.append(response.url)
                return response

            index = fetch(INVENTORY)
            pdf_url = inventory_pdf(index.text, index.url)
            pdf = fetch(pdf_url)
        if not pdf.content.startswith(b'%PDF-'):
            raise ValueError('Inventory is not a PDF')
        with tempfile.TemporaryDirectory(prefix='alcaudete-') as temp:
            path = Path(temp) / 'inventory.pdf'
            path.write_bytes(pdf.content)
            result = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                                    check=True, capture_output=True, timeout=90)
            text = result.stdout.decode('utf-8')
        rows = parse_inventory(text, pdf_url)
        if capture_dir:
            (capture_dir / 'inventory.html').write_text(index.text, encoding='utf-8')
            (capture_dir / 'inventory.pdf').write_bytes(pdf.content)
            (capture_dir / 'inventory.txt').write_text(text, encoding='utf-8')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp_output = output.with_suffix('.jsonl.tmp')
        temp_output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp_output.replace(output)
        return {'count': len(rows), 'written': len(rows), 'live_records': len(rows),
                'source_urls': source_urls, 'limitations': LIMITATIONS,
                'coverage': 'estudios_de_detalle_inventario_provincial', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full current snapshot; no unverified date cursor and no state mutation.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {'count': 0, 'disabled': True, 'reason': 'No verified public granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
