"""One PGOU instrument from the municipality-linked plan document inventory."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL = 'https://www.zumarraga.eus/eu/'
SOURCE = 'https://zumarragaplanorokorra.eus/es'
PLAN_HOST = 'zumarragaplanorokorra.eus'
LIMITATIONS = [
    'Cobertura parcial: un PGOU en elaboración, inventario documental en castellano; no es un registro de todos los proyectos municipales.',
    'Las fases de tramitación descritas son una hoja de ruta; no acreditan aprobación inicial, provisional o definitiva.',
    'Sin fechas de publicación, acuerdo o aprobación verificadas; las carpetas de subida no son fechas administrativas.',
    'Sin geometría vectorial verificada; los planos PDF se conservan como documentos, sin inventar coordenadas.',
    'Sin licencias concedidas; formularios, contratación y noticias ajenas quedan fuera.',
]


def _check_pagination(soup):
    for a in soup.select('a[href]'):
        if (set(a.get('rel', [])) & {'next', 'prev'}
                or a.get_text(' ', strip=True).casefold() in
                {'siguiente', 'anterior', 'next', 'previous', 'hurrengoa', 'aurrekoa'}
                or any(c in {'page-numbers', 'next', 'prev'} for c in a.get('class', []))):
            raise ValueError('Inventory pagination appeared; traversal requires review')


class ZumarragaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html: str):
        soup = BeautifulSoup(html, 'html.parser')
        _check_pagination(soup)
        text = soup.get_text(' ', strip=True)
        if not all(marker in text for marker in
                   ('Ayuntamiento de Zumarraga', 'Plan General de Ordenación Urbana',
                    'LOS OBJETIVOS DE LA REVISIÓN DEL PGOU')):
            raise ValueError('Missing Zumarraga PGOU identity/narrative')
        documents = {}
        for a in soup.select('a[href]'):
            url = urljoin(SOURCE, a['href'])
            parts = urlsplit(url)
            if (parts.scheme == 'https' and parts.hostname == PLAN_HOST
                    and parts.path.startswith('/wp-content/uploads/')
                    and parts.path.lower().endswith('.pdf')):
                title = a.get_text(' ', strip=True)
                if not title:
                    raise ValueError('Untitled plan document requires review')
                documents.setdefault(url, {'titulo': title, 'url': url,
                                          'source_url': SOURCE})
        titles = {d['titulo'] for d in documents.values()}
        if not {'AVANCE: MEMORIA', 'AVANCE: PLANOS', 'AVANCE: DIE'} <= titles:
            raise ValueError('Missing substantive PGOU advance documents')
        return [{
            'id': 'zumarraga-proy-pgou', 'municipio': 'Zumarraga',
            'codigo_ine': '20080', 'provincia': 'Gipuzkoa',
            'titulo': 'Revisión del Plan General de Ordenación Urbana de Zumarraga (PGOU)',
            'tipo': 'planeamiento_urbanistico',
            'fase': 'elaboración; documentación de avance disponible',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_pgou',
            'descripcion': 'Revisión del PGOU de Zumarraga. El portal publica documentación de información urbanística, participación, avance y seguimiento; no se infiere aprobación de la descripción genérica de fases.',
            'documentos': list(documents.values()),
            'provenance': {'municipal_link_page': MUNICIPAL,
                           'document_inventory': SOURCE, 'language': 'es'},
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'limitations': LIMITATIONS,
        }]

    def _fetch(self, session, url, name):
        response = session.get(url, timeout=40)
        response.raise_for_status()
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML inventory')
        if urlsplit(response.url).hostname != urlsplit(url).hostname:
            raise ValueError('Unexpected source redirect')
        # Explicit UTF-8: requests may otherwise default to ISO-8859-1.
        html = response.content.decode('utf-8')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                     for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-zumarraga/1.0'
            municipal_html = self._fetch(session, MUNICIPAL, 'municipal.html')
            municipal = BeautifulSoup(municipal_html, 'html.parser')
            if not any(urlsplit(urljoin(MUNICIPAL, a['href'])).hostname == PLAN_HOST
                       for a in municipal.select('a[href]')):
                raise ValueError('Municipality no longer links the PGOU portal')
            rows = self.parse_projects(self._fetch(session, SOURCE, 'pgou.html'))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows),
                'source_urls': [MUNICIPAL, SOURCE], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot of this single instrument, with stable identity.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
