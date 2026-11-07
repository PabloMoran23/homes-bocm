"""Andoain's public-exhibition inventory, one record per planning instrument."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.andoain.eus/es/planes-exposicion-publica'
MONTHS = {name: i for i, name in enumerate(
    'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), 1)}
LIMITATIONS = [
    'Partial coverage: only instruments listed in the municipal public-exhibition inventory; not a complete planning or works history.',
    'Inventory membership does not establish that the statutory public consultation period remains open.',
    'Inventory dates are retained as labelled source claims; agreement and publication dates come from the linked BOG notice.',
    'No granted licences or verified vector geometry; no coordinates inferred from plans.',
    'Initial/final approval inventories contain inconsistent titles, dates and cross-links and are outside this adapter scope.',
]


def canonical(url, base=SOURCE):
    parsed = urlparse(urljoin(base, url))
    if parsed.hostname != 'www.andoain.eus':
        raise ValueError('Unexpected non-municipal source URL')
    return urlunparse(('https', parsed.netloc, parsed.path, '', '', ''))


def check_pagination(soup):
    for a in soup.select('a[href]'):
        if a['href'].strip() in ('', '#'):
            continue
        if ('next' in a.get('rel', []) or
                a.get_text(' ', strip=True).lower() in {'siguiente', 'hurrengoa', 'next', '›', '»'} or
                a.find_parent(class_=re.compile(r'pagination|paginator|pager'))):
            raise ValueError('Pagination detected: extend traversal before accepting output')


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    content = soup.select_one('[data-analytics-asset-id="544727"]')
    if not content or 'Planes en exposición pública' not in content.get_text(' ', strip=True):
        raise ValueError('Public exhibition inventory missing or language/markup changed')
    tables = content.select('table.cebra')
    if len(tables) != 1 or 'Fecha de acuerdo' not in tables[0].get_text(' ', strip=True):
        raise ValueError('Unrecognized inventory table')
    rows = {}
    # The live site puts its data rows inside THEAD and uses TH cells.
    for tr in tables[0].select('tr'):
        cells = tr.find_all(['th', 'td'], recursive=False)
        if cells and cells[0].get_text(' ', strip=True) == 'Nombre':
            continue
        if len(cells) != 4:
            raise ValueError('Unexpected inventory row')
        a, notice = cells[0].select_one('a[href]'), cells[3].select_one('a[href]')
        title = cells[0].get_text(' ', strip=True)
        if not a or not notice or 'Estudio de Detalle' not in title:
            raise ValueError('Unsupported instrument or missing source link')
        url = canonical(a['href'])
        raw_date = cells[2].get_text(' ', strip=True)
        d, m, y = map(int, raw_date.split('-'))
        claim_date = date(y, m, d).isoformat()
        row = {
            'id': 'andoain-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'municipio': 'Andoain', 'codigo_ine': '20009', 'provincia': 'Gipuzkoa',
            'titulo': title, 'tipo': 'estudio_de_detalle',
            'estado_inventario': cells[1].get_text(' ', strip=True),
            'url': url, 'source': 'ayuntamiento', 'origen': 'planeamiento_exposicion_publica',
            'source_url': SOURCE, 'fecha': None,
            'fecha_inventario': claim_date, 'fecha_inventario_etiqueta': 'Fecha de acuerdo',
            'url_anuncio': canonical(notice['href']),
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'cobertura': LIMITATIONS,
        }
        if url in rows and rows[url] != row:
            raise ValueError('Conflicting duplicate instrument')
        rows[url] = row
    if not rows:
        raise ValueError('Empty inventory requires review')
    return list(rows.values())


def parse_documents(html, detail_url):
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    articles = [el for el in soup.select('.journal-content-article')
                if any('Estudio de Detalle' in h.get_text(' ', strip=True) for h in el.select('h1'))
                and el.select('ul.destacado')]
    if len(articles) != 1:
        raise ValueError('Missing or ambiguous instrument documentation')
    docs = {}
    for a in articles[0].select('ul.destacado a[href]'):
        url = canonical(a['href'], detail_url)
        if '/documents/' not in url:
            raise ValueError('Unexpected document source')
        docs[url] = {'titulo': a.get_text(' ', strip=True), 'url': url, 'source_url': detail_url}
    if not any('Memoria' in d['titulo'] for d in docs.values()):
        raise ValueError('Missing substantive plan; an announcement alone is insufficient')
    return list(docs.values())


def parse_notice(text):
    text = re.sub(r'-\s*\n\s*', '', text)
    text = ' '.join(text.split())
    if 'AYUNTAMIENTO DE ANDOAIN' not in text or 'Estudio de Detalle' not in text:
        raise ValueError('Notice is not an Andoain detailed plan')
    approval = re.search(r'Mediante Resolución de Alcaldía n\.[ºo]\s*(\d+) de fecha (\d{1,2}) de (\w+) de (\d{4}), ha sido aprobado, con carácter inicial', text)
    publication = re.search(r'(?:Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo),?\s+a\s+(\d{1,2}) de (\w+) de (\d{4})', text)
    if not approval or not publication:
        raise ValueError('Unrecognized agreement/publication narrative in BOG notice')
    def iso(day, month, year):
        return date(int(year), MONTHS[month.lower()], int(day)).isoformat()
    return {'fecha_acuerdo': iso(*approval.group(2, 3, 4)),
            'fecha_publicacion': iso(*publication.group(1, 2, 3)),
            'fase': 'aprobación inicial', 'numero_resolucion': approval[1]}


class AndoainAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-andoain/1.0 (public planning inventory)'})
        response.raise_for_status()
        if urlparse(response.url).hostname != 'www.andoain.eus':
            raise ValueError('Unexpected source redirect')
        data = response.content
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            target = Path(capture_dir)
            target.mkdir(parents=True, exist_ok=True)
            suffix = '.pdf' if data.startswith(b'%PDF-') else '.html'
            (target / (hashlib.sha256(url.encode()).hexdigest()[:16] + suffix)).write_bytes(data)
        return data

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = parse_inventory(self._fetch(SOURCE).decode('utf-8'))
        for row in rows:
            docs = parse_documents(self._fetch(row['url']).decode('utf-8'), row['url'])
            if row['url_anuncio'] not in {d['url'] for d in docs}:
                raise ValueError('Inventory and instrument notice links disagree')
            pdf = self._fetch(row['url_anuncio'])
            if not pdf.startswith(b'%PDF-'):
                raise ValueError('Notice response is not PDF')
            result = subprocess.run(['pdftotext', '-raw', '-', '-'], input=pdf,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30)
            row.update(parse_notice(result.stdout.decode('utf-8')))
            row['documentos'] = docs
            row['date_provenance'] = {
                'fecha_acuerdo': row['url_anuncio'], 'fecha_publicacion': row['url_anuncio'],
                'fecha_inventario': SOURCE}
            row['discrepancia_fecha_inventario'] = row['fecha_inventario'] != row['fecha_acuerdo']
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + [r['url'] for r in rows],
                'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current snapshot, with no date cutoff; disappearance is not deletion.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
