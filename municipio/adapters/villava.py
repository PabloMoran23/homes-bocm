"""Municipal PGM document inventory; historical source stages are not current status."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

INVENTORY = ('https://www.villava.es/transparencia/urbanismo-obras-publicas-y-medioambiente/'
             'planes-de-ordenacion-urbana-y-convenios-urbanisticos/')
MONTHS = dict(zip('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), range(1, 13)))


def _canonical(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, re.sub('/+', '/', parts.path), parts.query, ''))


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('main .contenido.content')
    if content is None:
        raise ValueError('Municipal document content missing; source layout needs review')
    # This is a document page, not a paginated news feed. Fail if that changes.
    if soup.select('.pagination, .page-numbers, a[rel="next"], .nav-links'):
        raise ValueError('Unexpected pagination; refusing a partial inventory')
    for a in content.select('a[href]'):
        if a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'hurrengoa'}:
            raise ValueError('Unexpected next-page link')
    return soup, content


def _spanish_date(text):
    match = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', text.lower())
    if not match or match[2] not in MONTHS:
        raise ValueError('Missing explicit agreement date')
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


class VillavaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def discover_plan(html):
        _, content = _content(html)
        links = {
            _canonical(urljoin(INVENTORY, a['href']))
            for a in content.select('a[href]')
            if 'Plan General de Ordenación Urbana' in a.get_text(' ', strip=True)
        }
        if len(links) != 1:
            raise ValueError('Expected one municipal PGM inventory link')
        url = links.pop()
        if urlsplit(url).hostname != 'www.villava.es':
            raise ValueError('PGM link left official municipal website')
        return url

    @staticmethod
    def parse_plan(html, source_url):
        soup, content = _content(html)
        title = soup.select_one('main h2.titulo_prede')
        if not title or title.get_text(' ', strip=True) != 'Documentación del Plan General Municipal':
            raise ValueError('Expected detailed municipal PGM page')
        paragraphs = [p.get_text(' ', strip=True) for p in content.select('p')]
        initial = [p for p in paragraphs if 'aprobó inicialmente el Plan General Municipal' in p]
        provisional = [p for p in paragraphs if 'Con fecha' in p and 'el Ayuntamiento Pleno acuerda' in p]
        if len(initial) != 1 or len(provisional) != 1 or not any('PRIMERO.- Aprobar provisionalmente el Plan General Municipal' in p for p in paragraphs):
            raise ValueError('Historical PGM agreements missing or ambiguous')
        agreements = [
            {'fase': 'aprobación inicial', 'fecha_acuerdo': _spanish_date(initial[0]), 'texto_fuente': initial[0]},
            {'fase': 'aprobación provisional', 'fecha_acuerdo': _spanish_date(provisional[0]),
             'texto_fuente': '\n'.join([provisional[0]] + [p for p in paragraphs if p.startswith(('PRIMERO.-', 'SEGUNDO.-', 'TERCERO.-'))])},
        ]
        documents = {}
        section = 'Acuerdos y anuncio'
        for node in content.find_all(['h4', 'a']):
            if node.name == 'h4':
                section = node.get_text(' ', strip=True)
                continue
            href = node.get('href')
            if not href:
                continue
            url = _canonical(urljoin(source_url, href))
            parts = urlsplit(url)
            is_pdf = parts.hostname == 'www.villava.es' and parts.path.lower().endswith('.pdf')
            is_bon = parts.hostname in {'www.navarra.es', 'bon.navarra.es'} and '/2015/105/Anuncio-15' in parts.path
            if not (is_pdf or is_bon):
                raise ValueError(f'Unreviewed link in PGM document inventory: {url}')
            label = node.get_text(' ', strip=True)
            if not label:
                raise ValueError('Unlabelled PGM document')
            documents.setdefault(url, {'titulo': label, 'seccion': section, 'url': url,
                                       'url_pagina': source_url, 'tipo': 'pdf' if is_pdf else 'anuncio_bon'})
        if not any(d['seccion'].startswith('Plan Urbanístico Municipal') for d in documents.values()):
            raise ValueError('PGM memory document missing')
        if not any(d['seccion'] == 'Planos' for d in documents.values()):
            raise ValueError('PGM plan documents missing')
        return [{
            'id': 'villava-pgm', 'municipio': 'Villava / Atarrabia', 'codigo_ine': '31258',
            'provincia': 'Navarra', 'titulo': 'Plan General Municipal de Villava / Atarrabia',
            'tipo': 'planeamiento_urbanistico', 'url': source_url, 'source': 'ayuntamiento',
            'origen': 'inventario_documentacion_pgm', 'url_inventario': INVENTORY,
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'acuerdos_documentados': agreements, 'estado_actual': 'no verificado',
            'descripcion': '\n'.join(paragraphs), 'documentos': list(documents.values()),
            'cobertura': 'Documentación histórica del PGM enlazada actualmente por transparencia; no acredita estado vigente ni todas sus modificaciones.',
            'geometry': None, 'lat': None, 'lon': None, 'geometry_status': 'unavailable',
            'publication_ready': False,
        }]

    def _fetch(self, url, name):
        response = requests.get(url, timeout=35, headers={'User-Agent': 'municipio-villava/1.0'})
        response.raise_for_status()
        if urlsplit(response.url).hostname != 'www.villava.es':
            raise ValueError('Source redirected outside official municipal website')
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_bytes(response.content)
        return response.text, response.url

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        inventory, _ = self._fetch(INVENTORY, 'inventory.html')
        plan_url = self.discover_plan(inventory)
        html, final_url = self._fetch(plan_url, 'pgm.html')
        rows = self.parse_plan(html, _canonical(final_url))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [INVENTORY, final_url],
                'coverage': 'partial_historical_pgm', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh of this bounded document inventory. No date-based cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
