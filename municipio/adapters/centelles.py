"""Centelles: current municipal planning documents and physical-works inventory."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.centelles.cat/'
PLANNING = BASE + 'ajuntament/informacio-oficial/planejament-urbanistic'
WORKS = BASE + 'viure/urbanisme-i-medi-ambient/urbanisme'
LIMITATIONS = [
    'Partial coverage: current planning-document inventory and PROJECTE D’OBRES / Projecte executiu Vapor only; not the historical RPUC register.',
    'General PGO, PEPCH, mobility and regional-plan links on Urbanisme are outside this snapshot.',
    'Surface-right agreement for Osonament is excluded: not a verified construction project or granted licence.',
    'Document labels are the provenance; PDF bodies are not parsed. No inferred approval or publication dates.',
    'No verified project coordinates or geometry. No granted-licence extraction.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _guard(soup):
    # These are unpaginated curated pages today. Refuse a changed inventory
    # rather than silently exporting just the first page.
    for a in soup.select('a[href]'):
        rel = a.get('rel', [])
        if ('next' in rel or _text(a).casefold() in
                {'següent', 'siguiente', 'next', '»', '›'} or
                re.search(r'[?&](?:page|pagina|offset|start)=', a['href'], re.I)):
            raise ValueError('Centelles inventory has pagination; crawler review required')
    if soup.select('.pagination, .paginacio, .pager'):
        raise ValueError('Centelles pagination detected')


def _documents(node, source):
    docs = []
    for a in node.select('a[href]'):
        url = urljoin(BASE, a['href'])  # municipal pages declare a root <base>
        if urlparse(url).hostname != 'www.centelles.cat' or not urlparse(url).path.lower().endswith('.pdf'):
            raise ValueError('Unexpected non-municipal/PDF inventory document')
        docs.append({'titulo': _text(a), 'url': url, 'source_url': source})
    return docs


def _record(key, title, source, kind):
    return {
        'id': 'centelles-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
        'municipio': 'Centelles', 'codigo_ine': '08067', 'provincia': 'Barcelona',
        'titulo': title, 'tipo': kind, 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'url': source, 'source': 'ayuntamiento',
        'origen': 'inventario_documental_municipal', 'documentos': [],
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'coverage': 'partial_current_inventory',
    }


def _finish(rows):
    for row in rows:
        docs = {doc['url']: doc for doc in row['documentos']}
        if not docs:
            raise ValueError('Centelles instrument has no source documents')
        row['documentos'] = list(docs.values())
        row['url_documento'] = row['documentos'][0]['url']
        row['descripcion'] = '\n'.join(d['titulo'] for d in row['documentos'])
    if not rows:
        raise ValueError('No supported Centelles records; source markup may have changed')
    return rows


class CentellesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='centelles', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE.rstrip('/'))

    @staticmethod
    def parse_planning(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        _guard(soup)
        heading = next((h for h in soup.select('h2.sectionTitle')
                        if _text(h) == 'Planejament urbanístic - Documentació'), None)
        inventory = heading.find_next_sibling('ul') if heading else None
        if inventory is None:
            raise ValueError('Missing Centelles planning inventory')
        rows = {}
        current = None
        for node in inventory.find_all(['li', 'ul'], recursive=False):
            # The actual page places subsidiary ULs beside LI, not inside LI.
            if node.name == 'ul':
                if current is not None:
                    current['documentos'].extend(_documents(node, PLANNING))
                continue
            label = _text(node)
            low = label.casefold()
            if 'dret de superfície' in low and 'osonament' in low:
                current = None
                continue
            if 'gavarra' in low:
                key, title = 'mp44-gavarra', 'Modificació puntual número 44 del PGOU de Centelles: ampliació del polígon industrial La Gavarra'
            elif 'mp42' in low:
                key, title = 'mp42', label
            elif 'mp39' in low:
                key, title = 'mp39-casa-pujol', label
            elif 'casa ripoll' in low:
                key, title = 'casa-ripoll', label
            elif 'mp45' in low:
                key, title = 'mp45', label
            elif 'pla de millora urbana' in low and 'pilar' in low:
                key, title = 'pmu-pilar-3', label
            else:
                raise ValueError(f'Unclassified Centelles planning entry: {label}')
            current = rows.setdefault(key, _record(key, title, PLANNING, 'planeamiento_urbanistico'))
            current['documentos'].extend(_documents(node, PLANNING))
        result = _finish(list(rows.values()))
        # Only the explicitly labelled certificate establishes this agreement
        # date; the page update and month-only document labels do not.
        for row in result:
            for doc in row['documentos']:
                match = re.search(r"Certificat del Ple de l'Ajuntament (\d{2})/(\d{2})/(\d{4})\. Aprovació provisional", doc['titulo'])
                if match:
                    agreement = date(int(match[3]), int(match[2]), int(match[1])).isoformat()
                    doc['fecha_acuerdo'] = agreement
                    row.update(fecha_acuerdo=agreement, fecha_aprob=agreement,
                               fase='aprobación provisional', fecha_acuerdo_source_url=doc['url'])
        return result

    @staticmethod
    def parse_works(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        _guard(soup)
        heading = next((h for h in soup.select('h2.sectionTitle') if _text(h) == 'Documentació'), None)
        if heading is None:
            raise ValueError('Missing Centelles works documentation')
        rows = []
        active = False
        vapor_title = None
        for node in heading.next_siblings:
            if getattr(node, 'name', None) == 'h2':
                break
            if not getattr(node, 'name', None):
                continue
            label = _text(node)
            if label == "PROJECTE D'OBRES":
                active = True
                continue
            if not active:
                continue
            if label == 'Projecte executiu Vapor':
                vapor_title = label
                continue
            if node.name != 'ul':
                continue
            docs = _documents(node, WORKS)
            if vapor_title:
                row = _record('projecte-executiu-vapor', vapor_title, WORKS, 'proyecto_obra')
                row['documentos'] = docs
                rows.append(row)
            else:
                for doc in docs:
                    if not re.search(r'projecte.*(?:reforma|rehabilitació|urbanització|instal·lació|construcció)', doc['titulo'], re.I):
                        raise ValueError('Unclassified physical-works document')
                    row = _record(doc['url'], doc['titulo'], WORKS, 'proyecto_obra')
                    row['documentos'] = [doc]
                    rows.append(row)
        return _finish(rows)

    def _fetch(self, url, name):
        with requests.get(url, timeout=(10, 40), stream=True, headers={
                'User-Agent': self.config.get('user_agent', 'municipio-centelles/1.0')}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'www.centelles.cat':
                raise ValueError('Unexpected Centelles source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Centelles inventory exceeds response size limit')
                chunks.append(chunk)
            body = b''.join(chunks)
            if self.config.get('capture_dir'):
                path = Path(self.config['capture_dir'])
                path.mkdir(parents=True, exist_ok=True)
                (path / (name + '.html')).write_bytes(body)
            return body.decode('utf-8')

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self.parse_planning(self._fetch(PLANNING, 'planejament'))
        rows += self.parse_works(self._fetch(WORKS, 'urbanisme'))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [PLANNING, WORKS],
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Full refresh of both curated inventories, not a date-filtered delta.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No granted-licence inventory implemented'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
