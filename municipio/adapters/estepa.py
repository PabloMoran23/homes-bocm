"""Current official Estepa planning inventories; no inferred licences or geometry."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://transparencia.estepa.es'
PREFIX = ROOT + '/es/transparencia/indicadores-de-transparencia/indicador/'
INVENTORY = PREFIX + 'Plan-General-de-Ordenacion-Urbana-PGOU-y-planeamiento-de-desarrollo/'
MODIFICATIONS = PREFIX + 'Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00045/'
SOURCES = (INVENTORY, MODIFICATIONS)


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower()) if not unicodedata.combining(c))


def text(node):
    return node.get_text(' ', strip=True) if node else ''


def page_url(url):
    """Canonicalize gallery page 1 to the inventory, preserving other pages."""
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if parts.scheme != 'https' or parts.netloc != 'transparencia.estepa.es':
        raise ValueError('Unexpected inventory host')
    if parts.path.rstrip('/') not in {urlsplit(u).path.rstrip('/') for u in SOURCES}:
        raise ValueError('Unexpected inventory path')
    if any(not re.fullmatch(r'pagegalleryfiles-\d+-\d+', k) or not v.isdigit() or int(v) < 1 for k, v in query):
        raise ValueError('Unexpected pagination parameters')
    query = sorted((k, v) for k, v in query if v != '1')
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/') + '/', urlencode(query), ''))


def parse_inventory(html, url):
    """Return document observations and every advertised gallery page."""
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.sg-indicador-trans')
    if not article or not article.select_one('.contentblock section.gallery'):
        raise ValueError('Estepa planning inventory markup missing')
    observations = []
    is_main = urlsplit(url).path.rstrip('/') == urlsplit(INVENTORY).path.rstrip('/')
    for gallery in article.select('.contentblock section.gallery'):
        block = gallery.find_parent(class_='contentblock')
        heading = text(block.select_one('h3'))
        gallery_heading = text(gallery.select_one('h4.gallery-title'))
        narrative = text(block.select_one('.contentblock-texto'))
        for anchor in gallery.select('h4.title-element a[href], .sg-download-gallery tbody a[href]'):
            target = urljoin(url, anchor['href'])
            parsed = urlsplit(target)
            if parsed.netloc != 'transparencia.estepa.es' or not parsed.path.startswith('/export/sites/estepa/') or not parsed.path.lower().endswith('.pdf'):
                raise ValueError('Unexpected planning document URL')
            media = anchor.find_parent(class_='media')
            description = text(media.select_one('.description')) if media else ''
            title = text(anchor)
            context = norm(' '.join((title, description, gallery_heading)))
            # Generic ordinance consultation is not a planning instrument.
            if 'ordenanza' in context or 'licencia' in context:
                continue
            number = re.search(r'(\d+)\s*\.?\s*[ªº]?\s*modifica', context)
            if number:
                key = 'pgou-mod-' + str(int(number[1]))
                instrument_title = f'Modificación {int(number[1])} del PGOU de Estepa'
            elif 'plan especial de proteccion del conjunto historico' in norm(heading):
                key = 'pepch'
                instrument_title = 'Plan Especial de Protección del Conjunto Histórico de Estepa'
            elif (is_main and 'plan general de ordenacion' in norm(heading)) or anchor.find_parent(class_='sg-download-gallery'):
                key = 'pgou'
                instrument_title = 'Plan General de Ordenación Urbanística de Estepa — adaptación parcial de las NN.SS.'
            else:
                raise ValueError(f'Unclassified planning document: {title}')
            date_node = media.select_one('time[datetime]') if media else None
            observations.append({
                'key': key, 'instrument_title': instrument_title,
                'document': {'titulo': title, 'url': target, 'inventory_url': url,
                             'seccion': heading, 'grupo': gallery_heading,
                             'descripcion': description, 'contexto_seccion': narrative,
                             'fecha_publicacion': date_node['datetime'][:10] if date_node else None,
                             'date_provenance': 'CMS time[datetime]; not an agreement date' if date_node else None},
            })
    if not observations:
        raise ValueError('No usable planning documents found')
    pages = set()
    for anchor in article.select('a[href]'):
        href = anchor['href']
        if 'pagegalleryfiles-' in href:
            pages.add(page_url(urljoin(url, href)))
        elif ('pagelink' in ' '.join(anchor.get('class', [])) or 'next' in anchor.get('rel', [])) and href and not href.startswith('#'):
            raise ValueError('Unrecognized inventory pagination')
    return observations, sorted(pages)


def group_instruments(observations):
    records = {}
    for observation in observations:
        key = observation['key']
        row = records.setdefault(key, {
            'id': 'estepa-plan-' + key, 'municipio': 'Estepa', 'codigo_ine': '41041',
            'provincia': 'Sevilla', 'titulo': observation['instrument_title'],
            'tipo': 'instrumento de planeamiento urbanístico', 'url': INVENTORY if key in ('pgou', 'pepch', 'pgou-mod-1') else MODIFICATIONS,
            'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'documentos': [], 'source_urls': [], 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
        document = observation['document']
        if document not in row['documentos']:
            row['documentos'].append(document)
        if document['inventory_url'] not in row['source_urls']:
            row['source_urls'].append(document['inventory_url'])
    if not records:
        raise ValueError('Empty planning inventory')
    return list(records.values())


class EstepaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        pending = list(SOURCES)
        visited = set()
        observations = []
        captures = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-estepa/1.0 (public planning inventory)'
            while pending:
                url = page_url(pending.pop(0))
                if url in visited:
                    continue
                if len(visited) >= 100:
                    raise ValueError('Pagination exceeds safety bound; refusing partial output')
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if page_url(response.url) != url:
                    raise ValueError('Unexpected inventory redirect')
                response.encoding = 'utf-8'
                items, links = parse_inventory(response.text, url)
                visited.add(url)
                observations.extend(items)
                pending.extend(link for link in links if link not in visited)
                captures.append((url, response.content))
        rows = group_instruments(observations)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            for url, body in captures:
                (directory / ('source-' + hashlib.sha256(url.encode()).hexdigest()[:12] + '.html')).write_bytes(body)
        return {'count': len(rows), 'source_urls': sorted(visited), 'coverage': 'current planning document inventories; partial municipal coverage', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
