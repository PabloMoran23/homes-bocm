"""Salteras: municipal transparency planning documents, grouped by instrument."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://salteras.sedelectronica.es/transparency/668172bc-1a3d-4c32-9896-3eaea200139b/'
HOST = 'salteras.sedelectronica.es'
LIMITATIONS = [
    'Inventario 7.3 Normativa urbanística únicamente; no es un histórico exhaustivo.',
    'No incluye el POU publicado en la web municipal ni otras secciones de la sede.',
    'La presencia documental no acredita vigencia, aprobación ni concesión de licencia.',
    'Sin fechas de acuerdo o aprobación verificadas y sin geometría.',
]


def official_url(base, href, prefix):
    url = urljoin(base, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != HOST or not parsed.path.startswith(prefix):
        raise ValueError('Unexpected source document URL')
    return url


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.TransparencyListPanel')
    if not table or '7.3. NORMATIVA URBANÍSTICA' not in soup.get_text(' ', strip=True):
        raise ValueError('Planning inventory missing or changed')
    # Wicket pagination cannot be followed as ordinary static links. Fail visibly.
    for element in soup.select('a, button, [class*="pagin"], [class*="Pagin"], [class*="navigator"]'):
        label = ' '.join([element.get_text(' ', strip=True), element.get('title', ''),
                          element.get('aria-label', '')]).lower()
        if (element.get('rel') and 'next' in element['rel']) or re.search(r'\b(siguiente|next|últim[ao]|last)\b', label) or any(
            word in ' '.join(element.get('class', [])).lower() for word in ('pagin', 'navigator')
        ):
            if element.get('aria-disabled') != 'true' and not element.has_attr('disabled'):
                raise ValueError('Pagination detected; inventory coverage needs review')
    groups = {}
    for a in table.select('a[href]'):
        target = official_url(url, a['href'], '/preview-document/')
        title = a.get_text(' ', strip=True)
        description = ' '.join(a.get('title', '').split())
        if re.fullmatch(r'(?:Planos_Adaptacion_LOUA_Salteras-\d+-\d+|documento_adaptacion_loua_salteras)', title, re.I):
            key = 'adaptacion-loua'
            name = 'Adaptación a la LOUA del planeamiento municipal de Salteras'
        elif (title.upper().startswith('ANUNCIO BOP ') and 'MODIF NNSS' in title.upper()
              and 'MUNICIPIO DE SALTERAS' in description.upper()):
            # Scope from the descriptive inventory title, not a BOP filename/date.
            key = 'modificacion-' + hashlib.sha256(description.encode()).hexdigest()[:16]
            name = description
        else:
            raise ValueError(f'Unclassified inventory document: {title}')
        row = groups.setdefault(key, {
            'id': 'salteras-plan-' + key, 'municipio': 'Salteras', 'codigo_ine': '41085',
            'provincia': 'Sevilla', 'titulo': name, 'tipo': 'planeamiento_urbanistico',
            'source': 'ayuntamiento', 'origen': 'inventario_normativa_urbanistica',
            'url': url, 'inventory_url': url, 'documentos': [],
            'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'inventario_parcial_seccion_7_3',
        })
        if target not in {doc['url'] for doc in row['documentos']}:
            row['documentos'].append({'titulo': title, 'url': target, 'inventory_url': url,
                                      'descripcion_fuente': description})
    if not groups:
        raise ValueError('No planning documents found')
    for row in groups.values():
        if row['id'].endswith('adaptacion-loua') and not any(
            doc['titulo'].lower() == 'documento_adaptacion_loua_salteras' for doc in row['documentos']
        ):
            raise ValueError('Adaptation inventory lacks its main document')
    return list(groups.values())


class SalterasAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, capture):
        response = session.get(url, timeout=40)
        response.raise_for_status()
        official_url(url, response.url, '/')
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture).write_bytes(response.content)
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-salteras/1.0 (public planning inventory)'
            rows = parse_inventory(self._fetch(session, SOURCE, 'planeamiento-live.html'))
            for row in rows:
                for doc in row['documentos']:
                    capture = urlparse(doc['url']).path.rsplit('/', 1)[-1] + '.html'
                    html = self._fetch(session, doc['url'], capture)
                    soup = BeautifulSoup(html, 'html.parser')
                    frame = soup.select_one('iframe[src]')
                    if not frame:
                        raise ValueError('Source preview lacks a PDF document')
                    official_url(doc['url'], frame['src'], '/preview/pdf/')
                    # Keep the durable preview URL, not the temporary PDF token.
                    doc['formato'] = 'PDF'
                    doc['provenance'] = 'Ficha documental de la sede electrónica municipal'
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [SOURCE], 'limitations': LIMITATIONS}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
