"""Cunit's published planning inventory: complete snapshot, not a licence register."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.cunit.cat/informacio-i-serveis/urbanisme-i-obres/planejament-urbanisme/'
# Two municipal notices describe successive stages of this same instrument.
SUD2 = 'pla-parcial-sud2'
SUD2_NOTICES = {
    'aprovacio-definitiva-pla-parcial-sud2-cunit',
    'aprovacio-inicial-pla-parcial-sud-2-pla-de-cunit-2',
}
EXCLUDED = {'informacio-publica-documentacio-cessio-finca-per-construccio-institut'}
LIMITATIONS = [
    'Partial municipal coverage: the published Planejament inventory only; not all current planning or public works.',
    'Inventory statuses are source labels, not independently verified current legal validity.',
    'Land transfer for a future institute is excluded; no granted licences are extracted.',
    'Publication narratives and public-exposure dates are retained separately; publication dates are not inferred from exposure or URL filenames.',
    'Linked files are retained with provenance, not downloaded or certified accessible; some source URLs are malformed or use HTTP.',
    'No verified project geometry; coordinates remain null and publication_ready is false.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content')
    if content is None:
        raise ValueError('Missing Cunit content: possible login, error or changed markup')
    for node in content.select('[data-pagination]'):
        settings = json.loads(node['data-pagination'])
        if settings.get('type') != 'disabled' or int(settings.get('max_pages', 0)) > 1:
            raise ValueError('Pagination detected; crawler must be extended before extraction')
    for a in content.select('a[href]'):
        if 'next' in a.get('rel', []) or a.get_text(' ', strip=True).lower() in {'següent', 'siguiente', 'next', '»'}:
            raise ValueError('Pagination detected; refusing a partial snapshot')
    if content.select('.wpv-pagination-nav-links, .wpv-pagination-next-link, .pagination a[href]'):
        raise ValueError('Pagination controls detected')
    return soup, content


def _date(text):
    text = text.strip()
    return datetime.strptime(text, '%d/%m/%Y').date().isoformat() if text else None


class CunitAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.cunit.cat')

    @staticmethod
    def parse_inventory(html):
        _, content = _soup(html)
        rows = []
        tables = content.select('table')
        if len(tables) != 2:
            raise ValueError('Expected the two municipal planning tables')
        for table in tables:
            headers = [th.get_text(' ', strip=True) for th in table.select('thead th')]
            if headers not in [
                ['Títol', 'Aprovació inicial', 'Estat'],
                ['Títol', 'Apr. inicial', 'Apr. definitiva', 'Estat'],
            ]:
                raise ValueError('Changed approval-date table schema')
            for tr in table.select('tbody tr'):
                cells = tr.find_all('td', recursive=False)
                if len(cells) != len(headers) or not cells[0].select_one('a[href]'):
                    raise ValueError('Malformed planning row')
                a = cells[0].select_one('a[href]')
                url = urljoin(SOURCE, a['href'])
                parsed = urlparse(url)
                if parsed.hostname != 'www.cunit.cat' or not re.fullmatch(r'/planejament/[^/]+/', parsed.path):
                    raise ValueError('Unexpected planning detail URL')
                key = parsed.path.strip('/').split('/')[-1]
                if key in EXCLUDED:
                    continue
                rows.append({
                    'key': SUD2 if key in SUD2_NOTICES else key,
                    'titulo': a.get_text(' ', strip=True), 'url': url,
                    'fecha_aprob_inicial': _date(cells[1].get_text(strip=True)),
                    'fecha_aprob_definitiva': _date(cells[2].get_text(strip=True)) if len(cells) == 4 else None,
                    'estado_fuente': cells[-1].get_text(' ', strip=True),
                })
        if not rows:
            raise ValueError('No planning records in municipal inventory')
        if len({r['url'] for r in rows}) != len(rows):
            raise ValueError('Duplicate inventory URLs')
        return rows

    @staticmethod
    def parse_detail(html, url):
        soup, content = _soup(html)
        title = soup.select_one('h1.page-header-title')
        if not title or not content.select_one('.type-planejament'):
            raise ValueError('Not a municipal planning detail')
        docs = {}
        for a in content.select('a[href]'):
            href = a['href'].strip()
            target = urljoin(url, href)
            if not href or urlparse(target).scheme not in {'http', 'https'}:
                continue
            # Only dossier content, never menu/sidebar/site links.
            if not ('.pdf' in target.lower() or '/doc/' in target or '/ebop/' in target or '.sharepoint.com/' in target):
                continue
            docs.setdefault(target, {'titulo': a.get_text(' ', strip=True), 'url': target, 'url_origen': url})
        text = content.get_text(' ', strip=True)
        # Some documents are printed as plain URLs rather than anchors (FTTH).
        for target in re.findall(r'https?://[^\s<>]+\.pdf', text, re.I):
            docs.setdefault(target, {'titulo': 'URL documental en texto de la ficha', 'url': target, 'url_origen': url})
        if not docs:
            raise ValueError('Planning detail lacks source documents')
        return {
            'titulo': title.get_text(' ', strip=True), 'url': url,
            'descripcion': text,
            'documentos': list(docs.values()),
            'exposicion_publica_texto': [p.get_text(' ', strip=True) for p in content.select('p') if 'Exposició pública:' in p.get_text()],
            'publicaciones_texto': [p.get_text(' ', strip=True) for p in content.select('p') if re.search(r'Publicaci[oó]|Publicat', p.get_text(), re.I)],
        }

    @staticmethod
    def group_records(entries):
        groups = {}
        for row, detail in entries:
            groups.setdefault(row['key'], []).append((row, detail))
        records = []
        for key, items in groups.items():
            initial = {r['fecha_aprob_inicial'] for r, _ in items if r['fecha_aprob_inicial']}
            definitive = {r['fecha_aprob_definitiva'] for r, _ in items if r['fecha_aprob_definitiva']}
            if len(initial) > 1 or len(definitive) > 1:
                raise ValueError('Conflicting approval dates for one instrument')
            first, _ = items[0]
            docs = {}
            for _, detail in items:
                for doc in detail['documentos']:
                    docs.setdefault(doc['url'], {**doc, 'urls_origen': []})['urls_origen'].append(detail['url'])
            records.append({
                'id': 'cunit-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Cunit', 'provincia': 'Tarragona', 'codigo_ine': '43051',
                'titulo': 'Pla Parcial SUD 2 «Pla de Cunit 2»' if key == SUD2 else first['titulo'],
                'tipo': 'proyecto_urbanizacion' if 'urbanitzacio' in key else 'instrumento_urbanistico',
                'fase': 'aprobación definitiva' if definitive else 'aprobación inicial',
                'fecha': None, 'fecha_publicacion': None,
                'fecha_aprob': next(iter(definitive or initial), None),
                'fecha_aprob_inicial': next(iter(initial), None),
                'fecha_aprob_definitiva': next(iter(definitive), None),
                'url': first['url'], 'url_inventario': SOURCE,
                'source': 'ayuntamiento', 'origen': 'inventario_planejament',
                'fuentes': [{**row, **detail} for row, detail in items],
                'documentos': list(docs.values()),
                'descripcion': '\n\n'.join(detail['descripcion'] for _, detail in items),
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            })
        return records

    def _fetch(self, url):
        with requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=40, stream=True) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'www.cunit.cat':
                raise ValueError('Unexpected redirect outside municipal website')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Source exceeds response size limit')
                chunks.append(chunk)
            body = b''.join(chunks)
            if self.config.get('capture_dir'):
                folder = Path(self.config['capture_dir'])
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(body)
            return body.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        inventory = self.parse_inventory(self._fetch(SOURCE))
        entries = [(row, self.parse_detail(self._fetch(row['url']), row['url'])) for row in inventory]
        records = self.group_records(entries)
        self._write(out_jsonl, records)
        return {'status': 'ok', 'rows': len(records), 'source_urls': [SOURCE] + [r['url'] for r in inventory], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh: no date watermark may omit older dossiers' new documents.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
