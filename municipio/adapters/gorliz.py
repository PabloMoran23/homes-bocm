"""Gorliz's current PGOU dossier and current development inventory (partial coverage)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.gorliz.eus'
ROOT = BASE + '/es-ES/Ayuntamiento/Urbanismo/'
STRUCTURAL = ROOT + 'Paginas/planeamiento-estructural.aspx'
DEVELOPMENT = ROOT + 'Paginas/planeamiento-desarrollo.aspx'
MONTHS = ('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split()


def official(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != 'www.gorliz.eus' or not parsed.path.startswith('/es-ES/Ayuntamiento/Urbanismo/'):
        raise ValueError('Unexpected urbanism source URL: ' + url)
    return url


def content(html, selector='#main-content'):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one(selector)
    if main is None:
        raise ValueError('Municipal content region missing: ' + selector)
    for a in main.select('a[href]'):
        if (a.get('rel') and 'next' in a['rel']) or re.search(r'^(siguiente|next|hurrengoa|[»›])$', a.get_text(' ', strip=True), re.I) or re.search(r'(?:[?&](?:page|paged|pagenumber|Paged)=)', a['href'], re.I):
            raise ValueError('Pagination detected; traversal requires review')
    return main


def links(node, source):
    found = {}
    for a in node.select('a[href]'):
        url = official(urljoin(source, a['href']))
        label = a.get_text(' ', strip=True)
        if not label:
            img = a.select_one('img[alt]')
            label = img['alt'] if img else ''
        found.setdefault(url, {'titulo': label, 'url': url, 'pagina_fuente': source})
    return list(found.values())


def pdf_documents(html, source):
    docs = links(content(html, '#ProcedureZone'), source)
    if not docs or any(not urlsplit(d['url']).path.lower().endswith('.pdf') for d in docs):
        raise ValueError('Expected a nonempty PDF document inventory: ' + source)
    return docs


def parse_development(html):
    # Historical plans are explicitly labelled "No vigente" in rightColumn.
    main = content(html)
    column = main.select_one('#centerColumn')
    if column is None or 'Planeamiento y desarrollo PGOU' not in column.get_text(' ', strip=True):
        raise ValueError('Current development inventory missing')
    groups, pages = {}, []
    for link in links(column, DEVELOPMENT):
        path = urlsplit(link['url']).path
        if path.lower().endswith('.pdf'):
            groups.setdefault(path.rsplit('/', 1)[0], []).append(link)
        elif path.lower().endswith('.aspx'):
            pages.append(link)
        else:
            raise ValueError('Unrecognized development entry')
    if not groups and not pages:
        raise ValueError('Empty current development inventory')
    for docs in groups.values():
        if not any(d['titulo'].startswith('Plan especial de regulación de las viviendas turísticas') for d in docs):
            raise ValueError('Unreviewed development document group')
    for page in pages:
        if not re.fullmatch(r'PAU A\.I\.E\.\s*\d+', page['titulo']):
            raise ValueError('Unreviewed development instrument')
    return list(groups.values()), pages


def spanish_date(text):
    match = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', text.lower())
    if not match or match[2] not in MONTHS:
        raise ValueError('Missing Spanish calendar date')
    return date(int(match[3]), MONTHS.index(match[2]) + 1, int(match[1])).isoformat()


def parse_notice(text, kind):
    text = ' '.join(text.split())
    if 'Ayuntamiento de Gorliz' not in text:
        raise ValueError('Notice municipality missing')
    publication = re.search(r'Núm\.\s*\d+\s+\w+,\s*(\d{1,2} de \w+ de \d{4})', text)
    agreement = re.search(r'sesión ordinaria celebrada el (\d{1,2} de \w+ de \d{4})', text)
    cve = re.search(r'BOB-\d{4}a\d+-\(II-\d+\)', text)
    if not publication or not agreement or not cve:
        raise ValueError('Notice dates or provenance missing')
    if kind == 'PAU':
        if not re.search(r'Aprobar definitivamente el PAU de la AIE\s*\d+', text):
            raise ValueError('PAU approval narrative missing')
        phase = 'aprobación definitiva'
    else:
        if 'Formular el Plan Especial de regulación de las viviendas turísticas' not in text:
            raise ValueError('Special plan formulation narrative missing')
        phase = 'formulación'
    agreed = spanish_date(agreement[1])
    return {'fecha_publicacion': spanish_date(publication[1]), 'fecha_acuerdo': agreed,
            'fecha_aprob': agreed if kind == 'PAU' else None, 'fase': phase,
            'cve': cve[0]}


class GorlizAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='gorliz', config=None, base_url=BASE):
        super().__init__(slug, config, base_url)
        self.source_urls = []

    def fetch(self, url, pdf=False):
        official(url)
        response = requests.get(url, timeout=45, headers={'User-Agent': 'municipio-gorliz/1.0'})
        response.raise_for_status()
        official(response.url)
        body = response.content
        if len(body) > 5_000_000:
            raise ValueError('Source exceeds reviewed response limit')
        if pdf and not body.startswith(b'%PDF-'):
            raise ValueError('Source is not a PDF')
        self.source_urls.append(url)
        capture = self.config.get('capture_dir')
        if capture:
            folder = Path(capture)
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + ('.pdf' if pdf else '.html')
            (folder / name).write_bytes(body)
        return body if pdf else body.decode('utf-8-sig')

    def notice(self, docs, kind):
        candidates = [d for d in docs if ('bob' in d['url'].lower())]
        if len(candidates) != 1:
            raise ValueError('Ambiguous official bulletin document')
        doc = candidates[0]
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'notice.pdf'
            path.write_bytes(self.fetch(doc['url'], pdf=True))
            # Preinstalled system utility, no optional Python PDF dependency.
            result = subprocess.run(['pdftotext', '-layout', str(path), '-'], check=True,
                                    capture_output=True, text=True, timeout=30)
        fields = parse_notice(result.stdout, kind)
        fields['procedencia_fechas'] = doc['url']
        return fields

    @staticmethod
    def record(key, title, url, docs, **extra):
        if not docs:
            raise ValueError('Instrument without documents')
        return {'id': 'gorliz-proy-' + key, 'municipio': 'Gorliz', 'codigo_ine': '48043',
                'provincia': 'Bizkaia', 'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
                'url': url, 'documentos': docs, 'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': None, 'fecha_aprob': None, 'fase': None,
                'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                'publication_ready': False, **extra}

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        structural = content(self.fetch(STRUCTURAL), '#ProcedureZone')
        current = [x for x in links(structural, STRUCTURAL) if x['titulo'] == 'PGOU en Vigor']
        if len(current) != 1:
            raise ValueError('Current PGOU link missing or ambiguous')
        pgou_url = current[0]['url']
        sections = links(content(self.fetch(pgou_url), '#ProcedureZone'), pgou_url)
        if {x['titulo'] for x in sections} != {'Memoria', 'Planos', 'Memoria EAE', 'Planos EAE'}:
            raise ValueError('PGOU sections changed; review scope before accepting')
        docs = {}
        for section in sections:
            for doc in pdf_documents(self.fetch(section['url']), section['url']):
                doc['seccion'] = section['titulo']
                docs.setdefault(doc['url'], doc)
        rows = [self.record('pgou', 'Plan General de Ordenación Urbana de Gorliz (PGOU)',
                            pgou_url, list(docs.values()), fase='en vigor según catálogo municipal',
                            notas='Dossier municipal con modificación de ordenanzas incorporada. No se verifica situación judicial ni vigencia jurídica de cada documento.')]
        groups, pages = parse_development(self.fetch(DEVELOPMENT))
        for documents in groups:
            rows.append(self.record('plan-viviendas-turisticas',
                        'Plan especial de regulación de las viviendas turísticas', DEVELOPMENT,
                        documents, **self.notice(documents, 'especial')))
        for page in pages:
            documents = pdf_documents(self.fetch(page['url']), page['url'])
            key = urlsplit(page['url']).path.rsplit('/', 1)[-1].removesuffix('.aspx')
            rows.append(self.record(key, page['titulo'], page['url'], documents,
                                    **self.notice(documents, 'PAU')))
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate instrument identity')
        result = self.write(out_jsonl, rows)
        return {**result, 'source_urls': self.source_urls, 'coverage': 'partial_current_planning'}

    @staticmethod
    def write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self.write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
