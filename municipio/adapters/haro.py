"""Haro's public planning inventory: discrete modifications and development plans.

This is a complete refresh of the supported inventory, not an incremental event log.
Documents are links, not independently counted projects or verified granted licences.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

INVENTORY = 'https://www.haro.org/es/servicios-municipales/urbanismo'
CATALOG = 'https://www.haro.org/es/ayuntamiento/urbanismo/1'
DETAIL = re.compile(r'^/es/ayuntamiento/urbanismo/\d+$')
MONTHS = dict(zip('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), range(1, 13)))
DATE = r'(\d{1,2})\s*(?:/\s*(\d{1,2})\s*/|(?:de\s+)?(' + '|'.join(MONTHS) + r')\s+(?:de\s+)?)(\d{4})'


def norm(text):
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


def labelled_date(text, label):
    match = re.search(label + r'\s*:?\s*(?:(?:por la |pleno |cotur\s*:?\s*|en el |en |bor )*)' + DATE, norm(text))
    if not match:
        return None
    day, month, name, year = match.groups()
    return date(int(year), int(month) if month else MONTHS[name], int(day)).isoformat()


def instrument_key(title, url):
    text = norm(title)
    ordinal = re.search(r'(\d+)a?\s+modificacion', text)
    if ordinal:
        # The first ordinal identifies the PGM instrument, even if it also
        # modifies PEPCHA. A standalone PEPCHA modification has its own series.
        family = 'pgm' if re.search(r'p\.?\s*g\.?\s*m\.?|plan general', text) else 'pepcha'
        return f'{family}-mod-{int(ordinal[1])}'
    return 'ficha-' + urlparse(url).path.rsplit('/', 1)[-1]


class HaroAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html, url=INVENTORY):
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.select('a[href]'):
            href = urljoin(url, a['href'])
            if a['href'] not in ('', '#') and (
                'next' in a.get('rel', []) or a.get_text(' ', strip=True) in {'›', '»'}
                or norm(a.get_text(' ', strip=True)) in {'siguiente', 'next'}
                or a.find_parent(class_=re.compile(r'pagination|paginacion', re.I))
                or (urlparse(href).path == urlparse(INVENTORY).path and urlparse(href).query)
            ):
                raise ValueError('Inventory pagination detected; review traversal before extraction')
        entries = {}
        for a in soup.select('a[href]'):
            target = urljoin(url, a['href'])
            parsed = urlparse(target)
            if parsed.hostname != 'www.haro.org' or not DETAIL.fullmatch(parsed.path):
                continue
            block = a.find_parent(class_='pi-box')
            heading = block.select_one('h4') if block else None
            if not heading:
                raise ValueError('Planning inventory entry has no title')
            entries[target] = heading.get_text(' ', strip=True)
        if not entries:
            raise ValueError('No Haro planning inventory entries found')
        selected = []
        excluded = []
        for target, title in entries.items():
            text = norm(title)
            if re.match(r'^(0\.[012]\.|borrador |avance |plan general municipal |convenios urbanisticos|estudio de regeneracion)', text):
                excluded.append({'url': target, 'titulo': title})
            elif ('modificacion' in text or text.startswith('redelimitacion')
                    or text.startswith('correccion de error') or 'plan parcial del sector' in text):
                selected.append((target, title))
            else:
                raise ValueError(f'Unclassified inventory entry: {title}')
        if not selected:
            raise ValueError('No supported discrete planning instruments')
        return selected, excluded

    @staticmethod
    def parse_detail(html, url):
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.select_one('#page h3')
        description = soup.select_one('#page .pi-box')
        if not heading or not description:
            raise ValueError(f'Missing planning detail at {url}')
        title = heading.get_text(' ', strip=True)
        text = description.get_text(' ', strip=True)
        if not text:
            raise ValueError(f'Empty planning description at {url}')
        normalized = norm(title + ' ' + text)
        approval = labelled_date(text, r'(?:aprobacion\s+defin[ti]*iva|definitivamente)')
        phase = 'definitiva' if approval or re.search(r'aprobacion\s+defin[ti]*iva|definitivamente', normalized) else next(
            (label for label in ('provisional', 'inicial') if re.search(r'aprobacion\s+' + label, normalized)), None)
        publication = labelled_date(text, r'(?:publicacion en el bor|publicacion en bor|publicacion bor|publicado en el bor|publicado en bor|bor|publicacion)')
        documents = {}
        for a in soup.select('#page .pi-tab-pane a[href]'):
            target = urljoin(url, a['href'])
            if urlparse(target).hostname == 'www.haro.org' and re.fullmatch(r'/descargas/textos-planos/\d+', urlparse(target).path):
                documents[target] = {'titulo': a.get_text(' ', strip=True), 'url': target, 'source_url': url}
        return {'titulo': title, 'url': url, 'descripcion': text,
                'fase': 'aprobación ' + phase if phase else None,
                'fecha_aprob': approval, 'fecha_publicacion': publication,
                'fecha_publicacion_contexto': 'BOR (según ficha municipal)' if publication else None,
                'documentos': list(documents.values())}

    @staticmethod
    def group_details(details, catalog_documents=()):
        groups = {}
        rank = {None: 0, 'aprobación inicial': 1, 'aprobación provisional': 2, 'aprobación definitiva': 3}
        for detail in details:
            key = instrument_key(detail['titulo'], detail['url'])
            groups.setdefault(key, []).append(detail)
        rows = []
        for key, sources in groups.items():
            primary = max(sources, key=lambda s: rank[s['fase']])
            documents = {d['url']: d for source in sources for d in source['documentos']}
            for doc in catalog_documents:
                # Only ordinal instrument titles can be matched across pages.
                if '-mod-' in key and instrument_key(doc['titulo'], doc['source_url']) == key:
                    documents.setdefault(doc['url'], doc)
            rows.append({
                'id': 'haro-proy-' + key, 'municipio': 'Haro', 'provincia': 'La Rioja',
                'codigo_ine': '26071', 'tipo': 'planeamiento_urbanistico',
                'titulo': primary['titulo'], 'url': primary['url'],
                'descripcion': primary['descripcion'], 'fase': primary['fase'],
                'fecha': None, 'fecha_acuerdo': None,
                'fecha_aprob': primary['fecha_aprob'],
                'fecha_publicacion': primary['fecha_publicacion'],
                'fecha_publicacion_contexto': primary['fecha_publicacion_contexto'],
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
                'source_url': INVENTORY, 'fuentes': sources,
                'documentos': list(documents.values()),
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            })
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        source_urls = []
        captures = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-haro/1.0 (public planning research)'

            def fetch(url):
                response = session.get(url, timeout=35)
                response.raise_for_status()
                if urlparse(response.url).hostname != 'www.haro.org' or 'html' not in response.headers.get('Content-Type', ''):
                    raise ValueError(f'Unexpected planning response at {url}')
                source_urls.append(url)
                if self.config.get('capture_dir'):
                    path = Path(self.config['capture_dir']) / ('source-' + hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(response.content)
                    captures.append({'url': url, 'path': str(path), 'sha256': hashlib.sha256(response.content).hexdigest()})
                return response.text

            selected, excluded = self.parse_inventory(fetch(INVENTORY))
            details = []
            for url, title in selected:
                time.sleep(0.15)
                detail = self.parse_detail(fetch(url), url)
                if norm(detail['titulo']) != norm(title):
                    raise ValueError(f'Inventory/detail title mismatch at {url}')
                details.append(detail)
            # The general-plan catalogue mixes several instruments. Only links
            # explicitly identifying a supported modification are attached.
            catalog = self.parse_detail(fetch(CATALOG), CATALOG)
        rows = self.group_details(details, catalog['documentos'])
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': source_urls,
                'captures': captures, 'excluded_inventory_entries': excluded,
                'detail_pages': len(details), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
