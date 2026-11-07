"""Capdepera's public planning folders and linked BOIB consolidation.

Only named, substantiated instruments are emitted. Folder labels and forms are
not records. This is a complete traversal of this inventory, not all municipal works.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://ajcapdepera.net/ca/enllacos/urbanisme'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def text(node):
    return node.get_text(' ', strip=True) if node else ''


def catalan_date(value):
    m = re.search(r"(\d{1,2})\s*(?:/|d[e’']?)\s*(\w+)\s*(?:/|de)\s*(\d{4})", value)
    if not m or m[2] not in MONTHS:
        return None
    return date(int(m[3]), MONTHS[m[2]], int(m[1])).isoformat()


def record(title, url, kind):
    return dict(id='capdepera-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                municipio='Capdepera', codigo_ine='07014', provincia='Illes Balears',
                titulo=title, tipo=kind, url=url, inventory_url=SOURCE,
                source='ayuntamiento', origen='inventario_planeamiento',
                fecha=None, fecha_publicacion=None, fecha_acuerdo=None, fecha_aprob=None,
                fase=None, lat=None, lon=None, geometry=None, publication_ready=False,
                geometry_status='No verified instrument geometry in extracted sources')


def parse_inventory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#block-consell-main-content')
    if main is None:
        raise ValueError('Missing municipal inventory content: ' + url)
    # Every folder, detail page and pagination link is traversed. No page cap.
    links = []
    for a in main.select('.taxonomy-term-files a[href], .links-results a[href], .pager a[href], a[rel~=next]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        if parsed.hostname == 'ajcapdepera.net' and parsed.path.startswith(('/ca/enllacos/', '/ca/enlla%C3%A7os/')):
            links.append(target)
    consolidations = []
    for heading in main.select('.links-results h4'):
        if text(heading) == 'Text consolidat NNSS Capdepera':
            container = heading.find_parent('div', class_='flex-wrap')
            anchors = container.select('a[href]') if container else []
            if len(anchors) != 1:
                raise ValueError('Ambiguous consolidation link')
            target = urljoin(url, anchors[0]['href'])
            if urlparse(target).hostname != 'www.caib.es' or '/eboibfront/' not in target:
                raise ValueError('Unexpected BOIB provenance')
            consolidations.append(target.replace('http://', 'https://', 1))
    rows = []
    prose = main.select_one('article.link-detail .prose')
    title = ' '.join(text(prose).split())
    if re.match(r'^Modificació\s+\d+/\d{4}\s+de les Normes Subsidiàries\b', title) and 'Capdepera' in title:
        row = record(title, url, 'modificació de NNSS')
        row['descripcion'] = title
        row['documentos'] = [{'titulo': 'Ficha municipal del instrumento', 'url': url,
                               'provenance': 'Ajuntament de Capdepera'}]
        rows.append(row)
    return links, consolidations, rows


def parse_consolidation(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    box = soup.select_one('.caja')
    title = text(box.select_one('p')) if box else ''
    narrative = ' '.join(text(soup).split())
    if not all(s in title for s in ('text consolidat', 'Capdepera')) or 'Donar conformitat al text consolidat' not in narrative:
        raise ValueError('BOIB does not substantiate the Capdepera consolidation')
    pdf = box.select_one('a.document[href]')
    if pdf is None:
        raise ValueError('Missing authentic BOIB document')
    pdf_url = urljoin(url, pdf['href'])
    if urlparse(pdf_url).hostname != 'www.caib.es':
        raise ValueError('Unexpected PDF origin')
    row = record('Text consolidat de les Normes subsidiàries de Capdepera', url, 'NNSS — text consolidat')
    agreement = re.search(r"en sessió de dia (.+?), ha pres l.acord", narrative)
    publication = re.search(r'Núm\.\s*\d+\s*-\s*(\d+\s*/\s*\w+\s*/\s*\d{4})', narrative)
    row.update(fecha_acuerdo=catalan_date(agreement[1]) if agreement else None,
               fecha_publicacion=catalan_date(publication[1]) if publication else None,
               fase='conformitat al text consolidat', url_documento=pdf_url,
               descripcion="Consolidació de les NNSS i modificacions posteriors. L'acord declara expressament que no implica aprovació definitiva d'un instrument de planejament.",
               documentos=[{'titulo': 'Acuerdo y texto consolidado (HTML)', 'url': url, 'provenance': 'BOIB'},
                           {'titulo': 'Versión oficial y auténtica (PDF)', 'url': pdf_url, 'provenance': 'BOIB'}])
    return row


class CapdeperaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def _fetch(self, url):
        with requests.get(url, timeout=40, stream=True, headers={'User-Agent': 'municipio-capdepera/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != urlparse(url).hostname:
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 5_000_000:
                    raise ValueError('Source exceeds 5 MB; refusing partial extraction')
                chunks.append(chunk)
            content = b''.join(chunks)
            if self.config.get('capture_dir'):
                folder = Path(self.config['capture_dir'])
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(content)
            return content.decode('utf-8')

    def backfill_proyectos(self, out_jsonl):
        pending, seen, boib, rows = [SOURCE], set(), set(), {}
        while pending:
            url = pending.pop(0)
            if url in seen:
                continue
            links, consolidations, parsed = parse_inventory(self._fetch(url), url)
            seen.add(url)
            pending.extend(link for link in links if link not in seen)
            boib.update(consolidations)
            for row in parsed:
                rows[row['id']] = row
        if len(boib) != 1:
            raise ValueError('Expected one unambiguous consolidated NNSS source')
        for url in sorted(boib):
            row = parse_consolidation(self._fetch(url), url)
            row['documentos'].insert(0, {'titulo': 'Inventario municipal', 'url': SOURCE, 'provenance': 'Ajuntament de Capdepera'})
            rows[row['id']] = row
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in sorted(rows.values(), key=lambda r: r['id'])), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(seen | boib),
                'coverage': 'Named instruments substantiated in municipal public planning folders; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
