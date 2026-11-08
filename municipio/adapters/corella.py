"""Corella's single-page PGM document inventory, grouped as one instrument."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, Tag

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.corella.es/urbanismo/'


def _text(node: Tag) -> str:
    return unicodedata.normalize('NFC', node.get_text(' ', strip=True))


class CorellaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ''):
        super().__init__(slug, config, base_url or 'https://www.corella.es')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        # This reviewed source is a complete, unpaginated document inventory.
        # Refuse changed pagination rather than silently taking the first page.
        if soup.select('a[rel~=next], .pagination, .page-numbers, .nav-links'):
            raise ValueError('PGM inventory now has pagination; review traversal')
        headings = [h for h in soup.select('h3') if _text(h).upper() == 'PLAN GENERAL MUNICIPAL']
        if len(headings) != 1:
            raise ValueError('Expected one municipal PGM heading')
        documents: dict[str, dict[str, str]] = {}
        sections = set()
        section = ''
        boundary_found = False
        for block in headings[0].next_siblings:
            if not isinstance(block, Tag):
                continue
            if block.name in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
                label = _text(block)
                if label == 'Licencia de obras':
                    boundary_found = True
                    break
                if block.name != 'h4' or label not in {
                    'Estrategia y Modelo de Ocupación del Territorio de Corella',
                    'Plan Urbanístico Municipal',
                }:
                    raise ValueError('Unreviewed PGM inventory section: ' + label)
                section = label
                sections.add(label)
            if block.select('h1, h2, h3, h4, h5, h6'):
                raise ValueError('Unreviewed nested PGM section heading')
            links = [block] if block.name == 'a' and block.has_attr('href') else block.select('a[href]')
            for link in links:
                url = urljoin(SOURCE, link['href'])
                parsed = urlsplit(url)
                if (parsed.scheme != 'https' or parsed.hostname != 'www.corella.es'
                        or not parsed.path.startswith('/wp-content/uploads/')
                        or not parsed.path.lower().endswith('.pdf') or not _text(link)):
                    raise ValueError('Unreviewed PGM document link: ' + url)
                documents.setdefault(url, {'titulo': _text(link), 'url': url,
                                            'seccion': section, 'url_fuente': SOURCE})
        labels = {d['titulo'] for d in documents.values()}
        if (not boundary_found or len(sections) != 2
                or '01 Normativa' not in labels
                or '01 MEMORIA INFORMATIVA DESCRIPTIVA Y JUSTIFICATIVA' not in labels
                or not any('EMOT-' in url for url in documents)):
            raise ValueError('Incomplete or changed Corella PGM inventory')
        return [{
            'id': 'corella-pgm', 'municipio': 'Corella', 'codigo_ine': '31077',
            'provincia': 'Navarra', 'titulo': 'Plan General Municipal de Corella',
            'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_pgm',
            'documentos': list(documents.values()),
            'descripcion': 'Inventario municipal del Plan General Municipal: Estrategia y '
                           'Modelo de Ocupación del Territorio y Plan Urbanístico Municipal. '
                           'Documentación informativa, justificativa, normativa y planos.',
            'cobertura': 'Parcial: únicamente el PGM enlazado en Urbanismo; no es un registro '
                         'completo de modificaciones, obras o licencias. La página no indica '
                         'fechas ni fase de aprobación. No se interpreta el texto de los PDF.',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'Planos PDF enlazados; sin geometría vectorial verificada',
        }]

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-corella/1.0'}) as response:
            response.raise_for_status()
            if response.url != SOURCE:
                raise ValueError('Unexpected redirect from municipal PGM inventory')
            chunks = []
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Corella inventory exceeds 4 MB; refusing truncation')
                chunks.append(chunk)
            body = b''.join(chunks)
        rows = self.parse_projects(body.decode('utf-8'))
        if self.config.get('evidence_dir'):
            captures = Path(self.config['evidence_dir'])
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'urbanismo-live.html').write_bytes(body)
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'documents': len(rows[0]['documentos']), 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete replacement: this source has no incremental cursor or pagination.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0,
                'reason': 'Application forms are not granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
