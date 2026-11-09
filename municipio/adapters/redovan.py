"""Snapshot of Redován's municipal planning inventory; not a licence register."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.redovan.es/ayuntamiento/estructura-municipal/concejalias-2/urbanismo/planeamiento-municipal-vigente/'


def _date(value: str) -> str:
    day, month, year = map(int, value.split('/'))
    # Only the reviewed municipal narrative uses a two-digit year (22/07/11).
    if year < 100:
        year += 2000
    return date(year, month, day).isoformat()


def _dates(text: str) -> tuple[str | None, str | None]:
    approval = re.search(r'aprobad[oa].*?fecha\s*(?:\(C\.T\.U\.\)\s*de fecha\s*)?(\d{1,2}/\d{1,2}/\d{2,4})', text, re.I)
    publication = re.search(r'publicad[oa].*?fecha\s*(\d{1,2}/\d{1,2}/\d{2,4})', text, re.I)
    return (_date(approval[1]) if approval else None,
            _date(publication[1]) if publication else None)


class RedovanAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.redovan.es')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        if len(soup.select('.entry-content')) != 1:
            raise ValueError('Expected exactly one municipal inventory content area')
        content = soup.select_one('.entry-content')
        if content is None or not content.select_one('.et_pb_toggle'):
            raise ValueError('Missing municipal planning inventory')
        for a in soup.select('a[href]'):
            label = a.get_text(' ', strip=True).casefold()
            classes = set(a.get('class', []))
            if ('next' in a.get('rel', []) or classes & {'next', 'page-numbers', 'post-page-numbers'}
                    or label in {'siguiente', 'next', 'página siguiente'}
                    or re.search(r'/(?:page/\d+|\d+/)$|[?&](?:paged|page)=\d+', a['href'])):
                raise ValueError('Pagination detected; review crawler before emitting partial inventory')
        rows = []
        sector = ''
        seen = set()
        for node in content.select('.page-title, .et_pb_toggle'):
            if 'page-title' in node.get('class', []):
                sector = node.get_text(' ', strip=True)
                continue
            heading = node.select_one('.et_pb_toggle_title')
            body = node.select_one('.et_pb_toggle_content')
            if heading is None or body is None:
                raise ValueError('Incomplete planning block')
            title = heading.get_text(' ', strip=True)
            if not re.match(r'^(PGOU$|Modificación Puntual|Proyecto de Homologación|Plan Parcial)', title):
                raise ValueError('Unreviewed planning heading: ' + title)
            if title == 'PGOU':
                title = 'Plan General de Ordenación Urbana (PGOU)'
            current = None
            for paragraph in body.find_all('p'):
                text = paragraph.get_text(' ', strip=True)
                # Embedded instruments have their own approval paragraph, not a
                # toggle. Do not assign their dates/documents to the parent plan.
                embedded = re.match(r'^\d+\s*[.\-]+\s*(Proyecto[^.]*?)(?:\.\s*|\s+)(?=Aprobado)', text, re.I)
                if embedded:
                    instrument = embedded[1].strip()
                elif current is None:
                    instrument = title
                else:
                    instrument = None
                if instrument is not None:
                    full_title = instrument + (' — ' + sector if sector else '')
                    key = full_title.casefold()
                    if key in seen:
                        raise ValueError('Duplicate instrument: ' + full_title)
                    seen.add(key)
                    approval, publication = _dates(text)
                    if not approval or not publication:
                        raise ValueError('Instrument lacks explicit approval/publication narrative: ' + full_title)
                    current = {
                        'id': 'redovan-proy-' + hashlib.sha256((SOURCE + '#' + key).encode()).hexdigest()[:16],
                        'municipio': 'Redován', 'provincia': 'Alicante', 'codigo_ine': '03111',
                        'titulo': full_title, 'tipo': 'planeamiento_urbanistico',
                        'fase': 'aprobado según inventario municipal',
                        'fecha': None, 'fecha_acuerdo': approval, 'fecha_aprob': approval,
                        'fecha_publicacion': publication,
                        'descripcion': text, 'url': SOURCE, 'source': 'ayuntamiento',
                        'origen': 'inventario_planeamiento_municipal', 'documentos': [],
                        'lat': None, 'lon': None, 'geometry': None,
                        'publication_ready': False,
                        'geometry_status': 'Sin geometría verificada; planos PDF enlazados sin georreferenciar',
                        'coverage': 'Inventario municipal de planeamiento; cobertura parcial, sin licencias',
                    }
                    if 'urbanización' in instrument.casefold():
                        current['tipo'] = 'proyecto_urbanizacion'
                    elif 'reparcelación' in instrument.casefold() or 'reparcelacion' in instrument.casefold():
                        current['tipo'] = 'proyecto_reparcelacion'
                    rows.append(current)
                elif re.search(r'\baprobad[oa]\b', text, re.I):
                    raise ValueError('Unsegmented approval narrative: ' + text)
                for a in paragraph.select('a[href]'):
                    url = urljoin(SOURCE, a['href'])
                    if urlsplit(url).path.lower().endswith('.pdf'):
                        if urlsplit(url).hostname != 'www.redovan.es':
                            raise ValueError('Unreviewed external document host')
                        doc = {'titulo': a.get_text(' ', strip=True) or urlsplit(url).path.rsplit('/', 1)[-1],
                               'url': url, 'source_url': SOURCE}
                        if not any(d['url'] == url for d in current['documentos']):
                            current['documentos'].append(doc)
        if not rows or any(not row['documentos'] for row in rows):
            raise ValueError('Inventory empty or instrument without linked documents')
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=40, stream=True,
                          headers={'User-Agent': self.config.get('user_agent', 'municipio-redovan/1.0')}) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname != 'www.redovan.es':
                raise ValueError('Inventory redirected outside municipal host')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Inventory exceeds reviewed response size')
                chunks.append(chunk)
            raw = b''.join(chunks)
        rows = self.parse_projects(raw.decode('utf-8'))
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'planeamiento.html').write_bytes(raw)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(output)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'partial', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete current inventory snapshot; no date watermark loses old edits.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
