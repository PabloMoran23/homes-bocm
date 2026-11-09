"""Municipal planning snapshot: existing PGM and documented POUM advance."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.santhilari.cat'
SOURCE = BASE + '/categories_areastematiques/urbanisme/'
LIMITATIONS = [
    'Partial coverage: municipal Urbanisme catalogue, PGM and POUM advance only; not a complete planning history or public works register.',
    'POUM advance is not an approved replacement for the PGM. Phase reflects the published document, not verified present-day processing status.',
    'No granted licence register verified; application forms and explanatory POUM page excluded.',
    'No exact publication/agreement/approval dates or project geometries verified. Upload paths are not dates.',
    'PDF links retained; PDF contents and georeferencing are not parsed.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('.pagination, .nav-links, a[rel~=next], a.next, .page-numbers'):
        raise ValueError('Pagination detected: review crawler before accepting snapshot')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).lower() in {'següent', 'següents', 'next', 'siguiente', 'més resultats', 'carrega més'}:
            raise ValueError('Continuation detected: incomplete inventory')
    return soup


def _official(url):
    p = urlparse(url)
    if p.scheme != 'https' or p.hostname not in {'www.santhilari.cat', 'santhilari.cat'}:
        raise ValueError('Unexpected source host: ' + url)
    return url


def _documents(block, source):
    docs = {}
    for a in block.select('a[href]'):
        url = urljoin(source, a['href'])
        if urlparse(url).path.lower().endswith('.pdf'):
            _official(url)
            docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url, 'source_url': source})
    if not docs:
        raise ValueError('Planning source has no PDF documents: ' + source)
    return list(docs.values())


class SantHilariSacalmAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html):
        soup = _soup(html)
        h = soup.select_one('.intro-category h1')
        if not h or h.get_text(strip=True) != 'Urbanisme':
            raise ValueError('Unexpected municipal inventory')
        cards = {}
        for card in soup.select('.item-medium'):
            title = card.select_one('h2')
            if title:
                key = title.get_text(' ', strip=True)
                if key in cards:
                    raise ValueError('Duplicate inventory heading: ' + key)
                cards[key] = card
        required = ['Pla General Municipal d’Ordenació Urbana', 'Plànol d’ordenació urbana',
                    'Avanç de planejament', 'Programa de participació ciutadana']
        if any(key not in cards for key in required):
            raise ValueError('Planning inventory changed or incomplete')
        plan, map_card = (cards[key] for key in required[:2])
        desc = plan.select_one('.item-medium__description')
        text = desc.get_text(' ', strip=True)
        if 'Sant Hilari Sacalm' not in text or 'definitivament' not in text:
            raise ValueError('PGM identity/approval narrative missing')
        year = re.search(r'definitivament el (\d{4})', text)
        row = SantHilariSacalmAyuntamientoAdapter._row('pgm', required[0], 'PGM', SOURCE)
        row.update(descripcion=text, fase='aprobación definitiva',
                   ano_aprobacion=int(year[1]) if year else None,
                   documentos=_documents(plan, SOURCE) + _documents(map_card, SOURCE))
        pages = []
        for key in required[2:]:
            a = cards[key].select_one('.button-more-wrapper a[href]')
            if not a:
                raise ValueError('Missing POUM detail link')
            pages.append(_official(urljoin(SOURCE, a['href'])))
        if len(set(pages)) != 2:
            raise ValueError('Ambiguous POUM detail pages')
        return row, pages

    @staticmethod
    def _row(key, title, kind, url):
        return {'id': 'sant-hilari-sacalm-proy-' + key, 'municipio': 'Sant Hilari Sacalm',
                'codigo_ine': '17164', 'provincia': 'Girona', 'titulo': title, 'tipo': kind,
                'url': url, 'source': 'ayuntamiento', 'origen': 'planejament_municipal',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'geometry_status': 'No verified instrument geometry'}

    @staticmethod
    def parse_poum(pages):
        docs, descriptions, sources = {}, [], []
        for index, (url, html) in enumerate(pages):
            soup = _soup(html)
            intro = soup.select_one('.intro-category')
            h = intro.select_one('h1') if intro else None
            expected = ['Avanç de planejament', 'Programa de participació ciutadana'][index]
            if not h or h.get_text(' ', strip=True) != expected or 'POUM' not in intro.get_text():
                raise ValueError('Unexpected POUM detail content')
            block = soup.select_one('.dowload-files')
            if block is None:
                raise ValueError('POUM attachments absent')
            for doc in _documents(block, url):
                docs.setdefault(doc['url'], doc)
            descriptions.append(intro.get_text(' ', strip=True))
            sources.append(url)
        if len(sources) != 2:
            raise ValueError('Incomplete POUM source set')
        row = SantHilariSacalmAyuntamientoAdapter._row(
            'poum-avanc', 'POUM de Sant Hilari Sacalm — Avanç de planejament', 'POUM', sources[0])
        row.update(fase='avance de planeamiento', descripcion='\n'.join(descriptions),
                   documentos=list(docs.values()), source_urls=sources)
        return row

    def _fetch(self, url):
        response = requests.get(_official(url), timeout=40, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-sant-hilari-sacalm/1.0')})
        response.raise_for_status()
        _official(response.url)
        if len(response.content) > 5_000_000:
            raise ValueError('Oversized HTML response')
        response.encoding = 'utf-8'
        capture = self.config.get('capture_dir')
        if capture:
            path = Path(capture)
            path.mkdir(parents=True, exist_ok=True)
            (path / (urlparse(url).path.strip('/').split('/')[-1] + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pgm, pages = self.parse_inventory(self._fetch(SOURCE))
        poum = self.parse_poum([(url, self._fetch(url)) for url in pages])
        self._write(out_jsonl, [pgm, poum])
        return {'status': 'ok', 'rows': 2, 'source_urls': [SOURCE] + pages, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete replacement snapshot; no date cursor or hidden historical cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': LIMITATIONS[2]}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
