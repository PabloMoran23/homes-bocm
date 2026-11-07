"""Numbered planning/project instruments in Azpeitia's official inventory.

Coverage intentionally excludes unnumbered legacy entries and urban agreements.
Dates inside linked PDFs are not parsed; inventory placement is not approval.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.azpeitia.eus/udala/hirigintza-plangintza'
REFERENCE = re.compile(r'\b\d{4}PLAN\d{4}\b', re.I)
SECTIONS = {'Garapen planteamendua', 'Plangintza kudeaketa'}
LIMITATIONS = [
    'Partial inventory: only explicitly numbered planning, urbanization and reparcelation instruments.',
    'Unnumbered legacy entries, the general plan and its first amendment, and urban agreements excluded.',
    'PDF contents and their dates are not parsed; publication and agreement dates remain unknown.',
    'No granted licences or verified project geometry; no coordinates inferred.',
    'Full snapshot refresh, not an event history or deletion feed.',
]


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('main#content')
    if content is None:
        raise ValueError('Missing municipal inventory content')
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).lower()
        if ('next' in a.get('rel', []) or label in {'next', 'siguiente', 'hurrengoa', 'hurrengo'}
                or re.search(r'[?&](?:b_start(?::int)?|start|page)=', a['href'])
                or a.find_parent(class_=re.compile(r'pagination|listingBar', re.I))):
            raise ValueError('Pagination detected: traversal must be implemented before extraction')
    records = {}
    seen_sections = set()
    for section in content.select('.accordion-item'):
        button = section.select_one('.accordion-header button')
        name = button.get_text(' ', strip=True) if button else ''
        if name not in SECTIONS:
            continue
        seen_sections.add(name)
        for item in section.select('.accordion-body > ul > li, .accordion-body > ol > li'):
            heading = BeautifulSoup(str(item), 'html.parser').li
            for nested in heading.select('ul, ol'):
                nested.decompose()
            title = heading.get_text(' ', strip=True)
            refs = set(r.upper() for r in REFERENCE.findall(title))
            low = title.lower()
            kind = None
            if 'xehetasun azterlan' in low or 'xehetasun-azter' in low:
                kind = 'estudio de detalle'
            elif 'birpartzelazio proiektu' in low or 'bipartzelazio proiektu' in low:
                kind = 'proyecto de reparcelación'
            elif 'urbanizazio proiektu' in low:
                kind = 'proyecto de urbanización'
            elif 'plan berezi' in low:
                kind = 'plan especial'
            if not refs or kind is None:
                continue
            if len(refs) != 1:
                raise ValueError('Ambiguous instrument references')
            ref = next(iter(refs))
            documents = {}
            for a in item.select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                parsed = urlparse(url)
                if (parsed.scheme == 'https' and parsed.hostname == 'www.azpeitia.eus'
                        and parsed.path.startswith('/udala/hirigintza-plangintza/')
                        and '.pdf' in parsed.path.lower()):
                    url = parsed._replace(fragment='').geturl()
                    documents.setdefault(url, {'url': url, 'titulo': a.get_text(' ', strip=True),
                                               'source_url': SOURCE})
            if not documents:
                raise ValueError(f'No source documents for {ref}')
            if ref not in records:
                records[ref] = {
                    'id': 'azpeitia-proy-' + ref.lower(), 'expediente': ref,
                    'municipio': 'Azpeitia', 'codigo_ine': '20018', 'provincia': 'Gipuzkoa',
                    'titulo': title, 'tipo': kind,
                    'fase': 'aprobación definitiva' if 'behin betiko onespena' in low or 'behin betiko onarpena' in low else None,
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
                    'source_sections': [], 'documentos': [], 'titulos_fuente': [],
                    'geometry': None, 'lat': None, 'lon': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                }
            row = records[ref]
            if row['tipo'] != kind:
                raise ValueError(f'Conflicting instrument types for {ref}')
            if title not in row['titulos_fuente']:
                row['titulos_fuente'].append(title)
            if name not in row['source_sections']:
                row['source_sections'].append(name)
            existing = {d['url'] for d in row['documentos']}
            row['documentos'].extend(d for url, d in documents.items() if url not in existing)
    if seen_sections != SECTIONS or not records:
        raise ValueError('Missing inventory sections or supported numbered instruments')
    return sorted(records.values(), key=lambda row: row['expediente'])


class AzpeitiaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={'User-Agent': 'municipio-azpeitia/1.0'})
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE or 'html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Unexpected municipal inventory response')
        rows = parse_inventory(response.text)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory.html').write_text(response.text, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
