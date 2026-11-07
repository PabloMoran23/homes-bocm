"""Municipal PXOU document inventory; sheets are documents, not projects."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.aguarda.es'
URBANISMO = BASE + '/servizos-municipais/urbanismo/'


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('.entry-content')
    if main is None:
        raise ValueError('Missing municipal content')
    for a in soup.select('a[href]'):
        if (set(a.get('rel', [])) & {'next'} or
                re.search(r'^(seguinte|siguiente|next|[»›])$', a.get_text(strip=True), re.I) or
                re.search(r'/page/\d+|[?&]paged=\d+', a['href'])):
            raise ValueError('Unexpected pagination: inventory requires review')
    return main


def official_url(base, href):
    url = urljoin(base, href)
    if urlparse(url).hostname != 'www.aguarda.es' or urlparse(url).scheme != 'https':
        raise ValueError('Unexpected document host/scheme')
    return url.split('#')[0]


def discover(html):
    # Discover current inventories from the municipal service navigation.
    soup = BeautifulSoup(html, 'html.parser')
    found = {}
    for a in soup.select('a[href]'):
        label = normalized(a.get_text(' ', strip=True))
        if label in {'ordenanzas', 'planos'}:
            url = official_url(URBANISMO, a['href'])
            if not urlparse(url).path.startswith('/servizos-municipais/urbanismo/'):
                continue
            found[label] = url
    if set(found) != {'ordenanzas', 'planos'}:
        raise ValueError('Municipal planning inventories missing')
    return found


def parse_inventories(service_html, ordinance_html, maps_html, sources):
    service = content(service_html).get_text(' ', strip=True)
    match = re.search(r'Plan Xeral de Ordenación Urbana vixente con aprobación definitiva do (\d{2}\.\d{2}\.\d{2})', service)
    if not match:
        raise ValueError('Cannot verify municipal PXOU approval statement')
    approval = datetime.strptime(match[1], '%d.%m.%y').date().isoformat()
    records = {}
    for a in content(ordinance_html).select('a[href]'):
        title = a.get_text(' ', strip=True)
        key_title = normalized(title)
        if not re.match(r'^(plan xeral de ordenacion urbana|modificacion\b)', key_title):
            continue
        url = official_url(sources['ordenanzas'], a['href'])
        if not urlparse(url).path.lower().endswith('.pdf'):
            raise ValueError('Planning instrument no longer links a PDF')
        records.setdefault(url, {
            'id': 'a-guarda-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'municipio': 'A Guarda', 'codigo_ine': '36023', 'provincia': 'Pontevedra',
            'titulo': title, 'tipo': 'planeamiento_urbanistico', 'url': url,
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'inventory_url': sources['ordenanzas'],
            'documentos': [{'titulo': title, 'url': url, 'source_url': sources['ordenanzas'],
                            'tipo': 'normativa_urbanistica'}],
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    general = [r for r in records.values() if normalized(r['titulo']).startswith('plan xeral')]
    if len(general) != 1 or len(records) < 2:
        raise ValueError('Missing general plan or modifications; review source change')
    plan = general[0]
    plan['fecha_aprob'] = approval
    plan['fecha_aprob_source_url'] = URBANISMO
    plan['fase'] = 'aprobacion_definitiva'
    seen = set()
    for a in content(maps_html).select('a[href]'):
        url = official_url(sources['planos'], a['href']) if a['href'].startswith(('/', BASE)) else None
        if not url:
            continue  # Legacy external Xunta viewer is not a document.
        name = urlparse(url).path.rsplit('/', 1)[-1]
        if not (re.fullmatch(r'\d+\.\d+\.jpg', name) or name == 'referencia.jpg'):
            continue
        if url in seen:
            continue
        seen.add(url)
        plan['documentos'].append({'titulo': a.get_text(' ', strip=True), 'url': url,
                                   'source_url': sources['planos'], 'tipo': 'plano_escaneado'})
    if not any(d['url'].endswith('/referencia.jpg') for d in plan['documentos']) or len(seen) < 2:
        raise ValueError('Missing map inventory/index')
    return list(records.values())


class AGuardaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, capture_name):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-a-guarda/1.0 (public planning inventory)'})
        response.raise_for_status()
        official_url(BASE, response.url)
        directory = self.config.get('evidence_dir')
        if directory:
            target = Path(directory) / capture_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
        return response

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)
        return {'rows': len(rows), 'coverage': 'municipal_planning_document_inventory'}

    def backfill_proyectos(self, out_jsonl):
        service = self._fetch(URBANISMO, 'urbanismo.html').text
        sources = discover(service)
        ordinances = self._fetch(sources['ordenanzas'], 'ordenanzas.html').text
        maps = self._fetch(sources['planos'], 'planos.html').text
        rows = parse_inventories(service, ordinances, maps, sources)
        # Validate actual instrument documents, before replacing any previous output.
        for row in rows:
            name = urlparse(row['url']).path.rsplit('/', 1)[-1]
            response = self._fetch(row['url'], name)
            if not response.content.startswith(b'%PDF-'):
                raise ValueError('Instrument document is not a PDF')
        return self._write(out_jsonl, rows)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
