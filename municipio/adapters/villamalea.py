"""Villamalea's two public planning inventories; one row per instrument."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE_URL = 'https://villamalea.es/'
SOURCE_URLS = tuple(BASE_URL + path + '/' for path in (
    'plan-de-ordenacion-municipal', 'modificaciones-puntuales-del-pom'))
LIMITATIONS = [
    'Partial municipal coverage: only the two current public planning inventories; '
    'not the electronic noticeboard, procurement, news or a historical register.',
    'Published documents do not establish current legal validity or granted licences.',
    'Document labels are retained verbatim; no publication/agreement dates inferred '
    'from upload paths, filenames or the ambiguous modification heading.',
    'No geometry extracted; no coordinates or geocoding jitter.',
]


def _norm(value):
    return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()


def parse_inventory(html: str, url: str) -> list[dict]:
    """Parse scoped Elementor document links; reject unclassified new documents."""
    if url not in SOURCE_URLS:
        raise ValueError('Unexpected inventory URL')
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None or not main.select_one('h1.entry-title'):
        raise ValueError('Missing planning page structure')
    expected = ('modificaciones puntuales del pom' if url == SOURCE_URLS[1]
                else 'plan de ordenacion municipal')
    if _norm(main.select_one('h1.entry-title').get_text(' ', strip=True)) != expected:
        raise ValueError('Unexpected planning page title')
    # These inventories are single pages. Fail explicitly if pagination appears,
    # rather than delivering a silently truncated snapshot.
    if soup.select('a[rel~=next], .pagination, .page-links, .nav-links, .elementor-pagination'):
        raise ValueError('Pagination detected: traversal must be implemented before extraction')
    groups = {}
    for widget in main.select('.elementor-widget-text-editor'):
        heading = widget.find(['h2', 'h3', 'h4', 'h5', 'h6'])
        section = _norm(heading.get_text(' ', strip=True)) if heading else ''
        section_mp = re.fullmatch(r'modificacion\s*(?:n[ºo°.]*)?\s*(\d+)', section)
        for a in widget.select('a[href]'):
            target = urljoin(url, a['href'])
            if not urlparse(target).path.lower().endswith('.pdf'):
                continue
            label = a.get_text(' ', strip=True)
            text = _norm(label + ' ' + unquote(urlparse(target).path))
            if urlparse(target).hostname not in {
                'villamalea.es', 'www.dipualba.es', 'estaticos.dipualba.es',
            }:
                raise ValueError('Unexpected document host: ' + target)
            mp = re.search(r'modificacion[\s_]+puntual[\s_]*(?:n[ºo°.]*)?[\s_]*(\d+)', text)
            if mp or section_mp:
                number = (mp or section_mp).group(1)
                key, title = 'mp-' + number, 'Modificación puntual nº ' + number + ' del POM de Villamalea'
            elif 'catalogo de bienes y espacios protegidos' in text:
                key, title = 'catalogo-bienes', 'Catálogo de Bienes y Espacios Protegidos de Villamalea'
            elif 'interpretacion' in text and re.search(r'\bc1\b', text):
                key, title = 'interpretacion-c1', 'Interpretación C1 del POM de Villamalea'
            elif url == SOURCE_URLS[0] and ('pom_villamalea' in text or 'refundido_2016.pdf' in text):
                key, title = 'pom', 'Plan de Ordenación Municipal de Villamalea'
            else:
                raise ValueError('Unclassified planning document: ' + target)
            row = groups.setdefault(key, {
                'id': 'villamalea-' + key, 'municipio': 'Villamalea',
                'provincia': 'Albacete', 'codigo_ine': '02079', 'titulo': title,
                'tipo': 'instrumento de planeamiento', 'source': 'ayuntamiento',
                'origen': 'inventario_planeamiento', 'url': url, 'inventory_url': url,
                'documentos': [], 'publication_ready': False,
                'geometry_status': 'unavailable', 'coverage': 'current_document_inventory',
            })
            if not any(d['url'] == target for d in row['documentos']):
                row['documentos'].append({'titulo': label, 'url': target, 'source_url': url})
    if not groups:
        raise ValueError('No planning instruments found')
    return list(groups.values())


class VillamaleaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        groups = {}
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-inventory/1.0'
            for url in SOURCE_URLS:
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if response.url.rstrip('/') != url.rstrip('/'):
                    raise ValueError('Unexpected inventory redirect: ' + response.url)
                if self.config.get('capture_dir'):
                    capture_dir = Path(self.config['capture_dir'])
                    capture_dir.mkdir(parents=True, exist_ok=True)
                    (capture_dir / (urlparse(url).path.strip('/') + '.html')).write_bytes(response.content)
                for row in parse_inventory(response.text, url):
                    if row['id'] in groups:
                        old = groups[row['id']]
                        existing = {d['url'] for d in old['documentos']}
                        old['documentos'].extend(d for d in row['documentos'] if d['url'] not in existing)
                    else:
                        groups[row['id']] = row
        rows = sorted(groups.values(), key=lambda row: row['id'])
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': list(SOURCE_URLS),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full current snapshot; do not claim deletion/history tracking.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
