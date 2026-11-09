"""Ondarroa port planning inventory, published by the Basque Government.

One instrument with all its listed versions, not one project per PDF. This is a
partial planning snapshot, not a licence register or a claim of legal currency.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


SOURCE = 'https://www.euskadi.eus/gobierno-vasco/-/planes-urbanisticos/'
DOCUMENT_ROOT = '/contenidos/informacion/puertos_planes_urbanisticos/'


class OndarroaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.find('h1')
        if not heading or heading.get_text(' ', strip=True) != 'Planes urbanísticos':
            raise ValueError('Port planning inventory title missing')
        # The reviewed inventory is a single unpaginated list. Fail closed if
        # navigation appears, instead of silently accepting the first page.
        for a in soup.select('a[href]'):
            if a['href'] in ('', '#'):
                continue
            if ('next' in a.get('rel', []) or
                    a.get_text(' ', strip=True).casefold() in
                    {'siguiente', 'siguiente página', 'next', 'hurrengoa'}):
                raise ValueError('Inventory pagination requires review')
        sections = [node.parent for node in soup.find_all('strong')
                    if node.get_text(' ', strip=True) == 'Ondarroa'
                    and node.parent.name == 'li']
        if len(sections) != 1:
            raise ValueError('Expected one Ondarroa inventory section')
        section = sections[0]
        province = section.find_previous('h3')
        if not province or province.get_text(strip=True) != 'BIZKAIA':
            raise ValueError('Ondarroa section not under Bizkaia')
        documents = {}
        for a in section.select('a[href]'):
            url = urldefrag(urljoin(SOURCE, a['href']))[0]
            parsed = urlparse(url)
            label = a.get_text(' ', strip=True)
            if (parsed.scheme != 'https' or parsed.hostname != 'www.euskadi.eus'
                    or not parsed.path.startswith(DOCUMENT_ROOT)
                    or not parsed.path.lower().endswith('.pdf') or not label):
                raise ValueError('Unexpected document in Ondarroa section')
            documents.setdefault(url, {'titulo': label, 'url': url,
                                       'source_url': SOURCE,
                                       'publicador': 'Gobierno Vasco'})
        if not documents or not any('PE original' in d['titulo'] for d in documents.values()):
            raise ValueError('Ondarroa original plan documents missing')
        return [{
            'id': 'ondarroa-proy-plan-especial-puerto',
            'municipio': 'Ondarroa', 'codigo_ine': '48073', 'provincia': 'Bizkaia',
            'titulo': 'Plan especial del puerto de Ondarroa',
            'tipo': 'plan_especial', 'url': SOURCE,
            'source': 'gobierno_vasco', 'publicador': 'Gobierno Vasco',
            'origen': 'inventario_planes_urbanisticos_portuarios',
            'documentos': list(documents.values()),
            'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'descripcion': 'Plan portuario: documento original y modificaciones '
                           'agrupados según el inventario oficial. Los años de las '
                           'etiquetas documentales no son fechas de aprobación.',
            'coverage': 'Parcial: solo el plan portuario listado; no todo el planeamiento municipal.',
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }]

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                     for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        capture = self.config.get('evidence_dir')
        capture = Path(capture) if capture else None
        if capture:
            capture.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-ondarroa/1.0 (public planning inventory)'
            response = session.get(SOURCE, timeout=30)
            response.raise_for_status()
            html = response.content
            rows = self.parse_inventory(html)
            if capture:
                (capture / 'ports.html').write_bytes(html)
            # PDFs are up to 241 MB. Verify a small byte range without downloading
            # or pretending to parse the full planning documents.
            checks = []
            for doc in rows[0]['documentos']:
                with session.get(doc['url'], headers={'Range': 'bytes=0-2047'},
                                 stream=True, timeout=30) as pdf:
                    pdf.raise_for_status()
                    prefix = next(pdf.iter_content(2048), b'')
                    if not prefix.startswith(b'%PDF-'):
                        raise ValueError('Linked plan document is not a PDF: ' + doc['url'])
                    check = {'url': doc['url'], 'status': pdf.status_code,
                             'content_type': pdf.headers.get('Content-Type'),
                             'content_range': pdf.headers.get('Content-Range'),
                             'captured_bytes': len(prefix),
                             'sha256_prefix': hashlib.sha256(prefix).hexdigest()}
                    checks.append(check)
                    if capture:
                        name = urlparse(doc['url']).path.rsplit('/', 1)[-1]
                        (capture / (name + '.prefix')).write_bytes(prefix)
            if capture:
                (capture / 'document_checks.json').write_text(
                    json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'documents': len(checks), 'coverage': 'port planning only'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
