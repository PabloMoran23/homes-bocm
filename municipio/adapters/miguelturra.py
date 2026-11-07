"""Snapshot of the official planning inventory; no licence or geometry inference."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.miguelturra.es/ayuntamiento/normas-municipales/normas-urbanisticas'
SUPPORTED = re.compile(r'^(Plan de Ordenación Municipal|Modificación puntual|Corre[c]?ción de errores|Correción de errores)', re.I)
MONTHS = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5,
          'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9,
          'octubre': 10, 'noviembre': 11, 'diciembre': 12}


def official(url):
    p = urlparse(url)
    return p.scheme == 'https' and p.netloc == 'www.miguelturra.es'


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    view = soup.select_one('.view-ordenanzas')
    if view is None:
        raise ValueError('Missing official planning inventory')
    entries = {}
    for a in view.select('.teaser__headline a[href]'):
        title = a.get_text(' ', strip=True)
        target = urljoin(url, a['href'])
        if not SUPPORTED.match(title):
            continue  # e.g. parcel information sheet, not an independent plan
        if not official(target) or not urlparse(target).path.startswith('/ordenanzas/'):
            raise ValueError('Unexpected planning detail URL')
        entries[target] = title
    if not entries:
        raise ValueError('No named planning instruments')
    pages = set()
    for a in view.select('.pager a[href], a[rel~=next]'):
        target = urljoin(url, a['href'])
        if not official(target) or urlparse(target).path != urlparse(SOURCE).path:
            raise ValueError('Unsupported inventory pagination')
        pages.add(target)
    # Detect pagination outside the view, too; do not silently take page one.
    for a in soup.select('.pager a[href], a[rel~=next]'):
        if a not in view.select('.pager a[href], a[rel~=next]'):
            raise ValueError('Pagination outside reviewed inventory structure')
    return entries, pages


def parse_detail(html, url, expected_title):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.node')
    title = article.select_one('.field--name-title') if article else None
    if title is None or title.get_text(' ', strip=True) != expected_title:
        raise ValueError('Missing or changed planning detail title')
    docs = {}
    for a in article.select('.field--name-field-ordenanzas-archivo a[href]'):
        target = urljoin(url, a['href'])
        if not official(target) or not urlparse(target).path.startswith('/sites/default/files/ordenanzas_archivos/'):
            raise ValueError('Unexpected planning document URL')
        docs[target] = {'titulo': a.get_text(' ', strip=True), 'url': target, 'source_url': url}
    if not docs:
        raise ValueError('Planning instrument lacks source documents')
    body = article.select_one('.field--name-body')
    text = body.get_text(' ', strip=True) if body else ''
    row = {
        'id': 'miguelturra-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Miguelturra', 'codigo_ine': '13056', 'provincia': 'Ciudad Real',
        'titulo': expected_title, 'tipo': 'planeamiento_urbanistico',
        'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_normas_urbanisticas',
        'inventory_url': SOURCE, 'documentos': list(docs.values()),
        'source_urls': [url], 'publication_ready': False, 'geometry_status': 'unavailable',
        'lat': None, 'lon': None, 'geometry': None,
    }
    if text:
        row['descripcion'] = text
    # An explicitly labelled BOP publication is not the approval date.
    publication = re.search(r'\(BOP (\d{4}-\d{2}-\d{2})\)', expected_title)
    if publication:
        row['fecha_publicacion'] = date.fromisoformat(publication[1]).isoformat()
        row['fecha_publicacion_fuente'] = {'url': url, 'texto': publication[0], 'medio': 'BOP'}
    approval = re.search(r'sesión de fecha (\d{1,2}) de (\w+) de (\d{4}) acordó aprobar definitivamente', text, re.I)
    if approval:
        value = date(int(approval[3]), MONTHS[approval[2].lower()], int(approval[1])).isoformat()
        row.update(fecha_acuerdo=value, fecha_aprob=value,
                   fecha_acuerdo_fuente={'url': url, 'texto': approval[0]})
    decree = re.search(r'Decreto de la Alcaldía nº [\d/]+ de fecha (\d{1,2}) de (\w+) de (\d{4}), se ha resuelto someter a información pública', text, re.I)
    if decree:
        row['fecha_acuerdo'] = date(int(decree[3]), MONTHS[decree[2].lower()], int(decree[1])).isoformat()
        row['fecha_acuerdo_fuente'] = {'url': url, 'texto': decree[0]}
        row['fase_documentada'] = 'información pública (según la ficha; no acredita estado actual)'
    return row


def group_instruments(rows):
    """Keep the published 2008 correction with the POM, not as another project."""
    plans = [r for r in rows if re.match(r'^Plan de Ordenación Municipal\b', r['titulo'], re.I)]
    corrections = [r for r in rows if re.match(r'^Corr', r['titulo'], re.I)]
    if corrections and len(plans) != 1:
        raise ValueError('Cannot unambiguously attach POM corrections')
    for correction in corrections:
        plan = plans[0]
        plan['documentos'].extend(correction['documentos'])
        plan['source_urls'].extend(correction['source_urls'])
        plan.setdefault('documentos_relacionados', []).append({
            'titulo': correction['titulo'], 'url': correction['url'], 'relacion': 'corrección de errores'})
    return [r for r in rows if r not in corrections]


class MiguelturraAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        if not official(url):
            raise ValueError('Non-official source')
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-miguelturra/1.0'})
        response.raise_for_status()
        if not official(response.url) or urlparse(response.url).path != urlparse(url).path:
            raise ValueError('Unexpected source redirect')
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML source')
        capture = self.config.get('evidence_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pending, visited, entries = {SOURCE}, set(), {}
        while pending:
            url = min(pending)
            pending.remove(url)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Pagination safety limit reached; no output written')
            found, pages = parse_inventory(self._fetch(url), url)
            visited.add(url)
            entries.update(found)
            pending.update(pages - visited)
        rows = group_instruments([parse_detail(self._fetch(url), url, title)
                                  for url, title in sorted(entries.items())])
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'inventory_pages': len(visited),
                'source_urls': sorted(visited | set(entries)),
                'coverage': 'published_municipal_planning_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
