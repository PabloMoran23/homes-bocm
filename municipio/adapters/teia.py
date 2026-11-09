"""Teià's municipal project inventory, not a register of granted licences."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://teia.cat/serveis/urbanisme/projectes-urbanistics'


def _key(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


class TeiaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://teia.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.select_one('table#projectTable')
        if table is None or [x.get_text(' ', strip=True) for x in table.select('thead th')] != ['Data del Projecte', 'Nom del Projecte']:
            raise ValueError('Teià project inventory schema missing or changed')
        # The reviewed source has all rows in HTML and a client-side text filter.
        # A future server-side pager must be reviewed rather than silently skipped.
        if soup.select('.pagination, .pager, a[rel="next"], [data-next-page]'):
            raise ValueError('Teià pagination detected; full traversal needs review')
        for a in soup.select('a[href]'):
            if re.search(r'[?&](?:start|limitstart|page)=', a['href']) or _key(a.get_text(' ', strip=True)) in {'següent', 'siguiente', 'next'}:
                raise ValueError('Teià pagination detected; full traversal needs review')
        grouped = {}
        for tr in table.select('tbody tr'):
            cells = tr.find_all('td', recursive=False)
            if len(cells) != 2:
                raise ValueError('Malformed Teià inventory row')
            title = cells[1].get_text(' ', strip=True)
            # Allocation of existing rental homes is not a construction project.
            if _key(title) == 'procés d’adjudicació d’habitatges en règim de lloguer per a joves':
                continue
            key = _key(title)
            if not re.match(r'^(projecte\b|pla especial\b|pla de millora\b|avanç de planejament\b|ampliació de\b|reforma\b|parc de\b)', key):
                raise ValueError('Unreviewed inventory category: ' + title)
            raw_date = cells[0].get_text(' ', strip=True)
            project_date = datetime.strptime(raw_date, '%d-%m-%Y').date().isoformat() if raw_date else None
            links = []
            for a in cells[1].select('a[href]'):
                url = urljoin(SOURCE, a['href'].strip())
                parsed = urlsplit(url)
                if parsed.scheme != 'https' or parsed.hostname not in {'teia.cat', 'www.teia.cat', 'ajuntamentteia.sharepoint.com'}:
                    raise ValueError('Unexpected project document origin')
                links.append({'titulo': a.get_text(' ', strip=True), 'url': url,
                              'tipo_enlace': 'carpeta' if '/:f:/' in parsed.path else 'documento',
                              'provenance_url': SOURCE, 'contenido_verificado': False})
            if not links:
                raise ValueError('Project without source document links')
            if key not in grouped:
                planning = key.startswith(('pla especial', 'pla de millora', 'avanç de planejament'))
                grouped[key] = {
                    'id': 'teia-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                    'municipio': 'Teià', 'codigo_ine': '08281', 'provincia': 'Barcelona',
                    'titulo': title, 'tipo': 'planeamiento_urbanistico' if planning else 'proyecto_obras',
                    'fase': None, 'fecha': None, 'fecha_publicacion': None,
                    'fecha_acuerdo': None, 'fecha_aprob': None,
                    'fecha_proyecto_fuente': project_date,
                    'fecha_proyecto_etiqueta': 'Data del Projecte (semántica adicional no especificada)',
                    'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_proyectos_urbanisticos',
                    'documentos': [], 'entradas_fuente': [],
                    'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                    'coverage': 'Inventario municipal; no acredita aprobación, ejecución ni vigencia actual',
                }
            row = grouped[key]
            if row['fecha_proyecto_fuente'] != project_date:
                row['fecha_proyecto_fuente'] = None
            row['entradas_fuente'].append({'titulo': title, 'fecha_proyecto': project_date, 'url': SOURCE})
            seen = {d['url'] for d in row['documentos']}
            for link in links:
                if link['url'] not in seen:
                    row['documentos'].append(link)
                    seen.add(link['url'])
        if not grouped:
            raise ValueError('No supported Teià project records')
        return list(grouped.values())

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-teia/1.0')})
        response.raise_for_status()
        if len(response.content) > 4_000_000:
            raise ValueError('Teià inventory exceeds reviewed response size')
        rows = self.parse_projects(response.text)
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / 'inventory.html').write_bytes(response.content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'publication_ready': False, 'coverage': 'Complete current HTML inventory, filtered to projects'}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
