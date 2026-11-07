"""Reviewed physical investment proposals in Brenes' official habitat news inventory.

This is partial coverage, not an approved planning or licence register.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.aytobrenes.es/es/temas/habitat-urbano/noticias-tema/'
LIMITATIONS = [
    'Cobertura parcial: propuestas de inversión física descritas en noticias de Hábitat Urbano; no registro de expedientes.',
    'Solo se reconocen las dos actuaciones con contenido revisado: Parque del Bodegón y antiguo Mercado de Abastos.',
    'La publicación no acredita aprobación, licitación, inicio, terminación ni vigencia actual de las actuaciones.',
    'Sin fechas de acuerdo/aprobación, geometría ni registro verificado de licencias concedidas.',
]


def official_url(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname != 'www.aytobrenes.es':
        raise ValueError('Unexpected source outside official municipal host')
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    listing = soup.select_one('main .listado-simple')
    if listing is None:
        raise ValueError('Municipal news inventory structure missing')
    # The reviewed inventory has no pagination. Fail closed on added controls,
    # rather than silently emit only its first page.
    if soup.select('.pagination, .paginacion, .pager, [rel="next"], [data-next-page]'):
        raise ValueError('Pagination detected: review crawler before extraction')
    for a in soup.select('main a[href]'):
        if re.search(r'siguiente|next|ver m[aá]s|cargar m[aá]s', a.get_text(' ', strip=True), re.I):
            raise ValueError('Additional inventory pages detected')
    links = {}
    for a in listing.select('.item h3 a[href]'):
        target = official_url(urljoin(url, a['href']).split('?')[0])
        if not target.startswith(SOURCE) or target == SOURCE:
            raise ValueError('Unexpected news detail URL')
        links[target] = a.get_text(' ', strip=True)
    if not links:
        raise ValueError('Empty municipal news inventory')
    return links


def parse_article(html, url, inventory_url=SOURCE):
    official_url(url)
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('main .pm-noticia-content')
    if article is None:
        raise ValueError('Municipal article structure missing')
    heading = article.select_one('h2.detail-t')
    body = article.select_one('.detail-p')
    if heading is None or body is None:
        raise ValueError('Article heading or body missing')
    title = heading.get_text(' ', strip=True)
    paragraphs = [p.get_text(' ', strip=True) for p in body.select('p')]
    text = ' '.join(paragraphs)
    # Reject forms, procurement-only announcements and general political news.
    # This deliberately requires the reviewed substantive investment context.
    if not all(term in text for term in ('proyectos que ejecutará', 'Sevilla 107', 'Ayuntamiento')):
        return []
    date_node = article.select_one('.detail-date')
    date = datetime.strptime(date_node.get_text(' ', strip=True), '%d/%m/%Y').date().isoformat() if date_node else None
    rows = []
    park = next((p for p in paragraphs if 'remodelación del Parque del Bodegón' in p and 'arroyo Buenavista' in p), None)
    market_index = next((i for i, p in enumerate(paragraphs) if 'antiguo Mercado de Abastos' in p and 'Cuadra y González' in p and 'rehabilitarlo' in p), None)
    proposals = []
    if park:
        proposals.append(('parque-bodegon', 'remodelación del Parque del Bodegón', [park]))
    if market_index is not None:
        selected = paragraphs[market_index:]
        if any('primera fase de reforma y rehabilitación' in p for p in selected):
            proposals.append(('mercado-abastos', 'antiguo Mercado de Abastos', selected))
    for key, name, description in proposals:
        docs = {url: {'titulo': title, 'url': url, 'tipo': 'noticia municipal descriptiva'}}
        for a in body.select('a[href]'):
            target = urljoin(url, a['href'])
            if urlsplit(target).path.lower().endswith('.pdf'):
                docs[target] = {'titulo': a.get_text(' ', strip=True), 'url': target, 'tipo': 'documento enlazado; contenido no verificado'}
        row = {
            'id': 'brenes-actuacion-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Brenes', 'provincia': 'Sevilla', 'codigo_ine': '41018',
            'titulo': name, 'tipo': 'actuacion_fisica_prevista',
            'descripcion': ' '.join(description), 'url': url, 'inventory_url': inventory_url,
            'source': 'ayuntamiento', 'origen': 'noticia_municipal_inversion_prevista',
            'documentos': list(docs.values()), 'titulo_publicacion': title,
            'estado_fuente': 'propuesta de inversión descrita en noticia municipal',
            'publication_ready': False, 'geometry_status': 'unavailable',
        }
        if date:
            row['fecha_publicacion'] = date
        rows.append(row)
    return rows


class BrenesAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        official_url(url)
        response = requests.get(url, timeout=35, headers={'User-Agent': 'municipio-brenes-inventory/1.0'})
        response.raise_for_status()
        official_url(response.url)
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected official HTML source')
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            (directory / name).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        links = parse_inventory(self._fetch(SOURCE))
        rows = {}
        for url in links:
            for row in parse_article(self._fetch(url), url):
                if row['id'] in rows:
                    existing = rows[row['id']]
                    for doc in row['documentos']:
                        if doc['url'] not in {d['url'] for d in existing['documentos']}:
                            existing['documentos'].append(doc)
                else:
                    rows[row['id']] = row
        if not rows:
            raise ValueError('No reviewed physical investment proposals found; source review required')
        self._write(out_jsonl, rows.values())
        return {'count': len(rows), 'written': len(rows), 'inventory_articles': len(links),
                'source_urls': [SOURCE, *links], 'limitations': LIMITATIONS,
                'publication_ready': False, 'coverage': 'partial_municipal_investment_proposals'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
