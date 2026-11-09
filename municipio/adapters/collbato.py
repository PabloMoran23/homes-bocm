"""Partial snapshot of Collbató's official works inventory and PGOU documents."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.collbato.cat'
ROOT = BASE + '/ajuntament-seu-electronica/urbanisme/'
SOURCES = (ROOT + 'projectes.htm', ROOT + 'pla-general-ordenacio-urbana.htm')


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def _content(html, heading):
    soup = BeautifulSoup(html, 'html.parser')
    block = soup.select_one('#col-cont-contingut')
    title = soup.select_one('#col-cont > h2')
    if not block or not title or title.get_text(' ', strip=True) != heading:
        raise ValueError('Collbató inventory heading/content missing or changed')
    for a in soup.select('a[href]'):
        if ('next' in a.get('rel', []) or
                _norm(a.get_text(' ', strip=True)) in {'seguent', 'seguents', 'siguiente', 'next', '»'} or
                re.search(r'pagin|pagination', ' '.join(a.get('class', [])), re.I)):
            if a['href'] not in ('', '#'):
                raise ValueError('Pagination detected; extend crawler before extracting')
    return block


def _link(a, source):
    url = urljoin(source, a['href'])
    parsed = urlparse(url)
    if parsed.hostname == 'www.collbato.cat' and '/files/' in parsed.path and parsed.path.lower().endswith('.pdf'):
        return {'titulo': a.get_text(' ', strip=True), 'url': url,
                'tipo': 'documento_pdf', 'source_url': source}
    if parsed.hostname == 'tauler.seu.cat' and parsed.path == '/pagDetall.do' and 'idens=806920002' in parsed.query:
        return {'titulo': a.get_text(' ', strip=True), 'url': url,
                'tipo': 'referencia_edicto', 'source_url': source}
    raise ValueError('Unreviewed project link: ' + url)


def _row(key, title, kind, source, labels, links):
    return {
        'id': 'collbato-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
        'municipio': 'Collbató', 'codigo_ine': '08069', 'provincia': 'Barcelona',
        'titulo': title, 'tipo': kind, 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': source, 'source': 'ayuntamiento', 'origen': 'inventario_municipal',
        'descripcion': '\n'.join(labels),
        'documentos': [link for link in links if link['tipo'] == 'documento_pdf'],
        'referencias': [link for link in links if link['tipo'] == 'referencia_edicto'],
        'provenance': {'source_url': source, 'rotulos_originales': labels,
                       'date_semantics': 'No complete dates in inventory; PDF dates not parsed',
                       'phase_semantics': 'Labels retained; current legal phase not verified'},
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'coverage': 'Partial municipal inventory snapshot; linked notices may expire; no verified geometry',
    }


class CollbatoAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_projects(html):
        content = _content(html, 'Projectes')
        groups = {}
        for li in content.select('li'):
            label = li.get_text(' ', strip=True)
            norm = _norm(label)
            # Only actual named physical works; a procurement/form is never a project.
            if not re.search(r'\bprojecte\b', norm) or re.search(r'licitacio|contractacio|sol.licitud|formulari', norm):
                raise ValueError('Unreviewed entry in municipal works inventory: ' + label)
            subject = re.sub(r'^.*?\bprojecte\b\s*(?:d[´’\']obra ordinaria\s+projecte\s+executiu\s*)?', '', norm)
            subject = re.sub(r'^de\s+', '', subject)
            # These are the original notice, correction, initial and definitive notice
            # of the same physical work, not four projects.
            key = 'tancament-pista-poliesportiva' if 'tancament' in norm and 'pista poliesportiva' in norm else subject
            title = 'Projecte de tancament de la Pista Poliesportiva' if key == 'tancament-pista-poliesportiva' else label
            group = groups.setdefault(key, {'title': title, 'labels': [], 'links': {}})
            group['labels'].append(label)
            for a in li.select('a[href]'):
                link = _link(a, SOURCES[0])
                group['links'][link['url']] = link
        if not groups:
            raise ValueError('Empty Collbató works inventory')
        return [_row('works:' + key, g['title'], 'obra_publica', SOURCES[0],
                     g['labels'], list(g['links'].values())) for key, g in groups.items()]

    @staticmethod
    def parse_pgou(html):
        content = _content(html, 'Pla General Ordenació Urbana')
        links = {}
        for a in content.select('a[href]'):
            link = _link(a, SOURCES[1])
            links[link['url']] = link
        if not links or not any('Text Refós' in d['titulo'] for d in links.values()):
            raise ValueError('PGOU consolidated text missing')
        return [_row('pgou', 'Pla General Ordenació Urbana de Collbató', 'PGOU',
                     SOURCES[1], ['Pla General Ordenació Urbana', 'Text Refós', 'Normativa', 'Plànols'],
                     list(links.values()))]

    def backfill_proyectos(self, out_jsonl: Path):
        rows = []
        for url, parser in zip(SOURCES, (self.parse_projects, self.parse_pgou)):
            response = requests.get(url, timeout=35, stream=True,
                                    headers={'User-Agent': 'municipio-collbato/1.0'})
            with response:
                response.raise_for_status()
                if response.url != url:
                    raise ValueError('Unexpected inventory redirect: ' + response.url)
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 3_000_000:
                        raise ValueError('Inventory exceeds reviewed response limit')
                    chunks.append(chunk)
                raw = b''.join(chunks)
            html = raw.decode('utf-8')
            if self.config.get('capture_dir'):
                dest = Path(self.config['capture_dir'])
                dest.mkdir(parents=True, exist_ok=True)
                (dest / url.rsplit('/', 1)[-1]).write_bytes(raw)
            rows.extend(parser(html))
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES), 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full refresh of both unpaginated inventories, no date-based cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
