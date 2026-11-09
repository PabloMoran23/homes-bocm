"""Quintanar del Rey: numbered POM instruments in the official regional inventory."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'urbanismo.castillalamancha.es'
SOURCE = f'https://{HOST}/acuerdos-expedientes?title=Quintanar+del+Rey'
LIMITATIONS = [
    'Partial coverage: title-filtered regional agreement inventory, numbered POM modifications only; not a complete municipal project or current planning register.',
    'Regional urban-planning agreements are not granted municipal licences. Qualification cases, application forms and procurement notices are excluded.',
    'Catalogue dates are agreement dates, not web publication dates. No inferred approval dates, current validity, construction status or coordinates.',
    'PDF links retained as provenance; some PDFs are image scans. Their full text is not parsed by this adapter.',
]


def official_url(url):
    p = urlparse(url)
    if p.scheme != 'https' or p.netloc != HOST:
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def parse_page(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None:
        raise ValueError('Missing inventory main content')
    count = re.search(r'Mostrando\s+(\d+)\s*-\s*(\d+)\s+de\s+(\d+)\s+expediente/s', main.get_text(' ', strip=True))
    if not count:
        raise ValueError('Missing inventory result count (empty or changed source)')
    start, end, total = map(int, count.groups())
    entries = []
    for card in main.select('article.node--type-acuerdo-expediente-urbanistico'):
        title = card.select_one('h3.article__title')
        population = card.select_one('.field--name-field-poblacion')
        date = card.select_one('.field--name-field-expediente-fecha')
        links = card.select('.field--name-field-expediente-fichero a[href]')
        if not title or not population or not date or not links or not card.get('about'):
            raise ValueError('Incomplete agreement card')
        documents = list(dict.fromkeys(official_url(urljoin(url, a['href'])) for a in links))
        if any(not urlparse(d).path.lower().endswith('.pdf') for d in documents):
            raise ValueError('Unexpected agreement document format')
        entries.append({
            'titulo': title.get_text(' ', strip=True),
            'municipio': population.get_text(' ', strip=True),
            'fecha_acuerdo': datetime.strptime(date.get_text(strip=True), '%d/%m/%Y').date().isoformat(),
            'url': official_url(urljoin(url, card['about'])),
            'documentos': documents,
        })
    if len(entries) != end - start + 1 or not 1 <= start <= end <= total:
        raise ValueError('Inventory card count does not match reported range')
    next_links = main.select('a[rel~=next]')
    if len(next_links) > 1:
        raise ValueError('Ambiguous pagination')
    next_url = None
    if next_links:
        p = urlparse(official_url(urljoin(url, next_links[0]['href'])))
        query = parse_qs(p.query)
        # Some Drupal pagination links omit the exposed title filter.
        query['title'] = ['Quintanar del Rey']
        next_url = urlunparse(p._replace(query=urlencode(query, doseq=True)))
        if p.path != '/acuerdos-expedientes':
            raise ValueError('Unexpected pagination path')
    if (end < total) != bool(next_url):
        raise ValueError('Incomplete or contradictory pagination')
    return entries, start, end, total, next_url


def group_instruments(entries):
    groups = {}
    for entry in entries:
        if entry['municipio'] not in ('Quintanar del Rey', 'Quintanar del Rey (Cuenca)'):
            continue
        title = entry['titulo']
        if not re.search(r'\bPOM\b', title, re.I) or not re.search(r'\bQuintanar del Rey\b', title, re.I):
            continue
        match = re.search(r'Modificaci[oó]n\s+Puntual\s+n[º°o.]\s*(\d+)\b', title, re.I)
        if not match:
            continue
        number = int(match[1])
        row = groups.setdefault(number, {
            'id': f'quintanar-del-rey-pom-mp-{number}',
            'titulo': f'Modificación Puntual nº {number} del POM de Quintanar del Rey',
            'municipio': 'Quintanar del Rey', 'codigo_ine': '16175', 'provincia': 'Cuenca',
            'tipo': 'modificación puntual del Plan de Ordenación Municipal',
            'source': 'ayuntamiento', 'organismo_fuente': 'Junta de Comunidades de Castilla-La Mancha',
            'origen': 'inventario_autonomico_acuerdos_urbanismo', 'inventory_url': SOURCE,
            'url': entry['url'], 'documentos': [], 'acuerdos': [],
            'fecha_publicacion': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'coverage': 'partial_numbered_pom_agreements',
        })
        if entry not in row['acuerdos']:
            row['acuerdos'].append(entry)
        for link in entry['documentos']:
            if link not in row['documentos']:
                row['documentos'].append(link)
    if not groups:
        raise ValueError('No numbered Quintanar del Rey POM instruments found')
    rows = []
    for number in sorted(groups):
        row = groups[number]
        row['acuerdos'].sort(key=lambda e: (e['fecha_acuerdo'], e['url']))
        row['fecha_acuerdo'] = row['acuerdos'][0]['fecha_acuerdo'] if len(row['acuerdos']) == 1 else None
        rows.append(row)
    return rows


class QuintanarDelReyAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        url, seen, entries, expected_total, captures = SOURCE, set(), [], None, []
        while url:
            if url in seen:
                raise ValueError('Pagination cycle')
            seen.add(url)
            response = requests.get(url, timeout=45, headers={'User-Agent': 'municipio-quintanar-del-rey/1.0'})
            response.raise_for_status()
            official_url(response.url)
            page, start, end, total, next_url = parse_page(response.text, response.url)
            if start != len(entries) + 1 or (expected_total is not None and total != expected_total):
                raise ValueError('Inventory pagination changed during extraction')
            expected_total = total
            captures.append((response.url, response.text))
            entries.extend(page)
            url = next_url
        if len({e['url'] for e in entries}) != expected_total:
            raise ValueError('Duplicate or missing agreement cards')
        rows = group_instruments(entries)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        if self.config.get('capture_dir'):
            capture_dir = Path(self.config['capture_dir'])
            capture_dir.mkdir(parents=True, exist_ok=True)
            for index, (_, html) in enumerate(captures):
                (capture_dir / f'inventory-live-{index}.html').write_text(html, encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'inventory_entries': len(entries),
                'selected_agreements': sum(len(r['acuerdos']) for r in rows),
                'source_urls': [u for u, _ in captures], 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Complete source snapshot; do not use agreement dates as publication watermarks.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
