"""Two municipal planning document inventories, refreshed as complete snapshots."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.navas.cat'
SOURCES = {
    'poum': BASE + '/municipi/navas/poum/',
    'patrimoni': BASE + '/municipi/navas/pla-especial-urbanistic-de-proteccio-del-patrimoni-i-cataleg-de-bens-arquitectonics-historics-i-ambientals-de-navas/',
}
MONTHS = 'gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split()


def parse_inventory(html: str, instrument: str) -> dict:
    """One page describes one instrument; attachments never become projects."""
    source = SOURCES[instrument]
    soup = BeautifulSoup(html, 'html.parser')
    page = soup.select_one('main article.page-interior')
    heading = soup.select_one('main h1')
    if page is None or heading is None:
        raise ValueError('Missing municipal instrument content')
    # Reject newly paginated inventories rather than silently returning page one.
    for a in soup.select('a[href], button'):
        label = a.get_text(' ', strip=True).casefold()
        rel = a.get('rel', [])
        if 'next' in rel or label in {'següent', 'siguiente', 'next', "veure’n més", "veure'n més", 'load more'}:
            raise ValueError('Inventory pagination requires crawler review')
    title = heading.get_text(' ', strip=True)
    expected = 'ordenació urbanística municipal' if instrument == 'poum' else 'pla especial urbanístic de protecció del patrimoni'
    if expected not in title.casefold():
        raise ValueError('Unexpected instrument heading')
    paragraphs = [p.get_text(' ', strip=True) for p in page.select('article.content p')]
    description = '\n'.join(paragraphs)
    if 'Navàs' not in description:
        raise ValueError('Missing instrument narrative for Navàs')
    documents = {}
    blocks = page.select('article.file-block')
    for block in blocks:
        doc_title = block.select_one('h2.title')
        links = block.select('a[href]')
        if not doc_title or not links:
            raise ValueError('Incomplete document block')
        for a in links:
            url = urljoin(source, a['href'])
            parts = urlsplit(url)
            if parts.scheme != 'https' or parts.hostname != 'www.navas.cat' or not parts.path.startswith('/wp-content/uploads/') or not parts.path.lower().endswith('.pdf'):
                raise ValueError('Unexpected instrument document URL')
            documents.setdefault(url, {'titulo': doc_title.get_text(' ', strip=True), 'url': url, 'source_url': source})
    if not documents:
        raise ValueError('No instrument documents; navigation is not a record')
    row = {
        'id': 'navas-proy-' + hashlib.sha256(source.encode()).hexdigest()[:16],
        'municipio': 'Navàs', 'provincia': 'Barcelona', 'codigo_ine': '08141',
        'titulo': title, 'tipo': 'POUM' if instrument == 'poum' else 'plan_especial_urbanistico',
        'url': source, 'url_documento': next(iter(documents)),
        'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento_municipal',
        'descripcion': description, 'documentos': list(documents.values()),
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'fase': None, 'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False,
        'coverage': 'Partial: two municipal planning document pages; excludes notice board, amendments and licence register',
    }
    if instrument == 'poum':
        match = re.search(r"aprovat definitivament el mes d['’](\w+) de (\d{4})", description)
        if match and match[1] in MONTHS:
            row.update(fase='aprobación definitiva', fecha_aprob_mes=f'{match[2]}-{MONTHS.index(match[1]) + 1:02d}', fecha_aprob_texto=match[0])
        # A revised narrative must be reviewed, not assigned the old phase/date.
        elif 'aprovat definitivament' in description:
            raise ValueError('Unrecognized POUM approval date precision')
    return row


class NavasAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        with requests.get(url, timeout=35, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-navas/1.0'),
        }) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname != 'www.navas.cat':
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Municipal HTML exceeds reviewed size')
                chunks.append(chunk)
            raw = b''.join(chunks)
            if self.config.get('capture_dir'):
                path = Path(self.config['capture_dir'])
                path.mkdir(parents=True, exist_ok=True)
                key = next(key for key, value in SOURCES.items() if value == url)
                (path / f'{key}.html').write_bytes(raw)
            return raw.decode('utf-8')

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = [parse_inventory(self._fetch(url), key) for key, url in SOURCES.items()]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES.values()), 'publication_ready': False, 'coverage': 'partial'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
