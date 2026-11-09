"""Guareña's current municipal PGM document inventory (one instrument)."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://aytoguarena.es/temas/plan-general-municipal/'
HOSTS = {'aytoguarena.es', 'www.aytoguarena.es'}
DOCUMENT_PATH = '/recursos/pdf/plan-general-municipal/'
LIMITATIONS = [
    'Cobertura parcial: solo el inventario documental municipal del Plan General Municipal; no es un registro histórico de obras o licencias.',
    'Documentos estructurales, detallados, ambientales y planos agrupados en un instrumento; no se afirma aprobación ni vigencia.',
    'Sin fechas de publicación o acuerdo verificadas: los años de los títulos y nombres de archivo no son fechas administrativas.',
    'Sin geometría extraída o coordenadas verificadas; Torrefresneda figura como parte del planeamiento del término municipal.',
]


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    """Require the actual page and its named technical documents, not navigation."""
    parsed = urlparse(source_url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.path != urlparse(SOURCE).path:
        raise ValueError('Unexpected Guareña inventory URL')
    soup = BeautifulSoup(html, 'html.parser')
    page = soup.select_one('[data-elementor-type="wp-page"]')
    if page is None or not any(h.get_text(' ', strip=True) == 'Plan General Municipal' for h in page.select('h1')):
        raise ValueError('Missing municipal PGM inventory heading/container')
    # This is a single-page document inventory. A future paginated layout must
    # be supported explicitly; never return only the first page silently.
    if soup.select('link[rel~="next"], a[rel~="next"]') or page.select('.pagination, .page-numbers, .nav-links, .elementor-pagination'):
        raise ValueError('Unexpected pagination: inventory coverage cannot be guaranteed')
    documents = {}
    for anchor in page.select('a[href]'):
        target = urljoin(source_url, anchor['href'])
        doc = urlparse(target)
        if not doc.path.startswith(DOCUMENT_PATH):
            continue
        if doc.hostname not in HOSTS or doc.scheme != 'https' or not doc.path.lower().endswith('.pdf'):
            raise ValueError('Unexpected PGM document target')
        title = anchor.get_text(' ', strip=True)
        if not title:
            raise ValueError('Unnamed PGM document')
        documents.setdefault(target, {'titulo': title, 'url': target, 'source_url': source_url})
    titles = ' '.join(d['titulo'] for d in documents.values()).upper()
    if not documents or not all(word in titles for word in ('MEMORIA', 'NORMATIVA', 'PGM')):
        raise ValueError('No usable technical PGM document inventory')
    return [{
        'id': 'guarena-pgm', 'municipio': 'Guareña', 'codigo_ine': '06060',
        'provincia': 'Badajoz', 'titulo': 'Plan General Municipal de Guareña',
        'tipo': 'Plan General Municipal', 'url': source_url,
        'inventory_url': source_url, 'source': 'ayuntamiento',
        'origen': 'inventario_planeamiento_municipal',
        'documentos': list(documents.values()),
        'descripcion': 'Inventario documental del Plan General Municipal: ' + '; '.join(d['titulo'] for d in documents.values()),
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'limitations': LIMITATIONS,
    }]


class GuarenaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='guarena', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-guarena/1.0'),
        })
        response.raise_for_status()
        rows = parse_inventory(response.text, response.url)
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory.html').write_text(response.text, encoding='utf-8')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': [SOURCE], 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete current snapshot; not a date-filtered historical feed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public granted-licence register; forms excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
