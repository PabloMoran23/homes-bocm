"""Ortigueira's published municipal planning inventory (partial coverage)."""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://concellodeortigueira.gal/obras-servizos-e-medio-rural/plan-de-urbanismo/?lang=es'
TABLES = ('gralPlanTableSortable', 'planDesTableSortable')
HOST = 'concellodeortigueira.gal'


def _date(text):
    return date.fromisoformat(text).isoformat() if text else None


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    records = {}
    for table_id in TABLES:
        table = soup.find('table', id=table_id)
        if table is None:
            raise ValueError(f'Missing planning inventory: {table_id}')
        # This page embeds static tables, not a server-side DataTables endpoint.
        # Refuse a changed/paginated source instead of silently reading page one.
        scope = table.parent
        for a in scope.select('a[href]'):
            label = a.get_text(' ', strip=True).casefold()
            if (label in {'next', 'siguiente', 'seguinte', '>', '»'} or
                    'next' in a.get('rel', []) or 'paginate_button' in a.get('class', [])):
                if a['href'] not in {'', '#'} and 'disabled' not in a.get('class', []):
                    raise ValueError('Pagination requires review before extraction')
        info = soup.find(id=table_id + '_info')
        if info:
            raise ValueError('DataTables paging metadata requires completeness review')
        headers = [c.get_text(' ', strip=True).upper() for c in table.select('thead th')]
        if len(headers) != 6 or headers[0] != 'FIGURA' or headers[2:5] != ['APROB. DEF', 'BOP', 'DOG']:
            raise ValueError('Changed planning table schema')
        table_count = 0
        for tr in table.select('tbody tr'):
            cells = tr.find_all('td', recursive=False)
            if len(cells) not in (5, 6):
                raise ValueError('Incomplete planning row')
            figure = cells[0].get_text(' ', strip=True)
            if not re.match(r'^(Normas subsidiarias|Modificaci[oó]n puntual|Plan Parcial|Estudio de detalle)\b', figure, re.I):
                raise ValueError(f'Unreviewed planning figure: {figure}')
            links = {}
            for a in cells[1].select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                if urlparse(url).hostname != HOST or not urlparse(url).path.lower().endswith('.docx'):
                    raise ValueError('Unreviewed planning document URL')
                links[url] = {'titulo': a.get_text(' ', strip=True), 'url': url,
                              'procedencia': SOURCE, 'tipo': 'inventario documental municipal (Word)'}
            if not links:
                raise ValueError('Planning row without documentary provenance')
            label = re.sub(r'^DESCARGA\s+WORD\s*', '', cells[1].get_text(' ', strip=True), flags=re.I)
            title = figure if table_id == TABLES[0] else f'{figure} — {label}'
            dates = [_date(c.get_text(' ', strip=True)) for c in cells[2:]]
            if not dates[0]:
                raise ValueError('Missing stated definitive approval date')
            identity = ' '.join(title.casefold().split())
            key = 'ortigueira-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16]
            row = {
                'id': key, 'municipio': 'Ortigueira', 'codigo_ine': '15061', 'provincia': 'A Coruña',
                'titulo': title, 'tipo': figure, 'fase': 'aprobación definitiva según inventario municipal',
                'fecha_aprob': dates[0], 'fecha_publicacion': None,
                'fecha_publicacion_bop': dates[1], 'fecha_publicacion_dog': dates[2],
                'fecha_publicacion_normativa': dates[3] if len(dates) == 4 else None,
                'url': SOURCE, 'inventory_url': SOURCE,
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
                'documentos': list(links.values()), 'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'cobertura': 'Inventario municipal publicado; vigencia y exhaustividad no verificadas',
            }
            if key in records:
                existing = records[key]
                if any(existing[k] != row[k] for k in row if k != 'documentos'):
                    raise ValueError('Conflicting rows for one planning instrument')
                by_url = {d['url']: d for d in existing['documentos'] + row['documentos']}
                existing['documentos'] = list(by_url.values())
            else:
                records[key] = row
            table_count += 1
        if not table_count:
            raise ValueError('Empty planning table; review source')
    for script in soup.select('script'):
        text = script.get_text()
        # WordPress also has unrelated AJAX settings; scope AJAX to table scripts.
        table_script = 'datatable' in text.casefold() or any(t in text for t in TABLES)
        server_side = re.search(r'\bserverSide[\"\x27]?\s*:\s*true', text, re.I)
        if server_side or (table_script and re.search(r'\bajax[\"\x27]?\s*:', text, re.I)):
            raise ValueError('Dynamic inventory requires review')
    return list(records.values())


class OrtigueiraAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('evidence_dir')
        capture_dir = Path(captures) if captures else None
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
        source_urls = [SOURCE]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-ortigueira-inventory/1.0'

            def fetch(url):
                response = session.get(url, timeout=35)
                response.raise_for_status()
                if urlparse(response.url).hostname != HOST:
                    raise ValueError('Unexpected source redirect')
                return response

            response = fetch(SOURCE)
            if capture_dir:
                (capture_dir / 'municipal-inventory.html').write_bytes(response.content)
            rows = parse_inventory(response.text)
            for row in rows:
                for doc in row['documentos']:
                    response = fetch(doc['url'])
                    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                        if 'word/document.xml' not in archive.namelist():
                            raise ValueError('Source document is not a Word inventory')
                    doc['sha256'] = hashlib.sha256(response.content).hexdigest()
                    source_urls.append(doc['url'])
                    if capture_dir:
                        (capture_dir / (doc['sha256'] + '.docx')).write_bytes(response.content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': source_urls,
                'coverage': 'published municipal planning inventory; not a complete current register',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refreshed snapshot; no claim of incremental event history.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
