"""Palos de la Frontera: municipal planning instruments in the official DAEPU register."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://www.juntadeandalucia.es/medioambiente/daepu/'
FILTERS = {'find': 'findResolucionesFiltered', 'filter3': 'HUELVA',
           'filter5': 'PALOS DE LA FRONTERA', 'size': 10}
LIMITATIONS = [
    'Only DAEPU entries with primary municipality Palos de la Frontera and province Huelva; not a complete municipal planning inventory.',
    'Environmental proceedings include archived and inadmissible applications; no planning approval, current validity or granted licence is inferred.',
    'Resolution dates belong to environmental documents; BOJA publication dates are stored on their own documents. No municipal agreement dates or coordinates are inferred.',
    'Updates refresh the full filtered inventory; state_path is not a historical change log.',
]


def clean(text):
    return ' '.join(text.split())


def official_url(url):
    url = re.sub(r';jsessionid=[^/?#]+', '', url, flags=re.I)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'www.juntadeandalucia.es' or not parsed.path.startswith('/medioambiente/daepu/'):
        raise ValueError('Unexpected source URL: ' + url)
    return url


def iso_date(text):
    return datetime.strptime(text.strip(), '%d/%m/%Y').date().isoformat()


def parse_inventory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    footer = soup.select_one('tr.footer')
    match = re.search(r'Página\s+(\d+)\s+de\s+(\d+)', footer.get_text(' ', strip=True) if footer else '')
    if not match:
        raise ValueError('Missing pagination metadata')
    page, pages = map(int, match.groups())
    entries = []
    for tr in soup.select('table tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 10:
            continue
        values = [clean(c.get_text(' ', strip=True)) for c in cells]
        # Do not accept a broken/ignored server filter as municipal coverage.
        if values[2].upper() != 'HUELVA' or values[4].upper() != 'PALOS DE LA FRONTERA':
            raise ValueError('Server returned a different municipality/province')
        a = cells[9].select_one('a[href]')
        if not a or not values[8] or not re.search(r'PLAN|PGOU|MODIFICACI|INNOVACI', values[1], re.I):
            raise ValueError('Unrecognized planning entry')
        detail = official_url(urljoin(url, a['href']))
        if not re.search(r'/resolucions/\d+$', detail):
            raise ValueError('Missing resolution identity')
        entries.append({'titulo': values[1], 'expediente': values[8], 'url': detail, 'inventory_url': url,
                        'tipo_resolucion': values[6], 'fecha_resolucion': iso_date(values[7])})
    if not entries or not 1 <= page <= pages:
        raise ValueError('Empty or invalid inventory')
    return entries, page, pages


def parse_detail(html, url, entry):
    soup = BeautifulSoup(html, 'html.parser')
    def field(label):
        el = next((n for n in soup.select('label') if n.get_text(strip=True) == label), None)
        box = el.parent.select_one('.box') if el else None
        if box is None:
            raise ValueError('Missing detail field ' + label)
        return clean(box.get_text(' ', strip=True))
    if field('Municipio:').upper() != 'PALOS DE LA FRONTERA' or field('Provincia:').upper() != 'HUELVA':
        raise ValueError('Detail municipality/province mismatch')
    if field('Número de Expediente:') != entry['expediente'] or field('Actuación:') != entry['titulo']:
        raise ValueError('Inventory/detail identity mismatch')
    docs = {}
    for tr in soup.select('table tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 3:
            continue
        kind = clean(cells[0].get_text(' ', strip=True))
        date = iso_date(cells[1].get_text(strip=True))
        for a in cells[2].select('a[href]'):
            target = official_url(urljoin(url, a['href']))
            doc = {'titulo': kind, 'url': target, 'source_url': url, 'expediente': entry['expediente']}
            doc['fecha_publicacion' if kind == 'Publicación en BOJA (PB)' else 'fecha_resolucion'] = date
            docs[target] = doc
    if not docs:
        raise ValueError('Resolution has no source documents')
    return list(docs.values())


def group_instruments(entries):
    groups = {}
    for entry in entries:
        # Explicit shared numbered instrument across two environmental applications.
        numbered = re.search(r'INNOVACIÓN DE PLANEAMIENTO Nº\s*(\d+) DEL PGOUA', entry['titulo'], re.I)
        key = 'innovacion-pgoua-' + numbered[1] if numbered else entry['expediente']
        if key not in groups:
            groups[key] = {'id': 'palos-de-la-frontera-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                           'municipio': 'Palos de la Frontera', 'codigo_ine': '21055', 'provincia': 'Huelva',
                           'titulo': entry['titulo'], 'tipo': 'planeamiento_urbanistico',
                           'url': entry['url'], 'expediente': entry['expediente'],
                           'source': 'junta_de_andalucia', 'origen': 'daepu',
                           'publication_ready': False, 'geometry_status': 'unavailable',
                           'expedientes': [], 'resoluciones': [], 'documentos': []}
        row = groups[key]
        row['expedientes'].append(entry['expediente'])
        row['resoluciones'].append({k: v for k, v in entry.items() if k != 'documentos'})
        known = {d['url'] for d in row['documentos']}
        row['documentos'].extend(d for d in entry['documentos'] if d['url'] not in known)
    return list(groups.values())


class PalosDeLaFronteraAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        sources = []
        def fetch(url, capture):
            official_url(url)
            response = session.get(url, timeout=40)
            response.raise_for_status()
            official_url(response.url)
            response.encoding = 'utf-8'
            sources.append(url)
            if self.config.get('evidence_dir'):
                path = Path(self.config['evidence_dir']) / capture
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(response.text, encoding='utf-8')
            return response.text
        entries, seen = [], set()
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-palos-planning-inventory/1.0'
            page, total = 1, None
            while True:
                url = ROOT + 'resolucions/find?' + urlencode({**FILTERS, 'page': page})
                batch, current, pages = parse_inventory(fetch(url, f'inventory-{page}.html'), url)
                if current != page or (total is not None and pages != total):
                    raise ValueError('Pagination changed or server repeated page')
                total = pages
                for entry in batch:
                    if entry['url'] in seen:
                        raise ValueError('Repeated resolution across pages')
                    seen.add(entry['url'])
                    entries.append(entry)
                if page == total:
                    break
                page += 1
            for entry in entries:
                number = entry['url'].rsplit('/', 1)[1]
                entry['documentos'] = parse_detail(fetch(entry['url'], f'detail-{number}.html'), entry['url'], entry)
        rows = group_instruments(entries)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'environmental_cases': len(entries),
                'pages': total, 'source_urls': sources, 'limitations': LIMITATIONS,
                'coverage': 'current_filtered_daepu_inventory', 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
