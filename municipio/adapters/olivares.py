"""Named instruments in Olivares' official transparency galleries.

Full snapshots of three unpaginated inventories; no licence inference from
application forms, procurement notices, or document upload metadata.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://transparencia.olivares.es'
INVENTORY = ROOT + '/es/transparencia/indicadores-de-transparencia/indicador/'
SOURCES = (
    INVENTORY + '50.-Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00032/',
    INVENTORY + '53.-Se-publican-y-se-mantienen-publicados-las-modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados.-00032/',
    INVENTORY + '54.-Se-publica-informacion-precisa-de-los-Convenios-urbanisticos-del-Ayuntamiento-y-de-las-actuaciones-urbanisticas-en-ejecucion.-00032/',
)
LIMITATIONS = [
    'Cobertura parcial: solo galerías con instrumentos urbanísticos nombrados de los indicadores 50, 53 y 54.',
    'Excluidos expropiaciones, galería genérica Documentos en información pública (UR-10), calificación ambiental, contratos y formularios.',
    'Fechas no normalizadas; títulos de documentos conservan las fases sin afirmar vigencia ni aprobación del conjunto.',
    'Sin geometría verificada; enlace histórico del PGOU conservado sin garantizar su disponibilidad.',
    'No es un registro de licencias concedidas ni un inventario exhaustivo de obras.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _norm(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower()) if not unicodedata.combining(c))


def parse_inventory(html: str, url: str) -> list[dict]:
    if url not in SOURCES:
        raise ValueError('Unexpected inventory URL')
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.sg-indicador-trans')
    if article is None:
        raise ValueError('Missing municipal indicator article')
    # These are single-page galleries today. Fail explicitly if paging appears;
    # never return an apparently complete first page.
    if soup.select('[rel~=next], .pagination, .pager') or any(
        re.search(r'(?:searchPage|page|offset)=', a['href'], re.I)
        for a in article.select('a[href]')
    ):
        raise ValueError('Inventory pagination detected: traversal must be reviewed')
    records = {}
    for gallery in article.select('section.gallery'):
        heading = gallery.select_one('h4.gallery-title')
        if heading is None:
            continue
        title = _text(heading)
        normal = _norm(title)
        if normal.startswith('plan general de ordenacion urbanistica de olivares'):
            kind = 'PGOU'
        elif re.match(r'^modificacion\s+n[º°o.]?\s*\d+\s+pgou', normal):
            kind = 'modificación del PGOU'
        elif normal.startswith('modificacion del proyecto de reparcelacion'):
            kind = 'modificación de proyecto de reparcelación'
        elif normal.startswith('proyecto de delimitacion de dos unidades de ejecucion'):
            kind = 'proyecto de delimitación'
        else:
            continue
        documents = {}
        for anchor in gallery.select('h4.title-element a[href]'):
            target = urljoin(url, anchor['href'])
            parsed = urlparse(target)
            if kind == 'PGOU':
                allowed = parsed.hostname == '3web.dipusevilla.es' and parsed.path.startswith('/planeamiento/OlivaresPGOU/')
            else:
                allowed = parsed.hostname == 'transparencia.olivares.es' and parsed.path.startswith('/export/sites/olivares/es/transparencia/.galleries/') and parsed.path.lower().endswith('.pdf')
            if not allowed:
                raise ValueError('Unexpected instrument document URL: ' + target)
            documents[target] = {'titulo': _text(anchor), 'url': target, 'source_url': url}
        if not documents:
            raise ValueError('Named instrument without documents: ' + title)
        key = 'olivares-plan-' + hashlib.sha256(normal.encode()).hexdigest()[:16]
        if key in records:
            raise ValueError('Duplicate instrument gallery: ' + title)
        records[key] = {
            'id': key, 'municipio': 'Olivares', 'codigo_ine': '41067', 'provincia': 'Sevilla',
            'titulo': title, 'tipo': kind, 'url': url,
            'url_documento': next(iter(documents)), 'documentos': list(documents.values()),
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'fase': None, 'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'named_instrument_galleries_only',
        }
    if not records:
        raise ValueError('No named instruments found; source structure may have changed')
    return list(records.values())


class OlivaresAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = []
        capture = self.config.get('capture_dir')
        for number, url in enumerate(SOURCES):
            response = requests.get(url, timeout=45, headers={'User-Agent': 'municipio-olivares/1.0'})
            response.raise_for_status()
            if response.url != url:
                raise ValueError('Unexpected inventory redirect: ' + response.url)
            response.encoding = 'utf-8'
            if capture:
                folder = Path(capture)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f'inventory-{number + 1}.html').write_text(response.text, encoding='utf-8')
            rows.extend(parse_inventory(response.text, url))
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Instrument repeated across inventories; review grouping')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'source_urls': list(SOURCES), 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
