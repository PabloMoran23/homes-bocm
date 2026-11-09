"""Municipal PGOU document inventory: one instrument, not one project per PDF."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://ayto-montefrio.es/paginas/pgou.htm'


def clean(value):
    return ' '.join(value.split())


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href], link[href]'):
        if ('next' in a.get('rel', []) or
                clean(a.get_text(' ', strip=True)).lower() in
                {'siguiente', 'siguiente página', 'next', '»', '›'}):
            raise ValueError('Pagination detected; review coverage before extracting')
    intro = soup.select_one('div[align="justify"]')
    text = clean(intro.get_text(' ', strip=True)) if intro else ''
    identity = re.search(r'instrumento urbanístico (P\.G\.O\.U\. de Montefrío)', text, re.I)
    if not identity or 'No se incluyen la Memoria General y los Anexos' not in text:
        raise ValueError('Expected Montefrío PGOU identity/coverage statement missing')

    documents = {}
    for a in soup.select('a.wcBar2[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        if not parsed.path.lower().endswith('.pdf'):
            continue
        if (parsed.scheme != 'https' or parsed.netloc != urlparse(SOURCE).netloc
                or not parsed.path.startswith('/impresos/')):
            raise ValueError('Unexpected document origin in PGOU inventory')
        title = clean(a.get_text(' ', strip=True))
        if not title:
            raise ValueError('Untitled PGOU document')
        documents.setdefault(target, {'titulo': title, 'url': target,
                                      'source_url': url})
    if not documents:
        raise ValueError('PGOU inventory has no source documents')

    # Extract only explicitly attributed agreement dates, never a CMS/publication date.
    agreements = []
    regional = re.search(r'APROBACIÓN DEFINITIVA.*?de fecha (\d{1,2}) de marzo de (\d{4})', text)
    municipal = re.search(r'Pleno de la Corporación Municipal en sesión de (\d{1,2}) de julio de (\d{4})', text)
    for match, month, body in [(regional, '03', 'Consejería de Obras Públicas y Vivienda'),
                               (municipal, '07', 'Pleno de la Corporación Municipal')]:
        if match:
            day, year = match.groups()
            agreements.append({'organo_segun_fuente': body,
                               'fecha_acuerdo': f'{year}-{month}-{int(day):02}',
                               'source_url': url})
    return [{
        'id': 'montefrio-pgou', 'municipio': 'Montefrío', 'codigo_ine': '18135',
        'provincia': 'Granada', 'titulo': clean(identity.group(1)),
        'tipo': 'planeamiento_urbanistico', 'url': url, 'inventory_url': url,
        'source': 'ayuntamiento', 'origen': 'inventario_documental_pgou',
        'descripcion': text, 'acuerdos': agreements,
        'documentos': list(documents.values()),
        'coverage': 'partial_historical_pgou_document_inventory',
        'limitations': [
            'La fuente excluye Memoria General y Anexos; consulta completa en Oficina Técnica.',
            'Lojilla figura sin aprobar por la C.P.O.T.U.; no se atribuye aprobación a cada documento.',
            'No acredita vigencia actual ni cubre modificaciones posteriores, obras o licencias.',
            'Sin fecha de publicación verificada ni geometría verificada.'
        ],
        'publication_ready': False, 'geometry_status': 'unavailable',
    }]


class MontefrioAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                             encoding='utf-8')
        temporary.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=40,
                                headers={'User-Agent': 'municipio-montefrio/1.0'})
        response.raise_for_status()
        if response.url != SOURCE:
            raise ValueError('Unexpected PGOU inventory redirect')
        rows = parse_inventory(response.content, response.url)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'pgou.html').write_bytes(response.content)
        return {**self._write(out_jsonl, rows), 'source_urls': [SOURCE],
                'coverage': rows[0]['coverage']}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot of the bounded inventory, so removed links do not persist.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
