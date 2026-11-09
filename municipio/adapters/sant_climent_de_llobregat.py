"""Municipal in-progress planning inventory; one record per local MPGM package."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.santclimentdellobregat.cat/ajuntament/informacio-oficial/urbanisme/planejament-en-tramit'
HOST = 'www.santclimentdellobregat.cat'


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#readspeakerPage')
    heading = main.select_one('h1') if main else None
    if not heading or heading.get_text(' ', strip=True) != 'Planejament en tràmit':
        raise ValueError('Missing municipal planning inventory heading')
    # The reviewed source is a single complete page. Refuse a changed paginated
    # inventory, rather than quietly returning its first page.
    for a in soup.select('a[href]'):
        text = a.get_text(' ', strip=True).casefold()
        rel = a.get('rel', [])
        if ('next' in rel or text in {'següent', 'següents', 'siguiente', 'next', '»', '›'}
                or a.find_parent(class_=re.compile(r'pag(?:in|er)', re.I))):
            if a['href'] not in {'', '#'}:
                raise ValueError('Pagination detected; inventory traversal needs review')
    inventory = main.select_one('.dinamic')
    if inventory is None:
        raise ValueError('Missing planning document blocks')
    rows = {}
    for block in inventory.select('.ddbbtext'):
        links = []
        for a in block.select('a[href]'):
            url = urljoin(SOURCE, a['href'])
            if urlparse(url).scheme not in {'http', 'https'}:
                continue
            if not any(d['url'] == url for d in links):
                links.append({'titulo': a.get_text(' ', strip=True), 'url': url})
        # Require a technical MPGM document, not merely a notice, suspension,
        # consultation homepage, licence form or an attachment title in a menu.
        technical = [d for d in links if d['titulo'].startswith('MPGM ')
                     and urlparse(d['url']).hostname == HOST
                     and urlparse(d['url']).path.startswith('/media/repository/ajuntament/Urbanisme/')
                     and urlparse(d['url']).path.lower().endswith('.pdf')]
        if not technical:
            continue
        title_node = block.find_previous_sibling('div', class_='subtitle')
        title = title_node.get_text(' ', strip=True) if title_node else ''
        if not title.startswith('MPGM '):
            raise ValueError('Technical document without an unambiguous MPGM heading')
        narrative = block.get_text(' ', strip=True)
        if not re.search(r'aprovació inicial', narrative, re.I):
            raise ValueError('MPGM package lacks its reported initial-approval stage')
        publication = None
        publication_url = None
        for doc in links:
            match = re.search(r'Publicació DOGC.*?\b(\d{2}/\d{2}/\d{4})\b', doc['titulo'])
            if match:
                publication = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
                publication_url = doc['url']
        primary = technical[0]['url']
        key = 'sant-climent-proy-' + hashlib.sha256(primary.encode()).hexdigest()[:16]
        if key in rows:
            raise ValueError('Duplicate instrument package; grouping needs review')
        rows[key] = {
            'id': key, 'municipio': 'Sant Climent de Llobregat',
            'codigo_ine': '08204', 'provincia': 'Barcelona', 'titulo': title,
            'tipo': 'modificacion_planeamiento_general',
            'fase': 'aprobación inicial',
            'fase_alcance': 'Estado descrito por el inventario; no verifica vigencia jurídica actual',
            'fecha': None, 'fecha_publicacion': publication,
            'fecha_publicacion_fuente': publication_url,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE + '#' + title_node['id'] if title_node.get('id') else SOURCE,
            'inventory_url': SOURCE, 'url_documento': primary,
            'documentos': links, 'descripcion': narrative,
            'source': 'ayuntamiento', 'origen': 'planejament_en_tramit',
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'No verified instrument geometry extracted',
            'publication_ready': False,
        }
    if not rows:
        raise ValueError('No supported local technical MPGM packages found')
    return list(rows.values())


class SantClimentDeLlobregatAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=35, headers={
            'User-Agent': 'municipio-sant-climent-inventory/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Unexpected inventory redirect')
        response.encoding = 'utf-8'
        rows = parse_inventory(response.text)
        if self.config.get('evidence_dir'):
            capture_dir = Path(self.config['evidence_dir'])
            capture_dir.mkdir(parents=True, exist_ok=True)
            (capture_dir / 'live-inventory.html').write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(output)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'partial: local technical MPGM packages on the in-progress inventory',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full snapshot: do not use the website update timestamp as a cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
