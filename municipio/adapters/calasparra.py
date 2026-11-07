"""Calasparra's public WordPress planning inventory (document coverage only)."""
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

SOURCE = 'https://calasparra.org/urbanisme/'
API = 'https://calasparra.org/wp-json/wp/v2/pages?slug=urbanisme&per_page=100&page=1'
LIMITATIONS = [
    'Current document inventory only; not a complete historical planning register.',
    'Publication of documents does not establish approval, validity, execution or a granted licence.',
    'No agreement dates, instrument publication dates or coordinates verified; CMS dates are not instrument dates.',
    'The two Riñales parcel maps for phases I–II are excluded: their assignment to a single instrument is ambiguous.',
    'Valentín boundary sheets are grouped by nucleus; the source does not identify separate expediente numbers.',
    'PDF links retained; only two document prefixes sampled in live validation, not every complete PDF.',
]


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.upper())
                   if not unicodedata.combining(c))


def parse_inventory(page):
    """Parse one published API page, keeping document titles and source groupings."""
    if (page.get('slug') != 'urbanisme' or page.get('status') != 'publish'
            or page.get('link') != SOURCE):
        raise ValueError('Unexpected planning page identity')
    html = page.get('content', {}).get('rendered', '')
    soup = BeautifulSoup(html, 'html.parser')
    if ('<!--nextpage-->' in html or soup.select('.page-links, .pagination, a[rel~=next]')):
        raise ValueError('Paginated content requires review; refusing partial extraction')
    if not soup.find('h3', string=re.compile('RÈGLES SUBSIDIAIRES|NORMAS SUBSIDIARIAS', re.I)):
        raise ValueError('Missing planning inventory heading')
    sections = soup.select('.accordion-content')
    if len(sections) != 3:
        raise ValueError('Planning section structure changed')
    groups = {}
    omitted = []
    for index, section in enumerate(sections):
        for a in section.select('a[href]'):
            title = a.get_text(' ', strip=True)
            n = normalize(title)
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            if (parsed.scheme != 'https' or parsed.hostname != 'calasparra.org'
                    or not parsed.path.startswith('/wp-content/uploads/')
                    or not parsed.path.lower().endswith('.pdf')):
                raise ValueError(f'Unexpected document URL: {url}')
            if index < 2:
                key, label = 'normas-subsidiarias', 'Normas subsidiarias de Calasparra'
            elif n.startswith('DELIMITACION NUCLEO '):
                nucleus = title[len('DELIMITACIÓN NÚCLEO '):]
                if normalize(nucleus).startswith('VALENTIN'):
                    nucleus = re.split(r'\s+[–—-]\s+', nucleus)[0]
                key, label = 'delimitacion-' + normalize(nucleus), 'Delimitación núcleo ' + nucleus
            elif n.startswith('LOS RINALES-PARCELARIO FASES I'):
                omitted.append({'titulo': title, 'url': url, 'reason': 'Ambiguous phase I–II parcel maps'})
                continue
            elif 'RINALES' in n and 'FASE III' in n:
                key, label = 'rinales-iii', 'Plan parcial Riñales — fase III'
            elif n.startswith('PLAN PARCIAL RINALES') and 'FASE II' in n:
                key, label = 'rinales-ii', 'Plan parcial Riñales — fase II'
            elif 'CANADA MANRIQUE' in n and 'FASE II' in n:
                key, label = 'canada-manrique-ii', 'Plan parcial Cañada Manrique — fase II'
            else:
                raise ValueError(f'Unclassified planning document: {title}')
            group = groups.setdefault(key, {'titulo': label, 'documentos': []})
            document = {'titulo': title, 'url': url}
            if document not in group['documentos']:
                group['documentos'].append(document)
    if not groups or 'normas-subsidiarias' not in groups:
        raise ValueError('Empty planning inventory')
    rows = []
    for key, group in groups.items():
        if key in {'rinales-iii', 'rinales-ii', 'canada-manrique-ii'} and not any(
            normalize(d['titulo']).startswith(('PLAN PARCIAL', 'P P ')) for d in group['documentos']
        ):
            raise ValueError('Plan has auxiliary documents only')
        rows.append({
            'id': 'calasparra-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Calasparra', 'codigo_ine': '30013', 'provincia': 'Murcia',
            **group, 'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
            'origen': 'inventario_documental_planeamiento', 'url': group['documentos'][0]['url'],
            'inventory_url': SOURCE, 'source_api_url': API,
            'publication_ready': False, 'geometry_status': 'unavailable',
        })
    return rows, omitted


class CalasparraAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        response = requests.get(API, timeout=40, headers={'User-Agent': 'municipal-planning-inventory/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != 'calasparra.org':
            raise ValueError('Unexpected API redirect')
        payload = response.json()
        # A slug identifies one page. Extra pages/items indicate a changed source,
        # and must fail explicitly instead of silently truncating the inventory.
        if (response.headers.get('X-WP-TotalPages') != '1'
                or response.headers.get('X-WP-Total') != '1'
                or not isinstance(payload, list) or len(payload) != 1):
            raise ValueError('Unexpected API pagination or page count')
        rows, omitted = parse_inventory(payload[0])
        capture_dir = self.config.get('evidence_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'live-inventory.json').write_text(response.text, encoding='utf-8')
            (capture / 'live-headers.json').write_text(json.dumps(dict(response.headers), indent=2), encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE, API],
                'coverage': 'current_document_inventory', 'limitations': LIMITATIONS,
                'excluded_documents': omitted}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
