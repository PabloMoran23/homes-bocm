"""Cantillana's official indicator 53: grouped planning documents, not licences."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = (
    'https://transparencia.cantillana.es/es/transparencia/indicadores-de-transparencia/'
    'indicador/53.-Se-publican-y-se-mantienen-publicados-las-modificaciones-aprobadas-'
    'del-PGOU-y-los-Planes-parciales-aprobados.-00021/'
)
HOST = 'transparencia.cantillana.es'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if not unicodedata.combining(c))


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.sg-indicador-trans')
    if article is None:
        raise ValueError('Missing official indicator content')
    # This inventory currently renders all galleries in one response. A future
    # pagination change must be reviewed before accepting an incomplete snapshot.
    if soup.select('[rel~=next], .pagination, .paginacion, [class*=paginator]'):
        raise ValueError('Pagination detected; crawler needs review')
    for a in article.select('a[href]'):
        if normalized(a.get_text(' ', strip=True)) in {'siguiente', 'next', 'ver mas', 'cargar mas'}:
            raise ValueError('Continuation detected; crawler needs review')
    records = {}
    for gallery in article.select('section.gallery'):
        heading = gallery.select_one('h4.gallery-title')
        if heading is None:
            raise ValueError('Gallery without instrument heading')
        title = heading.get_text(' ', strip=True)
        title_key = normalized(title)
        # Informational settlement inventory is not itself a plan/project.
        if title_key.startswith('avance inventario'):
            continue
        if not (re.match(r'^(plan (parcial|especial|general)|modificacion|estudio de detalle)\b', title_key)
                or title_key == 'finca la pastora'):
            raise ValueError(f'Unreviewed gallery: {title}')
        key = 'cantillana-plan-' + hashlib.sha256(title_key.encode()).hexdigest()[:16]
        row = records.setdefault(key, {
            'id': key, 'municipio': 'Cantillana', 'codigo_ine': '41023',
            'provincia': 'Sevilla', 'titulo': title, 'tipo': 'planeamiento_urbanistico',
            'url': source_url, 'inventory_url': source_url, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_planeamiento', 'documentos': [],
            'publication_ready': False, 'geometry_status': 'unavailable',
        })
        for a in gallery.select('a[href]'):
            target = urljoin(source_url, a['href'])
            parsed = urlparse(target)
            if not parsed.path.lower().endswith('.pdf'):
                continue
            if parsed.scheme != 'https' or parsed.hostname != HOST or not parsed.path.startswith('/export/sites/cantillana/'):
                raise ValueError(f'Unexpected document provenance: {target}')
            if any(d['url'] == target for d in row['documentos']):
                continue
            doc = {'titulo': a.get_text(' ', strip=True), 'url': target, 'source_url': source_url}
            media = a.find_parent('div', class_='media')
            if media:
                timestamp = media.select_one('time[datetime]')
                if timestamp:
                    # CMS display date; not an agreement or verified publication date.
                    doc['fecha_catalogo'] = date.fromisoformat(timestamp['datetime'][:10]).isoformat()
                description = media.select_one('.description')
                if description:
                    doc['descripcion'] = description.get_text(' ', strip=True)
                    agreement = re.search(
                        r'acuerdo plenario de (\d{1,2}) de (\w+) de (\d{4})',
                        doc['descripcion'], re.I)
                    if agreement:
                        day, month, year = agreement.groups()
                        value = date(int(year), MONTHS.index(month.lower()) + 1, int(day)).isoformat()
                        if row.get('fecha_acuerdo', value) != value:
                            raise ValueError('Conflicting agreement dates')
                        row['fecha_acuerdo'] = value
                        row['fecha_acuerdo_fuente'] = {'url': target, 'texto': doc['descripcion'],
                                                       'ubicacion': 'descripcion municipal del documento'}
            row['documentos'].append(doc)
        if not row['documentos']:
            raise ValueError(f'Instrument has no PDF documents: {title}')
    if not records:
        raise ValueError('No usable planning instruments')
    return list(records.values())


class CantillanaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'municipio-cantillana/1.0 (public planning inventory)'})
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [response.url],
                'coverage': 'indicator_53_current_document_inventory', 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full replacement: no date watermark can safely represent this catalogue.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
