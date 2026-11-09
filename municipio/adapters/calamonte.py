"""Calamonte's official planning inventory; document identity precedes CMS labels."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://calamonte.org/servicios/oficina-tecnica/'
API = 'https://calamonte.org/wp-json/wp/v2/pages?slug=oficina-tecnica'
DOE = 'https://doe.juntaex.es/otrosFormatos/html.php?anio=2024&doe=510o&xml=2024AC0022'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def text_date(text):
    match = re.search(r'(\d{1,2}) de (' + '|'.join(MONTHS) + r') de (\d{4})', text, re.I)
    if not match:
        raise ValueError('Missing explicit Spanish date')
    return date(int(match[3]), MONTHS.index(match[2].lower()) + 1, int(match[1])).isoformat()


def record(key, title, kind, documents, **extra):
    if not documents:
        raise ValueError('Instrument without documents: ' + title)
    return dict(id='calamonte-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                municipio='Calamonte', provincia='Badajoz', codigo_ine='06025',
                titulo=title, tipo=kind, url=SOURCE, inventory_url=API,
                source='ayuntamiento', origen='inventario_planeamiento',
                documentos=documents, fecha_publicacion=None, fecha_acuerdo=None,
                lat=None, lon=None, geometry=None, geometry_status='unavailable',
                publication_ready=False, **extra)


def parse_inventory(html):
    """Read whole curated page, grouping attachments under their actual heading."""
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('a[rel~=next], .pagination, .page-numbers'):
        raise ValueError('Unexpected pagination in single-page planning inventory')
    headings = [h for h in soup.find_all('h3') if h.get_text(' ', strip=True).upper() in
                ('NORMAS SUBSIDIARIAS', 'PLAN PARCIAL DEHESA DEL REY')]
    if len(headings) != 2:
        raise ValueError('Planning inventory sections changed')
    groups = {'pgm': [], 'nnss': [], 'pp': [], 'modifications': []}
    for heading in headings:
        listing = heading.find_next_sibling('ul')
        if listing is None:
            raise ValueError('Missing planning document list')
        for a in listing.select('a[href]'):
            label = a.get_text(' ', strip=True)
            url = urljoin(SOURCE, a['href'])
            if urlparse(url).hostname not in ('calamonte.org', 'www.calamonte.org', 'drive.google.com'):
                raise ValueError('Unexpected planning document host')
            doc = {'titulo_enlace': label, 'url': url, 'source_url': SOURCE}
            if label.lower().startswith('aprobación definitiva de la modificación'):
                group = 'modifications'
            elif label.lower().startswith('plan general municipal'):
                group = 'pgm'
            else:
                group = 'nnss' if heading.get_text(strip=True).upper() == 'NORMAS SUBSIDIARIAS' else 'pp'
            if doc not in groups[group]:
                groups[group].append(doc)
    if any(not docs for docs in groups.values()):
        raise ValueError('Incomplete planning inventory')
    rows = [record('pgm', 'Plan General Municipal de Calamonte', 'plan general municipal', groups['pgm']),
            record('nnss', 'Normas Subsidiarias de Calamonte — documentación histórica',
                   'normas subsidiarias', groups['nnss'], vigencia='no verificada; documentación histórica'),
            record('pp-dehesa-del-rey', 'Plan Parcial Dehesa del Rey', 'plan parcial', groups['pp'])]
    return rows, groups['modifications']


def parse_modification(text, document):
    """Parse actual PDF heading; the two municipal anchor labels are interchanged."""
    text = ' '.join(text.split())
    heading = re.search(r'RESOLUCIÓN de (.+?) La Comisión de Urbanismo', text)
    publication = re.search(r'NÚMERO \d+ (.+?) \d+ RESOLUCIÓN', text)
    if not heading or not publication or 'Calamonte' not in heading[1]:
        raise ValueError('Unrecognized modification PDF')
    title = heading[1]
    if '2010060841' in title and 'SUP-I1 y SUP-I2' in title:
        key, name = 'mod-pp-sup-i1-i2', 'Modificación puntual del Plan Parcial de los Sectores SUP-I1 y SUP-I2 de Calamonte'
    elif '2015060595' in title and '1/2014' in title:
        key, name = 'mod-nnss-1-2014', 'Modificación puntual n.º 1/2014 de las NNSS y del Plan Parcial Industrial Dehesa del Rey'
    else:
        raise ValueError('Unknown modification identity; review document before adding')
    row = record(key, name, 'modificación de planeamiento', [document],
                 fase='aprobación definitiva', titulo_documento='RESOLUCIÓN de ' + title,
                 document_identity_basis='Texto del PDF, no título del enlace municipal',
                 source_label_mismatch=(('1/2014' in document['titulo_enlace']) != (key == 'mod-nnss-1-2014')))
    row['fecha_acuerdo'] = text_date(title)
    row['fecha_publicacion'] = text_date(publication[1])
    row['date_provenance'] = {'fecha_acuerdo': document['url'], 'fecha_publicacion': document['url']}
    return row


def enrich_pgm(row, html):
    soup = BeautifulSoup(html, 'html.parser')
    text = ' '.join(soup.stripped_strings)
    title = re.search(r'Acuerdo de (.+?aprobación definitiva parcial del Plan General Municipal de Calamonte\.)', text)
    publication = re.search(r'Fecha Publicación:\s*(.+?) Apartado:', text)
    if not title or not publication or 'Dejar en suspenso' not in text:
        raise ValueError('PGM approval scope could not be verified against DOE')
    row['fase'] = 'aprobación definitiva parcial'
    row['fecha_acuerdo'] = text_date(title[1])
    row['fecha_publicacion'] = text_date(publication[1])
    row['date_provenance'] = {'fecha_acuerdo': DOE, 'fecha_publicacion': DOE}
    row['limitaciones'] = ('Acuerdo publicado: queda en suspenso la ordenación de UA-9 de las NNSS '
                           'y terrenos colindantes incluidos en UA-1. No se verifica subsanación posterior ni vigencia consolidada.')
    row['documentos'].append({'titulo_enlace': 'Acuerdo DOE: aprobación definitiva parcial', 'url': DOE, 'source_url': DOE})


class CalamonteAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='calamonte', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl):
        session = requests.Session()
        session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; CalamontePlanningInventory/1.0)'
        captures = self.config.get('capture_dir')
        capture_dir = Path(captures) if captures else None
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
        visited = []

        def fetch(url, name):
            response = session.get(url, timeout=45)
            response.raise_for_status()
            if urlparse(response.url).hostname != urlparse(url).hostname:
                raise ValueError('Unexpected source redirect')
            visited.append(response.url)
            if capture_dir:
                (capture_dir / name).write_bytes(response.content)
            return response

        response = fetch(API, 'oficina-tecnica.json')
        pages = response.json()
        if (response.headers.get('X-WP-TotalPages') != '1' or
                response.headers.get('X-WP-Total') != '1' or
                not isinstance(pages, list) or len(pages) != 1 or
                pages[0].get('link') != SOURCE or pages[0].get('slug') != 'oficina-tecnica'):
            raise ValueError('Ambiguous or paginated WordPress page lookup')
        rows, modifications = parse_inventory(pages[0]['content']['rendered'])
        enrich_pgm(rows[0], fetch(DOE, 'doe-pgm.html').text)
        # pdftotext is an existing system utility, used only for these two public PDFs.
        # Without it extraction fails explicitly, rather than trusting swapped labels.
        for i, document in enumerate(modifications):
            pdf = fetch(document['url'], f'modification-{i}.pdf').content
            if not pdf.startswith(b'%PDF-'):
                raise ValueError('Planning attachment is not a PDF')
            with tempfile.TemporaryDirectory(prefix='calamonte-') as tmp:
                source = Path(tmp) / 'document.pdf'
                source.write_bytes(pdf)
                result = subprocess.run(['pdftotext', str(source), '-'], check=True,
                                        capture_output=True, timeout=30)
            text = result.stdout.decode('utf-8')
            if capture_dir:
                (capture_dir / f'modification-{i}.txt').write_text(text, encoding='utf-8')
            rows.append(parse_modification(text, document))
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate instrument identity')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'source_urls': [SOURCE, *visited],
                'coverage': 'complete current curated page; partial municipal planning coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'Application forms are not granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
