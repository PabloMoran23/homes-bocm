"""Guadassuar's official planning inventory; one row per instrument, not PDF."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.guadassuar.es/urbanisme/'
HOSTS = {'guadassuar.es', 'www.guadassuar.es'}


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.entry-content')
    if content is None:
        raise ValueError('Missing municipal inventory content')
    if content.select('.pagination, .page-links, .nav-links, a[rel~=next], [data-next-page], .load-more'):
        raise ValueError('Pagination detected; review inventory traversal before extracting')
    for a in content.select('a[href]'):
        if re.search(r'/page/\d+|[?&](?:paged|page)=\d+', a['href']):
            raise ValueError('Paginated inventory link detected')

    def documents(block):
        docs = {}
        for a in block.select('a[href]'):
            target = urljoin(url, a['href'])
            parsed = urlparse(target)
            if not parsed.path.lower().endswith('.pdf'):
                continue
            if parsed.scheme != 'https' or parsed.hostname not in HOSTS or not parsed.path.startswith('/wp-content/uploads/Urbanisme/'):
                raise ValueError('Unexpected planning document origin: ' + target)
            target = quote(target, safe=':/%?=&+#')
            label = a.select_one('.filename') or a
            docs.setdefault(target, {'titulo': label.get_text(' ', strip=True), 'url': target})
        if not docs:
            raise ValueError('Instrument or document group has no PDF links')
        return list(docs.values())

    records = {}

    def add(key, title, docs, section, anchor):
        if key not in records:
            records[key] = {
                'id': 'guadassuar-plan-' + key, 'municipio': 'Guadassuar',
                'codigo_ine': '46139', 'provincia': 'Valencia', 'titulo': title,
                'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
                'origen': 'inventario_municipal_planeamiento', 'inventory_url': url,
                'url': urljoin(url, '#' + anchor) if anchor else url,
                'situacion_inventario': section, 'documentos': [],
                'publication_ready': False, 'geometry_status': 'unavailable',
            }
        row = records[key]
        if row['situacion_inventario'] != section:
            raise ValueError('Instrument appears in conflicting inventory sections')
        seen = {d['url'] for d in row['documentos']}
        row['documentos'].extend(d for d in docs if d['url'] not in seen)

    section = None
    sections_seen = set()
    for block in content.select('h1.sek-heading, .sek-accord-item'):
        if block.name == 'h1':
            heading = block.get_text(' ', strip=True)
            section = ('tramitacio' if heading.startswith('01') and 'Planejament' in heading
                       else 'aprovat' if heading.startswith('02') and 'Planejament' in heading else None)
            if section:
                sections_seen.add(section)
            continue
        if section is None:
            continue
        title_el = block.select_one('.sek-inner-accord-title')
        body = block.select_one('.sek-accord-content')
        if title_el is None or body is None:
            raise ValueError('Changed planning accordion structure')
        title = title_el.get_text(' ', strip=True)
        anchor = body.get('id', '')
        if section == 'tramitacio':
            if not re.match(r'^(PLA |MODIFICACIÓ\b)', title):
                raise ValueError('Unknown instrument in processing: ' + title)
            number = re.search(r'MODIFICACIÓ\s+(?:NUM\s+)?(\d+)', title)
            key = ('mod-' + number[1] if number else hashlib.sha256(title.encode()).hexdigest()[:16])
            add(key, title, documents(body), 'Planejament urbanístic en tramitació', anchor)
        elif title == 'MODIFICACIONS':
            listing = body.select_one('ol')
            if listing is None or not listing.find_all('li', recursive=False):
                raise ValueError('Missing approved modification listing')
            for item in listing.find_all('li', recursive=False):
                name = ' '.join(str(t).strip() for t in item.find_all(string=True, recursive=False)).strip()
                number = re.match(r'MODIFICACIÓ\s+(\d+)\b', name)
                if not number:
                    raise ValueError('Unknown modification: ' + name)
                add('mod-' + number[1], name, documents(item), 'MODIFICACIONS APROVADES', anchor)
        elif title in {'ANUNCIS', 'ANEX', 'TOM I', 'TOM II', 'TOM III', 'TOM IV', 'CORRECCIÓ ERRORS'}:
            add('pgou', 'Pla General d’Ordenació Urbana (PGOU) de Guadassuar',
                documents(body), 'Planejament urbanístic aprovat. (PGOU)', anchor)
        else:
            raise ValueError('Unknown approved planning group: ' + title)
    if sections_seen != {'tramitacio', 'aprovat'} or not records or 'pgou' not in records:
        raise ValueError('Incomplete or empty planning inventory')
    return list(records.values())


class GuadassuarAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        # The www entry point currently redirects to the canonical host successfully;
        # direct canonical requests can receive an intermittent HTTP 403.
        response = requests.get(SOURCE, timeout=45, headers={'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in HOSTS:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [SOURCE, response.url], 'coverage': 'municipal_planning_document_inventory'}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        tmp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
