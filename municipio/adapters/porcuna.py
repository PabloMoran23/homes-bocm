"""Porcuna's public transparency inventories, grouped by instrument folder.

Only the planning and public-works branches are covered. Session-dependent
Wicket actions are resolved afresh; output uses stable public folder/document URLs.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ORIGIN = 'https://porcuna.sedelectronica.es'
INVENTORIES = (
    ORIGIN + '/transparency/11910f2d-ff3b-40e8-9ec4-52a684af7ec9/',
    ORIGIN + '/transparency/160122fa-7bb1-4276-8ea7-50f8cc045082/',
)
LIMITATIONS = [
    'Cobertura parcial: inventarios públicos 7.1 Planeamiento y 7.4 Obras públicas; no es un histórico municipal completo.',
    'Censo de instalaciones con amianto excluido: inventario patrimonial, no proyecto de obra.',
    'No se extraen licencias concedidas, noticias, contratación ni el tablón de anuncios.',
    'Documentos agrupados según carpeta municipal; no se verifica vigencia ni ejecución actual.',
    'Sin fechas de acuerdo/publicación verificadas ni geometrías. La fecha de creación del documento no se usa como aprobación.',
]


def official_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'porcuna.sedelectronica.es':
        raise ValueError('Unexpected source outside Porcuna public sede')
    return url


def parse_inventory(html, url):
    """Return folder actions and stable document references; fail on truncation."""
    official_url(url)
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.TransparencyListPanel')
    if table is None:
        raise ValueError('Missing municipal transparency inventory')
    # Current scoped inventories fit on one page. A future pagination change
    # must fail visibly rather than quietly returning the first ten entries.
    for more in soup.select('.more_results a, .more_results button'):
        if not more.has_attr('disabled') and more.get('aria-disabled') != 'true':
            raise ValueError('Inventory pagination requires additional pages; refusing partial extraction')
    folders, documents = [], {}
    for a in table.select('a.gIconLink'):
        title = a.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            count = re.search(r'\(\s*(\d+)\s*\)\s*$', title)
            action = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
            if not count or not action:
                raise ValueError('Unrecognised municipal folder/action')
            folders.append({'title': title[:count.start()].strip(),
                            'count': int(count[1]),
                            'action': official_url(urljoin(url, action[1]))})
        else:
            target = official_url(urljoin(url, a.get('href', '')))
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(target).path):
                raise ValueError('Unrecognised municipal document link')
            documents[target] = {'titulo': title, 'url': target,
                                 'descripcion': a.get('title', '').strip(),
                                 'inventory_url': url}
    return folders, list(documents.values())


def make_record(title, url, documents):
    """A leaf folder is one instrument, irrespective of its document count."""
    if not documents or 'CENSO' in title.upper():
        return None
    if not re.match(r'^(MODIFICACI[ÓO]N|ESTUDIO\b|ESTACI[ÓO]N DEPURADORA\b)', title, re.I):
        raise ValueError('Unclassified populated inventory folder: ' + title)
    return {
        'id': 'porcuna-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Porcuna', 'provincia': 'Jaén', 'codigo_ine': '23069',
        'titulo': title,
        'tipo': 'proyecto de infraestructura' if title.upper().startswith('ESTACIÓN') else 'instrumento de planeamiento',
        'url': url, 'source': 'ayuntamiento', 'origen': 'portal_transparencia',
        'documentos': sorted(documents, key=lambda d: d['url']),
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'inventario documental municipal parcial',
    }


class PorcunaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='porcuna', config=None, base_url=''):
        super().__init__(slug, config, base_url or ORIGIN + '/transparency')
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'municipio-porcuna/1.0 (public planning inventory)'
        self.source_urls = set()
        self._visited = set()

    def _get(self, url, ajax=False, referer=None):
        official_url(url)
        headers = {'Wicket-Ajax': 'true', 'Referer': referer} if ajax else {}
        response = self.session.get(url, headers=headers, timeout=40)
        response.raise_for_status()
        official_url(response.url)
        if not ajax:
            self.source_urls.add(response.url)
            if self.config.get('evidence_dir'):
                folder = Path(self.config['evidence_dir'])
                folder.mkdir(parents=True, exist_ok=True)
                key = hashlib.sha256(response.url.encode()).hexdigest()[:16]
                (folder / (key + '.html')).write_text(response.text, encoding='utf-8')
        return response

    def _open_folder(self, parent, title):
        # Reload parent to obtain a current action for this anonymous session.
        response = self._get(parent)
        folders, _ = parse_inventory(response.text, response.url)
        matches = [f for f in folders if f['title'] == title]
        if len(matches) != 1:
            raise ValueError('Folder disappeared or is ambiguous: ' + title)
        folder = matches[0]
        response = self._get(folder['action'], ajax=True, referer=parent)
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Wicket did not provide public folder location')
        target = official_url(urljoin(response.url, location))
        if not re.fullmatch(r'/transparency/[0-9a-f-]{36}/', urlparse(target).path):
            raise ValueError('Unexpected public folder destination')
        return target, folder['count']

    def _walk(self, url, title=None, expected=None):
        if url in self._visited:
            raise ValueError('Repeated inventory folder (cycle or duplicate)')
        self._visited.add(url)
        response = self._get(url)
        folders, documents = parse_inventory(response.text, response.url)
        rows = []
        total = len(documents)
        if documents:
            if not title or folders:
                raise ValueError('Mixed document/folder layout needs explicit grouping review')
            row = make_record(title, url, documents)
            if row:
                rows.append(row)
        for folder in folders:
            target, count = self._open_folder(url, folder['title'])
            if count != folder['count']:
                raise ValueError('Inventory changed during extraction')
            children, n = self._walk(target, folder['title'], count)
            rows.extend(children)
            total += n
        if expected is not None and total != expected:
            raise ValueError(f'Incomplete inventory {url}: expected {expected}, got {total}')
        return rows, total

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls, self._visited = set(), set()
        rows = []
        for url in INVENTORIES:
            records, _ = self._walk(url)
            rows.extend(records)
        if not rows:
            raise ValueError('No usable municipal instruments/projects found')
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate municipal instrument')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n'
                                  for r in sorted(rows, key=lambda r: r['id'])), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows),
                'source_urls': sorted(self.source_urls), 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full current snapshot; state is not advanced on a partial/failed read.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
