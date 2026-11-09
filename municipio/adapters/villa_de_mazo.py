"""Current PGO dossier linked by Villa de Mazo, grouped as one instrument."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL_URL = 'https://villademazo.com/el-ayuntamiento/gabinete-tecnico/'
GOV_HOST = 'www.gobiernodecanarias.org'
LIMITATIONS = [
    'Only the current PGO dossier linked by the municipal website; not the historical planning archive or all public works.',
    'Documents grouped as one instrument; no licence grants, final approval, legal validity or execution inferred.',
    'No publication/agreement dates normalized; source document titles retain their explicit dates.',
    'No verified geometry; PDF/ZIP contents are linked, not parsed.',
]


def reject_pagination(soup):
    for a in soup.select('a[href]'):
        if (a.get('rel') and 'next' in a['rel']) or re.fullmatch(
            r'(siguiente(?:\s*[»›>])?|next|[»›])', a.get_text(' ', strip=True), re.I
        ) or any('pagin' in c.lower() for c in a.get('class', [])):
            raise ValueError('Pagination detected: review dossier coverage before extraction')
    if soup.select_one('.pagination, .paginacion, .pager'):
        raise ValueError('Pagination detected: review dossier coverage before extraction')


def discover_dossier(html, url=MUNICIPAL_URL):
    soup = BeautifulSoup(html, 'html.parser')
    targets = set()
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() == 'plan general de ordenación':
            target = urljoin(url, a['href'])
            p = urlparse(target)
            if p.scheme != 'https' or p.hostname != GOV_HOST or not p.path.startswith(
                '/planificacionterritorial/materias/exposicion-de-planes-y-normas/'
            ):
                raise ValueError('Municipal PGO link no longer points to the reviewed official inventory')
            targets.add(target.split('#')[0])
    if len(targets) != 1:
        raise ValueError('Expected one unambiguous official municipal PGO link')
    return targets.pop()


def parse_dossier(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#centercontainer')
    if content is None:
        raise ValueError('Official dossier content missing')
    reject_pagination(content)
    headings = [h.get_text(' ', strip=True) for h in content.select('h2.titulo-modernizacion')
                if re.search(r'Plan General de Ordenaci[oó]n.*Villa de Mazo', h.get_text(' ', strip=True), re.I)]
    if len(headings) != 1:
        raise ValueError('Expected one named Villa de Mazo planning instrument')
    docs = {}
    for a in content.select('.texto-rico-basico a[href]'):
        target = urljoin(url, a['href'])
        p = urlparse(target)
        if p.path.lower().endswith(('.pdf', '.zip')):
            if p.scheme != 'https' or p.hostname != GOV_HOST or not p.path.startswith('/planificacionterritorial/descargas/'):
                raise ValueError('Unexpected document provenance')
            docs.setdefault(target, {'titulo': a.get_text(' ', strip=True), 'url': target,
                                     'source_url': url, 'formato': p.path.rsplit('.', 1)[1].lower()})
    if not docs or not any(d['formato'] == 'zip' for d in docs.values()):
        raise ValueError('PGO dossier lacks its full planning document archive')
    return [{
        'id': 'villa-de-mazo-pgo-supletorio', 'municipio': 'Villa de Mazo',
        'codigo_ine': '38053', 'provincia': 'Santa Cruz de Tenerife',
        'titulo': headings[0], 'tipo': 'planeamiento_urbanistico',
        'url': url, 'inventory_url': url, 'municipal_source_url': MUNICIPAL_URL,
        'source': 'ayuntamiento', 'source_organismo': 'Gobierno de Canarias',
        'origen': 'expediente_pgo_enlazado_por_ayuntamiento',
        'documentos': list(docs.values()), 'publication_ready': False,
        'geometry_status': 'unavailable', 'coverage': 'current_municipally_linked_pgo_dossier',
        'limitations': list(LIMITATIONS),
    }]


class VillaDeMazoAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'})
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(url).hostname:
            raise ValueError('Unexpected source redirect')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            name = 'municipal.html' if url == MUNICIPAL_URL else 'dossier.html'
            (directory / name).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        url = discover_dossier(self._fetch(MUNICIPAL_URL))
        rows = parse_dossier(self._fetch(url), url)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [MUNICIPAL_URL, url],
                'limitations': list(LIMITATIONS)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
