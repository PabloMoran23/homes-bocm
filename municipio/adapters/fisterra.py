"""Fisterra's published PXOM and PEPRICH document inventories.

This is a snapshot of municipal publications, not a register of all projects or
an assertion that the PEPRICH's published procedural stage is still current.
"""
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

BASE = 'https://concellofisterra.gal'
INDEX = BASE + '/portal_cidadan/presentacion_urbanismo/gl'
PLANS = {
    'pxom': 'Plan Xeral de Ordenación Municipal',
    'peprich': 'Plan Especial do Casco Histórico de Fisterra (PEPRICH)',
}


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('#info .colcontido')
    if body is None or body.find('h2') is None:
        raise ValueError('Missing municipal planning content')
    # These reviewed inventories have no pagination. Refuse a partial snapshot
    # if the portal introduces it; never impose a successful first-page limit.
    if soup.select('[rel~=next], .pagination, .paginacion, .paxinacion, .paginador'):
        raise ValueError('Pagination introduced; crawler requires review')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).lower() in {'siguiente', 'seguinte', 'next', '>', '»'}:
            raise ValueError('Pagination introduced; crawler requires review')
    return body


def inventory_links(html, url):
    body = content(html)
    categories, documents = {}, {}
    for a in body.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        label = a.get_text(' ', strip=True)
        if parsed.hostname == urlparse(BASE).hostname and re.fullmatch(
            r'/portal_cidadan/descargas_areas/gl/\d+', parsed.path
        ):
            categories.setdefault(target, label)
        elif parsed.path.lower().endswith('.pdf'):
            if parsed.hostname not in {urlparse(BASE).hostname, 'bop.dacoruna.gal'}:
                raise ValueError('Unreviewed document host: ' + target)
            documents.setdefault(target, {
                'titulo': label if label.lower() not in {'descargar', '⇓ descargar'} else a.get('title', label),
                'url': target, 'source_url': url,
                'procedencia': 'BOP A Coruña' if parsed.hostname == 'bop.dacoruna.gal' else 'Concello de Fisterra',
            })
    return categories, documents


def parse_plan(html, key):
    body = content(html)
    heading = body.find('h2').get_text(' ', strip=True)
    expected = 'Plan Xeral de Ordenación Municipal' if key == 'pxom' else 'PEPRICH'
    if heading != expected:
        raise ValueError('Unexpected planning page heading: ' + heading)
    # Remove document listings and social controls before reading the narrative.
    narrative = ' '.join(p.get_text(' ', strip=True) for p in body.find_all('p', recursive=False)
                         if not p.get('class'))
    # The portal nests p tags inside p.intro (retained by html.parser).
    intro = body.select_one('p.intro')
    if intro:
        narrative = intro.get_text(' ', strip=True)
    row = {
        'id': 'fisterra-plan-' + key, 'municipio': 'Fisterra', 'codigo_ine': '15037',
        'provincia': 'A Coruña', 'titulo': PLANS[key], 'tipo': 'planeamiento_urbanistico',
        'url': BASE + '/portal_cidadan/' + key + '/gl', 'inventory_url': INDEX,
        'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
        'descripcion': narrative, 'fecha': None, 'fecha_publicacion': None,
        'fecha_acuerdo': None, 'fecha_aprob': None, 'fase': None,
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'coverage': 'Partial municipal planning document snapshot; no licence register',
        'date_provenance': 'Dates parsed only from the municipal page narrative at url',
        'limitations': (
            'BOP heading mentions 2020, but its body and municipal inventory give approval 2019-08-05; '
            'publication date is BOP publication, not website upload time.' if key == 'pxom' else
            'Municipal page says new initial approval; linked memory cover says provisional and definitive '
            '(September 2020). Document labels do not establish an approval agreement or current legal stage.'
        ),
    }
    if key == 'pxom':
        approval = re.search(r'aprobado pola Orde .*? do (\d{1,2}/\d{1,2}/\d{4})', narrative)
        publication = re.search(r'publicado no\s+BOP de data (\d{1,2}/\d{1,2}/\d{4})', narrative)
        for field, match in [('fecha_aprob', approval), ('fecha_publicacion', publication)]:
            if match:
                row[field] = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
        if approval:
            row['fase'] = 'aprobado por Orde (según página municipal)'
    elif 'Nova Aprobación Inicial' in narrative:
        row['fase'] = 'nova aprobación inicial por modificacións substanciais'
    if not narrative:
        raise ValueError('Planning page has no substantive narrative')
    return row


class FisterraAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-fisterra/1.0')})
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(BASE).hostname:
            raise ValueError('Unexpected municipal source redirect')
        html = response.text
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(html, encoding='utf-8')
        self.source_urls.append(url)
        return html

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        index = BeautifulSoup(self._fetch(INDEX), 'html.parser')
        links = {urljoin(INDEX, a['href']) for a in index.select('#columna .menu a[href]')}
        rows = []
        for key in PLANS:
            url = BASE + '/portal_cidadan/' + key + '/gl'
            if url not in links:
                raise ValueError('Plan missing from municipal urbanism index: ' + key)
            html = self._fetch(url)
            row = parse_plan(html, key)
            pending, docs = inventory_links(html, url)
            seen = set()
            while pending:
                page = next(iter(pending))
                del pending[page]
                if page in seen:
                    continue
                seen.add(page)
                if len(seen) > 100:
                    raise ValueError('Unexpected inventory expansion; no partial output written')
                children, attachments = inventory_links(self._fetch(page), page)
                if not children and not attachments:
                    raise ValueError('Empty document inventory: ' + page)
                pending.update({u: t for u, t in children.items() if u not in seen})
                for target, doc in attachments.items():
                    docs.setdefault(target, doc)
            if not docs or not seen:
                raise ValueError('Plan lacks document inventory')
            row['documentos'] = list(docs.values())
            row['document_inventory_urls'] = sorted(seen)
            rows.append(row)
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': self.source_urls, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
