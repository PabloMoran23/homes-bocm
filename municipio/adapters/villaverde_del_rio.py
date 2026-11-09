"""Villaverde del Río: grouped instruments from the official transparency inventory."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://transparencia.villaverdedelrio.es/es/transparencia/'
          'indicadores-de-transparencia/indicador/50.-Esta-publicado-el-Plan-General-'
          'de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00028/')
DOC_PATH = '/export/sites/villaverdedelrio/es/transparencia/.galleries/IND-50-/'
GROUPS = {
    'nnss': ('Normas Subsidiarias de Villaverde del Río',
             r'Normas subsidiarias aprobadas el (\d{2}/\d{2}/\d{4})'),
    'adaptacion-loua': ('Adaptación Parcial de las Normas Subsidiarias a la LOUA de Villaverde del Río',
                       r'Adaptación Parcial de las Normas a la L\.O\.U\.A\. aprobadas el (\d{2}/\d{2}/\d{4})'),
    'avance-pgou': ('Avance del Plan General de Ordenación Urbanística de Villaverde del Río',
                    r'PGOU se encuentra en fase de Avance, aprobado por Pleno de (\d{2}/\d{2}/\d{4})'),
}


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.sg-indicador-trans')
    if article is None or 'Villaverde del Río' not in article.get_text(' ', strip=True):
        raise ValueError('Missing Villaverde del Río planning inventory')
    # This source is an unpaginated document gallery. Fail explicitly if it changes.
    if soup.select('[rel~=next], .pagination, .pager'):
        raise ValueError('Pagination detected; refusing an incomplete snapshot')
    text = ' '.join(p.get_text(' ', strip=True) for p in article.select('p'))
    rows = {}
    for key, (title, pattern) in GROUPS.items():
        match = re.search(pattern, text, re.I)
        if not match:
            raise ValueError(f'Missing instrument narrative: {key}')
        rows[key] = {
            'id': f'villaverde-del-rio-planeamiento-{key}',
            'municipio': 'Villaverde del Río', 'codigo_ine': '41101',
            'provincia': 'Sevilla', 'titulo': title,
            'tipo': 'instrumento de planeamiento',
            'url': source_url, 'inventory_url': source_url,
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'fecha_acuerdo': datetime.strptime(match[1], '%d/%m/%Y').date().isoformat(),
            'acuerdo_descripcion': match[0], 'fecha_acuerdo_fuente': source_url,
            'fase': 'avance aprobado' if key == 'avance-pgou' else 'aprobado según inventario municipal',
            'fecha_publicacion': None,
            'documentos': [], 'geometry_status': 'unavailable',
            'publication_ready': False,
            'coverage': 'Inventario documental parcial; no acredita vigencia actual ni ejecución de obras.',
        }
    seen = set()
    for a in article.select('section.gallery h4 a[href]'):
        target = urljoin(source_url, a['href'])
        parsed = urlparse(target)
        if not parsed.path.lower().endswith('.pdf'):
            continue  # Regional search link and the empty CMS attachment are not instruments.
        if parsed.hostname != urlparse(SOURCE).hostname or not parsed.path.startswith(DOC_PATH):
            raise ValueError(f'Unexpected document provenance: {target}')
        filename = unquote(parsed.path.rsplit('/', 1)[-1])
        if filename.startswith('NNSS-'):
            group = 'nnss'
        elif filename.startswith('C1av'):
            group = 'avance-pgou'  # Includes its information map of the older NNSS.
        elif filename in ('AdaptacionVillaverde_V5.pdf', 'Publicacion-en-el-BOP.pdf'):
            group = 'adaptacion-loua'
        else:
            raise ValueError(f'Unclassified planning document: {filename}')
        if target in seen:
            continue
        seen.add(target)
        label = a.get_text(' ', strip=True)
        if not label:
            raise ValueError('Unlabelled planning PDF')
        media = a.find_parent(class_='media')
        time = media.select_one('time[datetime]') if media else None
        publication = None
        if time:
            publication = datetime.fromisoformat(time['datetime']).date().isoformat()
        rows[group]['documentos'].append({
            'titulo': label, 'url': target, 'source_url': source_url,
            'fecha_publicacion': publication,
            'fecha_publicacion_semantica': 'fecha del adjunto en el CMS; no fecha del acuerdo ni del BOP',
        })
    if any(not row['documentos'] for row in rows.values()):
        raise ValueError('An instrument has no linked documents')
    return list(rows.values())


class VillaverdeDelRioAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'municipio-villaverde-del-rio/1.0'})
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE.rstrip('/'):
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        # Optional local evidence capture of the exact response used for extraction.
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory.html').write_bytes(response.content)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [response.url],
                'documents': sum(len(r['documentos']) for r in rows),
                'coverage': 'partial_current_document_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
