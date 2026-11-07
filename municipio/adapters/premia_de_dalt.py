"""Partial, anonymous snapshot of Premià de Dalt's municipal planning inventory."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.premiadedalt.cat/ajuntament/normativa/planificacio-urbanistica'
# Reviewed exclusions are explicit; new unsupported groups fail closed.
EXCLUDED = {
    'can-nolla': 'Area folder mixes partial plan, urbanisation, reparcelling and agreements.',
    'cal-rei': 'Area folder mixes urbanisation and reparcelling documents.',
    'can-costa-abril-2025': 'Area folder mixes POUM amendment, urbanisation and reparcelling stages.',
    'can-botey-febrer-2025': 'Area folder mixes technical documentation and heritage amendment; amendment covered in heritage container.',
    'pistes-de-volei-al-carrer-montseny-maig-2024': 'Folder mixes urbanisation and provisional land-use instruments.',
    'habitatges-dus-turistic-marc-2024': 'Not verified as a distinct planning instrument; excluded from project coverage.',
}
CONTAINERS = {
    'modificacions-puntuals-del-poum-de-premia-de-dalt',
    'modificacio-del-pla-especial-de-proteccio-del-patrimoni-arquitectonic-i-ambiental',
}
PLANNING = re.compile(r'^(?:pla\b|modificaci\w*\b|delimitació\b|projecte pla\b)', re.I)
WORKS = re.compile(r'^(?:projecte\b|reforma\b|renovació\b|bassa\b|complex municipal\b)', re.I)


def _title(anchor):
    # Counts and icons are children of the heading, not part of its title.
    clone = BeautifulSoup(str(anchor), 'html.parser')
    for el in clone.select('span, i'):
        el.decompose()
    return clone.get_text(' ', strip=True)


class PremiaDeDaltAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.premiadedalt.cat')

    @staticmethod
    def parse_inventory(html: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        soup = BeautifulSoup(html, 'html.parser')
        core = soup.select_one('#content-core')
        root = soup.select_one('#content-core #accordionFolderList')
        if core is None or root is None:
            raise ValueError('Municipal planning accordion missing; no records emitted')
        # This reviewed source embeds all folders and documents in one response.
        # A future paginated listing must be implemented before it can be used.
        if soup.select('.listingBar, .pagination, a[rel~=next]'):
            raise ValueError('Pagination detected; refusing incomplete inventory')
        for a in core.select('a[href]'):
            if re.search(r'[?&](?:b_start|page|pagina|offset)=', a['href'], re.I):
                raise ValueError('Pagination link detected')
        rows, excluded, by_documents, by_title = [], [], {}, {}

        def instrument(anchor, body):
            title = _title(anchor)
            if not (PLANNING.match(title) or WORKS.match(title)):
                raise ValueError(f'Unreviewed inventory group: {title}')
            docs = {}
            for a in body.select('a[href]'):
                href = a['href']
                if href.startswith('#'):
                    continue
                url = urljoin(SOURCE, href)
                parsed = urlparse(url)
                if (parsed.scheme != 'https' or parsed.netloc != 'www.premiadedalt.cat'
                        or not parsed.path.startswith(urlparse(SOURCE).path + '/')
                        or '.pdf' not in parsed.path.lower()):
                    raise ValueError(f'Unreviewed document link in {title}: {url}')
                docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                                      'source_url': SOURCE + anchor['href']})
            if not docs:
                raise ValueError(f'Instrument has no published PDF documents: {title}')
            ref = {'titulo': title, 'url': SOURCE + anchor['href']}
            key = frozenset(docs)
            title_key = ' '.join(title.casefold().split()).rstrip(' .')
            existing = by_documents.get(key) or by_title.get(title_key)
            if existing is not None:
                existing['referencias_inventario'].append(ref)
                known = {d['url'] for d in existing['documentos']}
                existing['documentos'].extend(d for u, d in docs.items() if u not in known)
                by_documents[key] = existing
                return
            url = ref['url']
            row = {
                'id': 'premia-de-dalt-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                'municipio': 'Premià de Dalt', 'provincia': 'Barcelona', 'codigo_ine': '08230',
                'titulo': title, 'tipo': 'planeamiento_urbanistico' if PLANNING.match(title) else 'proyecto_obra',
                'fase': None, 'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'fecha_texto_fuente': title,
                'url': url, 'url_documento': next(iter(docs)),
                'documentos': list(docs.values()), 'referencias_inventario': [ref],
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
                'provenance': {'inventory_url': SOURCE, 'method': 'HTML folder title and linked PDF metadata; PDF contents not parsed'},
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'geometry_status': 'No verified project geometry extracted',
            }
            rows.append(row)
            by_documents[key] = row
            by_title[title_key] = row

        for panel in root.find_all('li', recursive=False):
            anchor = panel.select_one(':scope > .panel-heading a[href]')
            if anchor is None:
                raise ValueError('Inventory panel lacks heading')
            href = anchor['href']
            if not href.startswith('#'):
                if href == SOURCE + '/altres-planejaments-1':
                    excluded.append({'url': href, 'reason': 'External-register pointer, not an instrument inventory.'})
                    continue
                raise ValueError(f'Unexpected inventory navigation: {href}')
            group = href[1:]
            body = panel.find('ul', recursive=False)
            if body is None or body.get('id') != group:
                raise ValueError(f'Incomplete accordion group: {group}')
            if group in EXCLUDED:
                excluded.append({'url': SOURCE + href, 'reason': EXCLUDED[group]})
            elif group in CONTAINERS:
                for child in body.find_all('li', recursive=False):
                    a = child.select_one(':scope > p > a[href]')
                    nested = child.find('ul', recursive=False)
                    if a is None or nested is None or a['href'] != '#' + nested.get('id', ''):
                        raise ValueError('Planning container structure changed')
                    instrument(a, nested)
            else:
                instrument(anchor, body)
        if not rows:
            raise ValueError('No supported municipal instruments found')
        return rows, excluded

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=(10, 60), stream=True,
                          headers={'User-Agent': 'municipio-premia-de-dalt/1.0'}) as response:
            response.raise_for_status()
            if response.url.rstrip('/') != SOURCE:
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 5_000_000:
                    raise ValueError('Planning inventory exceeds reviewed response size')
                chunks.append(chunk)
            content = b''.join(chunks)
            if self.config.get('capture_dir'):
                capture = Path(self.config['capture_dir'])
                capture.mkdir(parents=True, exist_ok=True)
                (capture / 'planning-index.html').write_bytes(content)
            rows, excluded = self.parse_inventory(content.decode('utf-8'))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'excluded_groups': excluded, 'coverage': 'partial municipal planning inventory',
                'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Full current snapshot; never use a publication label as an update cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
