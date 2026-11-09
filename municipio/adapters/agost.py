"""Agost's current municipal planning inventory, grouped by instrument.

Only catalogue metadata is extracted: PDF filenames and upload paths are not
agreement/publication dates, and linked plans are not granted licences.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE_URL = 'https://www.agost.es/el-ayuntamiento/obras-y-urbanismo/'
MODIFICATION = re.compile(r'^Modificación puntual n[ºª°o.]?\s*(\d+)\b', re.I)


def own_text(node):
    """List-item label without nested document labels."""
    return ' '.join(str(t).strip() for t in node.find_all(string=True)
                    if t.find_parent('li') is node and str(t).strip())


def documents(node, source_url):
    links = {}
    for anchor in node.select('a[href]'):
        url = urljoin(source_url, anchor['href'])
        parsed = urlparse(url)
        if (parsed.scheme not in {'http', 'https'}
                or parsed.hostname not in {'www.agost.es', 'agost.es'}
                or not parsed.path.lower().endswith('.pdf')):
            raise ValueError(f'Unexpected planning document URL: {url}')
        # One source anchor is accidentally split into three text fragments.
        title = anchor.get_text(' ', strip=True)
        if url in links:
            if title != links[url]['titulo']:
                links[url]['titulo'] += ' ' + title
        else:
            links[url] = {'titulo': title, 'url': url, 'source_url': source_url}
    return list(links.values())


def parse_inventory(html, source_url=SOURCE_URL):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.entry-content')
    if content is None or not any(h.get_text(' ', strip=True) == 'PLANEAMIENTO MUNICIPAL'
                                  for h in content.select('h2')):
        raise ValueError('Municipal planning inventory missing')
    if (soup.select('a[rel~=next], .pagination, .page-links, .nav-links')
            or any(a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'más resultados'}
                   for a in content.select('a[href]'))):
        raise ValueError('Pagination detected; review traversal before extracting')

    records = {}

    def add(identity, title, node, section, phase=None):
        docs = documents(node, source_url)
        if not docs:
            raise ValueError(f'Instrument without linked documents: {title}')
        key = 'agost-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16]
        if key in records:
            row = records[key]
            seen = {d['url'] for d in row['documentos']}
            row['documentos'].extend(d for d in docs if d['url'] not in seen)
            return
        row = {'id': key, 'titulo': title, 'municipio': 'Agost',
               'codigo_ine': '03002', 'provincia': 'Alicante',
               'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
               'origen': 'inventario_planeamiento_municipal',
               'url': docs[0]['url'], 'inventory_url': source_url,
               'source_section': section, 'documentos': docs,
               'publication_ready': False, 'geometry_status': 'unavailable'}
        if phase:
            row['fase'] = phase
        missing = [own_text(li) for li in node.select('li')
                   if not li.select('a[href], ul, ol') and own_text(li)]
        if missing:
            row['documentos_sin_enlace'] = missing
        records[key] = row

    sections = content.select('.gb-accordion__item')
    if not sections:
        raise ValueError('Planning accordion missing')
    for section in sections:
        label_node = section.select_one('.gb-accordion__toggle .gb-button-text')
        body = section.select_one('.gb-accordion__content')
        if label_node is None or body is None:
            raise ValueError('Incomplete planning section')
        label = label_node.get_text(' ', strip=True)
        if label.startswith('Revisión Normas Subsidiarias de Agost'):
            add('revision-nnss', label, body, label)
        elif label == 'Modificaciones puntuales':
            items = body.select('li')
            if not items:
                raise ValueError('Empty modifications section')
            for item in items:
                match = MODIFICATION.match(own_text(item))
                if not match:
                    raise ValueError('Unrecognized modification label')
                number = str(int(match[1]))
                add('modificacion-' + number, 'Modificación puntual nº' + number,
                    item, label)
        elif label in {'Planeamiento diferido', 'Planeamiento en tramitación'}:
            # Only outer list items represent instruments; nested items are files.
            items = [li for li in body.select('li') if li.find_parent('li') is None]
            if not items:
                raise ValueError('Empty planning section')
            for item in items:
                title = own_text(item)
                match = MODIFICATION.match(title)
                if match:
                    identity = 'modificacion-' + str(int(match[1]))
                elif label == 'Planeamiento diferido' and title.startswith('SAU/'):
                    title = 'Plan parcial ' + title
                    identity = title.casefold()
                elif title == 'Catálogo de Protecciones':
                    identity = 'catalogo-protecciones'
                else:
                    raise ValueError(f'Unrecognized planning instrument: {title}')
                add(identity, title, item, label,
                    'en tramitación' if label == 'Planeamiento en tramitación' else None)
        elif label != 'Ordenanzas':
            raise ValueError(f'Unreviewed inventory section: {label}')
    if not records:
        raise ValueError('No usable planning instruments')
    return list(records.values())


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows),
                         encoding='utf-8')
    temporary.replace(path)


class AgostAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        response = requests.get(SOURCE_URL, timeout=45,
                                headers={'User-Agent': 'municipio-agost-inventory/1.0'})
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE_URL.rstrip('/'):
            raise ValueError('Unexpected inventory redirect')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_text(response.text, encoding='utf-8')
        rows = parse_inventory(response.text, response.url)
        write_jsonl(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows),
                'coverage': 'current_municipal_planning_inventory',
                'source_urls': [response.url], 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full current snapshot; no claim of historical change tracking.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        write_jsonl(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified grants register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
