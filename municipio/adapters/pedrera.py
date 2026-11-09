"""Pedrera: two municipal planning document inventories, one row per instrument."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCES = {
    'pgou': 'https://www.pedrera.es/es/urbanismo/pgou/',
    'pbom': 'https://www.pedrera.es/es/ayuntamiento/encuesta-de-participacion-ciudadana/',
}
LIMITATIONS = [
    'Cobertura parcial: sólo PGOU 2015 y avance PBOM; no modificaciones, planes parciales, obras ni licencias.',
    'Fechas de publicación y acuerdo no extraídas; el mes/año del rótulo PGOU no es una fecha de aprobación verificada.',
    'Documentos enlazados, sin interpretar su contenido ni comprobar individualmente su disponibilidad.',
    'Sin geometría ni coordenadas; la presencia en el portal no acredita vigencia jurídica.',
    'Actualización mediante nueva instantánea completa de los dos inventarios, sin historial incremental.',
]


def parse_inventory(html: str, url: str, kind: str) -> dict:
    """Fail closed if the known inventory disappears or gains pagination."""
    if kind not in SOURCES or url != SOURCES[kind]:
        raise ValueError('Unexpected Pedrera inventory')
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None:
        raise ValueError('Missing inventory main element')
    if main.select('a[rel~=next], .pagination, .paginacion, .pager, [data-next-page]'):
        raise ValueError('Pagination detected: inventory traversal must be reviewed')
    heading = main.find(['h1', 'h3'])
    expected = 'PGOU' if kind == 'pgou' else 'Plan Básico de Ordenación Municipal'
    if heading is None or expected.casefold() not in heading.get_text(' ', strip=True).casefold():
        raise ValueError('Unexpected instrument heading')
    documents = {}
    for a in main.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        if parsed.path.lower().endswith(('.pdf', '.docx', '.zip')):
            allowed = (
                kind == 'pgou'
                and parsed.hostname == 'multimedia.dipusevilla.es'
                and parsed.path.startswith('/pedrera/ficheros/archivos/pgou_2015/')
            ) or (
                kind == 'pbom'
                and parsed.hostname == 'www.pedrera.es'
                and parsed.path.startswith('/export/sites/pedrera/.galleries/')
            )
            if not allowed or parsed.scheme not in ('http', 'https'):
                raise ValueError(f'Unreviewed document location: {target}')
            documents[target] = {
                'titulo': a.get_text(' ', strip=True) or a.get('title') or Path(parsed.path).name,
                'url': target,
                'source_url': url,
            }
    if not documents:
        raise ValueError('No planning documents found')
    text = ' '.join(main.stripped_strings)
    label = ('DOCUMENTO DE APROBACIÓN PGOU SEPTIEMBRE DE 2015' if kind == 'pgou'
             else 'PBOM FASE 3 AVANCE V2')
    if label not in text:
        raise ValueError('Inventory stage label changed; review required')
    return {
        'id': f'pedrera-{kind}',
        'municipio': 'Pedrera', 'codigo_ine': '41072', 'provincia': 'Sevilla',
        'titulo': ('Plan General de Ordenación Urbanística de Pedrera (PGOU 2015)'
                   if kind == 'pgou' else 'Plan Básico de Ordenación Municipal de Pedrera (avance)'),
        'tipo': 'instrumento de planeamiento urbanístico',
        'fase': 'avance' if kind == 'pbom' else None,
        'rotulo_fuente': label,
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': url, 'inventory_url': url, 'source': 'ayuntamiento',
        'origen': 'inventario_planeamiento',
        'documentos': list(documents.values()),
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class PedreraAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows, provenance = [], []
        capture_dir = self.config.get('capture_dir')
        for kind, url in SOURCES.items():
            response = requests.get(url, timeout=45, headers={
                'User-Agent': 'municipio-pedrera/1.0 (public planning inventory)',
            })
            response.raise_for_status()
            if response.url != url:
                raise ValueError(f'Unexpected inventory redirect: {response.url}')
            row = parse_inventory(response.text, response.url, kind)
            fetched = datetime.now(timezone.utc).isoformat()
            source = {'url': url, 'retrieved_at': fetched,
                      'sha256': hashlib.sha256(response.content).hexdigest()}
            row['provenance'] = source
            rows.append(row)
            provenance.append(source)
            if capture_dir:
                folder = Path(capture_dir)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f'{kind}.html').write_bytes(response.content)
        # Write only after both sources succeed: never present a partial fetch as complete.
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': list(SOURCES.values()),
                'sources': provenance, 'limitations': LIMITATIONS,
                'coverage': 'two_current_planning_document_inventories',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        raise NotImplementedError('Licencias disabled: no verified public grant register')

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
