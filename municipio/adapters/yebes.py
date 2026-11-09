"""Partial, grouped inventory from Yebes' anonymous transparency portal."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://yebes.sedelectronica.es'
INVENTORY = BASE + '/transparency/18d47a90-5cca-4c36-8320-64d40729eefb/'
# Deliberately scoped instruments; other transparency categories are not records.
INSTRUMENTS = {
    '7.1. PLANEAMIENTO URBANÍSTICO': ('Modificación núm. 2 del POM de Yebes', 'modificación del POM', None),
    '7.5. PROYECTO URBANIZACIÓN CALLE ERAS - CEMENTERIO': ('Proyecto de urbanización calle Eras - Cementerio', 'proyecto de urbanización', None),
    '7.7. MODIFICACIÓN PUNTUAL NÚM. 3 DEL POM': ('Modificación puntual núm. 3 del POM de Yebes', 'modificación del POM', None),
    '7.8 PROYECTOS EN TRAMITACIÓN': ('Modificación núm. 2 del Plan Parcial del sector 1 de Yebes (26004_MpPP)', 'modificación del plan parcial', 'en tramitación'),
}


def official(url):
    p = urlparse(url)
    if p.scheme != 'https' or p.netloc != 'yebes.sedelectronica.es':
        raise ValueError('Unexpected source host')
    return url


def parse_inventory(html, url):
    """Return every document and child folder; fail on unhandled pagination."""
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.TransparencyListPanel')
    if table is None or 'Ayuntamiento de Yebes' not in soup.get_text():
        raise ValueError('Missing Yebes public document inventory')
    text = soup.get_text(' ', strip=True).lower()
    if 'mostrar más' in text or soup.select('.pagination, .paging, a[rel="next"]'):
        raise ValueError('Inventory pagination requires investigation; refusing partial snapshot')
    docs, folders = [], []
    for a in table.select('a[href]'):
        title = a.get_text(' ', strip=True)
        href = a['href']
        if '/preview-document/' in href:
            docs.append({'titulo': title, 'url': official(urljoin(url, href)), 'inventory_url': url})
        elif 'exp' in a.get('class', []):
            count = re.search(r'\(\s*(\d+)\s*\)$', title)
            callback = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
            if not count or not callback:
                raise ValueError('Unrecognized folder/count/callback')
            folders.append({'titulo': title[:count.start()].strip(), 'count': int(count[1]),
                            'callback': official(urljoin(url, callback[1]))})
        else:
            raise ValueError('Unrecognized inventory entry')
    if not docs and not folders:
        raise ValueError('Empty inventory')
    return docs, folders


class YebesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []

    def _get(self, session, url, ajax=False):
        official(url)
        r = session.get(url, timeout=35, headers={'Wicket-Ajax': 'true'} if ajax else {}, allow_redirects=False)
        r.raise_for_status()
        if r.is_redirect:
            raise ValueError('Unexpected source redirect')
        if len(r.content) > 5_000_000:
            raise ValueError('Inventory response too large')
        if not ajax:
            self.source_urls.append(url)
            capture = self.config.get('capture_dir')
            if capture:
                dest = Path(capture)
                dest.mkdir(parents=True, exist_ok=True)
                (dest / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(r.content)
        return r

    def _folder(self, session, folder):
        response = self._get(session, folder['callback'], ajax=True)
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Missing public folder destination')
        target = official(urljoin(response.url, location))
        if not re.fullmatch(r'/transparency/[a-f0-9-]{36}/', urlparse(target).path):
            raise ValueError('Unexpected folder destination')
        return target

    def _documents(self, session, url, seen):
        if url in seen or len(seen) >= 30:
            raise ValueError('Cyclic or unexpectedly deep inventory')
        seen.add(url)
        docs, children = parse_inventory(self._get(session, url).text, url)
        for child in children:
            nested = self._documents(session, self._folder(session, child), seen)
            if len(nested) != child['count']:
                raise ValueError('Folder count mismatch; possible incomplete pagination')
            docs.extend(nested)
        if len({d['url'] for d in docs}) != len(docs):
            raise ValueError('Duplicate document links in instrument')
        return docs

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = []
        rows = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-yebes/1.0'
            _, folders = parse_inventory(self._get(session, INVENTORY).text, INVENTORY)
            for label, (title, kind, phase) in INSTRUMENTS.items():
                matches = [f for f in folders if f['titulo'] == label]
                if len(matches) != 1:
                    raise ValueError('Missing or ambiguous scoped instrument: ' + label)
                folder = matches[0]
                url = self._folder(session, folder)
                documents = self._documents(session, url, set())
                if len(documents) != folder['count']:
                    raise ValueError('Instrument document count mismatch')
                # These two folders have generic category names. A new, different
                # instrument must not be silently merged into the existing one.
                pattern = (r'mod.*?\b2\b.*?\bPOM\b' if label.startswith('7.1.') else
                           r'^26004_MpPP nº 2 S1 Yebes' if label.startswith('7.8 ') else None)
                if pattern and any(not re.search(pattern, d['titulo'], re.I) for d in documents):
                    raise ValueError('Unrecognized instrument in generic category')
                rows.append({
                    'id': 'yebes-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                    'municipio': 'Yebes', 'codigo_ine': '19326', 'provincia': 'Guadalajara',
                    'titulo': title, 'tipo': kind, 'fase': phase,
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': url, 'inventory_url': INVENTORY, 'documentos': documents,
                    'source': 'ayuntamiento', 'origen': 'portal_transparencia_inventario',
                    'descripcion': 'Inventario documental municipal; no certifica vigencia, aprobación ni ejecución.\n' +
                                   '\n'.join(d['titulo'] for d in documents),
                    'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                    'geometry_status': 'No verified project geometry extracted',
                })
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'coverage': 'four scoped municipal instrument folders; complete recursive document links'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
