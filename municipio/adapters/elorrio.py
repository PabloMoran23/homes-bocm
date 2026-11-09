"""Elorrio's municipal PGOU revision: one instrument, all listed documents.

This is a complete snapshot of a single-plan document inventory, not a register
of every municipal work. Document links describe the listing, not PDF contents.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOME = 'https://hapo-elorrio.eus/es'
NOTICE = 'https://www.elorrio.eus/es-ES/Noticias/Paginas/20260930-hapo-elorrio-aurrerakina.aspx'
LIMITATIONS = [
    'Partial municipal coverage: only the PGOU revision document inventory; no works or licence register.',
    'Publication date belongs to the municipal exposure announcement, not the documents or an approval agreement.',
    'PDF links retained as listed; their full contents and availability are not individually validated.',
    'The source repeats AA.2.2.A.pdf under AE.2.2.A; aliases are retained without correcting the source.',
    'No verified vector geometry or coordinates; PDF plans are not georeferenced by this adapter.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # This inventory is currently a single page. Fail closed if pagination is
    # introduced; never silently accept page one or a configured item limit.
    for link in soup.select('a[href]'):
        label = link.get_text(' ', strip=True).casefold()
        if (set(link.get('rel', [])) & {'next', 'prev'} or
                re.search(r'^(siguiente|anterior|next|previous|hurrengoa|[»›])', label) or
                'page=' in link['href'] or link.find_parent(class_=re.compile('pager|pagination'))):
            raise ValueError('PGOU inventory pagination requires crawler review')
    return soup


class ElorrioAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def discover_inventory(html):
        soup = _soup(html)
        urls = {urljoin(HOME, a['href']) for a in soup.select('a[href]')
                if a.get_text(' ', strip=True).casefold() == 'documentos'}
        if len(urls) != 1:
            raise ValueError('Missing or ambiguous PGOU document inventory')
        url = urls.pop()
        if urlsplit(url).hostname != 'hapo-elorrio.eus':
            raise ValueError('Unexpected inventory host')
        return url

    @staticmethod
    def parse_inventory(html, source_url):
        soup = _soup(html)
        body = soup.select_one('article .field--name-body')
        if body is None or 'Documentos disponibles' not in body.get_text(' ', strip=True):
            raise ValueError('PGOU document inventory markup missing')
        documents = {}
        phase = None
        phases = []
        for tag in body.find_all(['p', 'a']):
            text = ' '.join(tag.get_text(' ', strip=True).split())
            if tag.name == 'p' and re.match(r'^Fases?\s+\d', text, re.I):
                phase = text
                if phase not in phases:
                    phases.append(phase)
            if tag.name != 'a' or not tag.get('href'):
                continue
            url = urljoin(source_url, tag['href'])
            if not urlsplit(url).path.casefold().endswith('.pdf'):
                continue
            if not phase or not text or urlsplit(url).scheme != 'https':
                raise ValueError('Document without phase/title or unsafe URL')
            entry = documents.setdefault(url, {
                'titulo': text, 'url': url, 'source_url': source_url,
                'referencias': [], 'provenance': 'enlace del inventario municipal PGOU',
            })
            ref = {'titulo': text, 'fase_documental': phase}
            if ref not in entry['referencias']:
                entry['referencias'].append(ref)
        if not phases or not re.fullmatch(r'Fase 3:\s*Exposición Pública del Avance', phases[0], re.I):
            raise ValueError('PGOU current phase changed; review semantics before extraction')
        titles = {d['titulo'] for d in documents.values()}
        if not {'Memoria', 'Resumen ejecutivo', 'DIE(Documento Inicial Estratégico)'} <= titles:
            raise ValueError('Missing substantive Avance planning documents')
        return [{
            'id': 'elorrio-proy-revision-pgou', 'municipio': 'Elorrio',
            'codigo_ine': '48032', 'provincia': 'Bizkaia',
            'titulo': 'Revisión del Plan General de Ordenación Urbana de Elorrio',
            'tipo': 'planeamiento_urbanistico', 'fase': 'exposición pública del avance',
            'fases_documentales': phases, 'fecha': None,
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': source_url, 'source': 'ayuntamiento', 'origen': 'inventario_documental_pgou',
            'documentos': list(documents.values()),
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False, 'limitaciones': LIMITATIONS,
        }]

    @staticmethod
    def parse_provenance(html):
        soup = BeautifulSoup(html, 'html.parser')
        if not any(urljoin(NOTICE, a['href']) == HOME for a in soup.select('a[href]')):
            raise ValueError('Municipal announcement no longer endorses PGOU portal')
        if 'exposición pública del Avance del PGOU de Elorrio' not in soup.get_text(' ', strip=True):
            raise ValueError('Municipal PGOU announcement missing')
        dates = {s.get_text(strip=True) for s in soup.select('span.date')}
        if len(dates) != 1:
            raise ValueError('Ambiguous municipal announcement publication date')
        return datetime.strptime(dates.pop(), '%d/%m/%Y').date().isoformat()

    def _fetch(self, url):
        response = requests.get(url, timeout=35, headers={'User-Agent': 'municipio-elorrio/1.0'})
        response.raise_for_status()
        response.encoding = 'utf-8'
        # Optional local captures for reproducible live validation.
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = 'notice' if url == NOTICE else ('home' if url == HOME else 'inventory')
            (directory / (name + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        published = self.parse_provenance(self._fetch(NOTICE))
        inventory = self.discover_inventory(self._fetch(HOME))
        rows = self.parse_inventory(self._fetch(inventory), inventory)
        for row in rows:
            row['fecha_publicacion'] = published
            row['fecha_publicacion_source_url'] = NOTICE
            row['source_urls'] = [NOTICE, HOME, inventory]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [NOTICE, HOME, inventory],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
