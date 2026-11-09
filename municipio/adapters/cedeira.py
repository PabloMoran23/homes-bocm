"""Cedeira's municipal planning-document inventory (partial municipal coverage)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.cedeira.gal'
SOURCE = BASE + '/documentos-municipais-de-interese/plan-de-urbanismo/'
LIMITATIONS = [
    'Only the municipal planning-document index and all its linked instrument pages; not a complete municipal project register.',
    'PXOM interpretation documents for different years are grouped as one instrument; the full original PXOM is not reproduced.',
    'No granted licences, procurement notices or general news are extracted.',
    'Dates are unknown: heading years, upload paths and PDF filenames are not agreement or publication dates.',
    'Phase describes the documentation exposed by the source, not a verified latest legal status.',
    'PDF links and their original labels are retained; PDF contents and geometry are not parsed.',
]


def _page(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#main')
    content = main.select_one('.page__content') if main else None
    heading = main.select_one('h1') if main else None
    if content is None or heading is None:
        raise ValueError('Missing municipal planning page structure')
    # This is a single-page document inventory. Refuse a changed pagination
    # contract rather than silently returning only its first page.
    if soup.select('[rel~=next], .pagination, .page-numbers, .nav-links'):
        raise ValueError('Pagination detected; crawler must be extended')
    for link in soup.select('a[href]'):
        if re.search(r'/page/\d+|[?&](?:paged|page)=\d+', link['href']) or link.get_text(' ', strip=True).casefold() in {'seguinte', 'siguiente', 'next', '»'}:
            raise ValueError('Pagination detected; crawler must be extended')
    return heading.get_text(' ', strip=True), content


def _municipal_url(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname in {'www.cedeira.gal', 'cedeira.gal'}


class CedeiraAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        title, content = _page(html)
        if title != 'PLAN DE URBANISMO':
            raise ValueError('Unexpected planning inventory title')
        entries = {}
        for a in content.select('h3 a[href]'):
            label = a.get_text(' ', strip=True)
            url = urljoin(SOURCE, a['href']).split('#')[0]
            if not _municipal_url(url) or not urlparse(url).path.startswith('/documentos-municipais-de-interese/'):
                raise ValueError('Unexpected instrument host/path')
            if re.fullmatch(r'INTERPRETACIÓN DO PXOM \d{4}', label):
                group = 'pxom-interpretacions'
            elif label.startswith('MODIFICACIÓN PUNTUAL Nº2 DO PLAN XERAL DE ORDENACIÓN URBANA'):
                group = 'pxou-modificacion-2'
            else:
                raise ValueError('Unreviewed planning instrument: ' + label)
            entries[url] = {'url': url, 'titulo': label, 'group': group}
        if not entries:
            raise ValueError('No planning instrument pages found')
        return list(entries.values())

    @staticmethod
    def parse_detail(html, entry):
        title, content = _page(html)
        if title != entry['titulo']:
            raise ValueError('Instrument heading differs from inventory')
        documents = {}
        for a in content.select('a[href]'):
            url = urljoin(entry['url'], a['href']).split('#')[0]
            if not urlparse(url).path.lower().endswith('.pdf'):
                continue
            if not _municipal_url(url):
                raise ValueError('Unexpected document host')
            label = a.get_text(' ', strip=True)
            doc = documents.setdefault(url, {'url': url, 'titulos': [], 'source_url': entry['url'], 'seccion': title})
            if label and label not in doc['titulos']:
                doc['titulos'].append(label)
        if not documents:
            raise ValueError('Instrument page contains no PDF documents')
        return {'titulo': title, 'url': entry['url'],
                'descripcion': '\n'.join(p.get_text(' ', strip=True) for p in content.select('p') if not p.select('a') and p.get_text(strip=True)),
                'documentos': list(documents.values())}

    @staticmethod
    def assemble(entries, details):
        groups = {}
        for entry, detail in zip(entries, details, strict=True):
            group = entry['group']
            if group not in groups:
                interpretation = group == 'pxom-interpretacions'
                groups[group] = {
                    'id': 'cedeira-proy-' + group, 'municipio': 'Cedeira',
                    'codigo_ine': '15022', 'provincia': 'A Coruña',
                    'titulo': 'PXOM — documentación de interpretación' if interpretation else detail['titulo'],
                    'tipo': 'planeamiento_urbanistico',
                    'fase': None, 'fecha': None, 'fecha_publicacion': None,
                    'fecha_acuerdo': None, 'fecha_aprob': None,
                    'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
                    'url': SOURCE if interpretation else entry['url'],
                    'source_url': SOURCE, 'secciones': [], 'documentos': [],
                    'lat': None, 'lon': None, 'geometry': None,
                    'publication_ready': False, 'cobertura': 'parcial',
                    'limitations': LIMITATIONS,
                }
            row = groups[group]
            row['secciones'].append({k: v for k, v in detail.items() if k != 'documentos'})
            existing = {d['url'] for d in row['documentos']}
            row['documentos'].extend(d for d in detail['documentos'] if d['url'] not in existing)
            if group == 'pxou-modificacion-2' and any('APROBACIÓN INICIAL' in t for d in detail['documentos'] for t in d['titulos']):
                row['fase'] = 'aprobación inicial'
        return list(groups.values())

    def _fetch(self, url):
        response = requests.get(url, timeout=45, headers={'User-Agent': 'municipio-cedeira/1.0'})
        response.raise_for_status()
        if not _municipal_url(response.url) or 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Unexpected municipal response')
        if len(response.content) > 5_000_000:
            raise ValueError('Oversized planning page')
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (directory / name).write_bytes(response.content)
            (directory / (name + '.url')).write_text(url + '\n', encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        entries = self.parse_inventory(self._fetch(SOURCE))
        details = [self.parse_detail(self._fetch(entry['url']), entry) for entry in entries]
        rows = self.assemble(entries, details)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + [e['url'] for e in entries],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full current inventory snapshot. Do not invent date-based watermarks.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
