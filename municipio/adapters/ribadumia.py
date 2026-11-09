"""Documented planning instruments in Ribadumia's public-information inventory."""
from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://omeuconcello.ribadumia.org/seccion/94/informacion-publica'
PREFIX = 'ctl00$ContentSection$'
LIMITATIONS = [
    'Partial municipal coverage: documented PXOM modifications and Barrantes accessibility plans only; not a complete works inventory.',
    'Inventory dates are municipal publication dates. Agreement/approval dates and current legal validity are not inferred.',
    'No granted licences extracted; applications, procurement, ordinances and unrelated notices excluded.',
    'No verified vector geometry; PDF plans retained as documents, without invented coordinates.',
]


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.upper())
                   if not unicodedata.combining(c))


def parse_page(html):
    """Return inventory entries and explicit WebForms pagination state."""
    soup = BeautifulSoup(html, 'html.parser')
    pager = soup.select_one('select[id$="_dlPagina"]')
    size = soup.select_one('select[id$="_dlResultados"] option[selected]')
    if not pager or not size:
        raise ValueError('Missing inventory pagination controls')
    options = [int(o['value']) for o in pager.select('option')]
    selected = pager.select_one('option[selected]')
    total_match = re.fullmatch(r'(\d+) Rexistros', pager.get('title', ''))
    if not selected or not total_match or options != list(range(1, len(options) + 1)):
        raise ValueError('Unrecognized inventory pagination')
    current, total, per_page = int(selected['value']), int(total_match[1]), int(size['value'])
    if len(options) != max(1, (total + per_page - 1) // per_page):
        raise ValueError('Inconsistent inventory page count')
    entries = []
    for block in soup.select('.media-body'):
        heading = block.select_one('.media-heading .h4')
        if not heading:
            continue
        date = heading.select_one('small')
        if not date:
            raise ValueError('Inventory entry lacks publication date')
        date_text = date.get_text(' ', strip=True)
        publication = datetime.strptime(date_text.split(' - ')[0], '%d/%m/%y').date().isoformat()
        date.extract()
        title = heading.get_text(' ', strip=True)
        docs = []
        for a in block.select('a[href]'):
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            if parsed.path == '/cargararchivo.aspx':
                if parsed.hostname != urlparse(SOURCE).hostname or not parsed.query.startswith('id='):
                    raise ValueError('Unexpected document source')
                docs.append({'titulo': a.get('title') or a.get_text(' ', strip=True), 'url': url})
        entries.append({'titulo': title, 'fecha_publicacion': publication,
                        'descripcion': '\n'.join(p.get_text(' ', strip=True)
                                                 for p in block.select('p.text-sm')),
                        'documentos': docs})
    expected = min(per_page, max(0, total - (current - 1) * per_page))
    if len(entries) != expected:
        raise ValueError('Inventory row count does not match pagination')
    return entries, (current, len(options), total), soup


def group_projects(entries):
    grouped = {}
    for entry in entries:
        title = normalized(entry['titulo'])
        match = re.match(r'^MODIFIC(?:ACION|ACACION) PUNTUAL (?:NUMERO|NUM\.?|N[º°]?)\s*(\d+)\b', title)
        # The portal currently spells MODIFICACACIÓN, preserved in provenance.
        if match:
            key = 'pxom-mp-' + match[1]
            name = 'Modificación puntual número ' + match[1] + ' del PXOM de Ribadumia'
            kind = 'modificacion_planeamiento'
        elif title.startswith('PLAN DE ACCESIBILIDADE DO NUCLEO URBANO DE BARRANTES'):
            years = re.findall(r'\b20\d{2}\b', title)
            if len(years) != 1:
                raise ValueError('Ambiguous accessibility plan edition')
            key, name, kind = 'accesibilidad-barrantes-' + years[0], entry['titulo'], 'plan_accesibilidad'
        else:
            continue
        if not entry['documentos']:
            raise ValueError('Selected planning entry has no source documents')
        row = grouped.setdefault(key, {
            'id': 'ribadumia-proy-' + key, 'municipio': 'Ribadumia',
            'codigo_ine': '36046', 'provincia': 'Pontevedra', 'titulo': name,
            'tipo': kind, 'url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_informacion_publica', 'fecha': None,
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'documentos': [], 'publicaciones': [], 'lat': None, 'lon': None,
            'geometry': None, 'geometry_status': 'unavailable', 'publication_ready': False,
        })
        publication = {k: entry[k] for k in ('titulo', 'fecha_publicacion', 'descripcion')}
        publication['url'] = SOURCE
        if publication not in row['publicaciones']:
            row['publicaciones'].append(publication)
        for doc in entry['documentos']:
            if not any(d['url'] == doc['url'] for d in row['documentos']):
                row['documentos'].append({**doc, 'entrada_titulo': entry['titulo'],
                                          'fecha_publicacion': entry['fecha_publicacion'],
                                          'source_url': SOURCE})
    if not grouped:
        raise ValueError('No supported documented planning instruments in live inventory')
    for row in grouped.values():
        dates = {p['fecha_publicacion'] for p in row['publicaciones']}
        # Multiple publications remain explicit; no arbitrary date chosen.
        row['fecha_publicacion'] = next(iter(dates)) if len(dates) == 1 else None
    return sorted(grouped.values(), key=lambda r: r['id'])


class RibadumiaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        entries = []
        expected_meta = None
        fingerprints = set()
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-ribadumia/1.0 (public planning inventory)'
            response = session.get(SOURCE, timeout=40)
            page = 1
            while True:
                response.raise_for_status()
                if response.url != SOURCE:
                    raise ValueError('Unexpected inventory redirect')
                if self.config.get('capture_dir'):
                    capture = Path(self.config['capture_dir'])
                    capture.mkdir(parents=True, exist_ok=True)
                    (capture / f'inventory-page-{page}.html').write_text(response.text, encoding='utf-8')
                batch, (current, pages, total), soup = parse_page(response.text)
                if current != page or (expected_meta and expected_meta != (pages, total)):
                    raise ValueError('Pagination repeated or inventory changed during extraction')
                expected_meta = pages, total
                for item in batch:
                    fingerprint = json.dumps(item, sort_keys=True, ensure_ascii=False)
                    if fingerprint in fingerprints:
                        raise ValueError('Repeated inventory entry across pages')
                    fingerprints.add(fingerprint)
                entries.extend(batch)
                if page == pages:
                    break
                if page >= 100:
                    raise ValueError('Inventory exceeds pagination safety limit; no partial output accepted')
                payload = {i['name']: i.get('value', '') for i in soup.select('input[name]')
                           if i.get('type', '').lower() == 'hidden'}
                for select in soup.select('select[name]'):
                    option = select.select_one('option[selected]') or select.select_one('option')
                    payload[select['name']] = option['value']
                payload.update({'__EVENTTARGET': PREFIX + 'lbSiguiente', '__EVENTARGUMENT': ''})
                time.sleep(.3)
                response = session.post(SOURCE, data=payload, timeout=40)
                page += 1
        if len(entries) != total:
            raise ValueError('Incomplete inventory')
        rows = group_projects(entries)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_entries': total,
                'pages': pages, 'source_urls': [SOURCE], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
