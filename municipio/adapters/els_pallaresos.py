"""Narrow POUM advance snapshot, discovered in the official CIDO inventory.

The DOGC notice establishes the instrument, expediente and agreement date.
Municipal participation documents are attachments, never separate projects.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

INVENTORY = 'https://cido.diba.cat/normativa_local/7305489/planejament-urbanistic-ajuntament-dels-pallaresos'
PARTICIPA = 'https://elspallaresos.cat/wp-json/wp/v2/pages/1389'
PAGE = 'https://elspallaresos.cat/participa/'
MONTHS = 'gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split()
LIMITATIONS = [
    'Partial coverage: only the POUM advance advertised in the CIDO planning inventory; other instruments and works excluded.',
    'Municipal participation page has an outdated indicative timetable and unavailable advance/DIE cards; these do not establish approvals or publication dates.',
    'Linked participation PDFs retained as attachments, not parsed for geometry or separate projects.',
    'No granted-licence register extracted; no verified geometry or coordinates; publication_ready=false.',
]


def norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    if 'Ajuntament dels Pallaresos' not in text or 'Planejament urbanístic' not in text:
        raise ValueError('Unexpected CIDO municipality/inventory')
    for a in soup.select('a[href]'):
        if ('next' in a.get('rel', []) or
                a.get_text(' ', strip=True).lower() in {'següent', 'siguiente', 'next', '›', '»'} or
                a.find_parent(class_=re.compile('pagin', re.I))):
            raise ValueError('Inventory pagination detected; refusing partial snapshot')
    notices = {}
    for tr in soup.select('tr'):
        if "avanc del pla d'ordenacio urbanistica municipal" not in norm(tr.get_text(' ', strip=True)):
            continue
        timestamp = tr.select_one('time[datetime]')
        if not timestamp:
            raise ValueError('POUM notice lacks publication date')
        published = date.fromisoformat(timestamp['datetime']).isoformat()
        urls = list(dict.fromkeys(urljoin(INVENTORY, a['href']) for a in tr.select('a[href]')))
        pdfs = [u for u in urls if urlparse(u).hostname == 'portaldogc.gencat.cat'
                and urlparse(u).path == '/utilsEADOP/AppJava/PdfProviderServlet']
        if not pdfs:
            raise ValueError('POUM notice lacks official DOGC PDF')
        for pdf in pdfs:
            if pdf in notices and notices[pdf]['fecha_publicacion'] != published:
                raise ValueError('Conflicting publication dates')
            notices[pdf] = {'url': pdf, 'fecha_publicacion': published, 'enlaces': urls,
                            'descripcion_inventario': tr.get_text(' ', strip=True)}
    if not notices:
        raise ValueError('No supported POUM advance notice in current inventory')
    return list(notices.values())


def parse_notice(text, published):
    text = ' '.join(text.split())
    if 'AJUNTAMENT DELS PALLARESOS' not in text or not re.search(r"acord d.aprovar l.avanc", norm(text)):
        raise ValueError('PDF does not establish a Pallaresos POUM advance agreement')
    exp = re.search(r'exp\.\s*(\d+/\d{4})', text)
    agreement = re.search(r'sessió ordinària celebrada el dia (\d{1,2}) de (\w+) de (\d{4})', text)
    header = re.search(r'Núm\.\s*\d+\s*-\s*(\d{1,2})\.(\d{1,2})\.(\d{4})', text)
    if not exp or not agreement or not header:
        raise ValueError('Missing expediente, agreement date or bulletin header')
    approval = date(int(agreement[3]), MONTHS.index(agreement[2].lower()) + 1, int(agreement[1])).isoformat()
    pdf_publication = date(int(header[3]), int(header[2]), int(header[1])).isoformat()
    if pdf_publication != published:
        raise ValueError('CIDO/DOGC publication date mismatch')
    return {'expediente': exp[1], 'fecha_acuerdo': approval, 'fecha_aprob': approval,
            'fecha_publicacion': published, 'texto_anuncio': text}


def parse_documents(payload):
    if payload.get('id') != 1389 or payload.get('link') != PAGE:
        raise ValueError('Unexpected municipal participation page')
    content = payload['content']['rendered']
    # The municipality embeds static HTML in a shadow.innerHTML template.
    # Parse that literal as data; never execute JavaScript from the source.
    templates = re.findall(r'shadow\.innerHTML\s*=\s*`(.*?)`\s*;', content, re.S)
    soup = BeautifulSoup(templates[0] if len(templates) == 1 else content, 'html.parser')
    section = soup.select_one('#poum-documents')
    if not section or 'POUM dels Pallaresos' not in section.get_text(' ', strip=True):
        raise ValueError('POUM municipal document inventory missing')
    docs = {}
    for a in section.select('a.doc-card[href]'):
        if 'disabled' in a.get('class', []):
            continue
        url = urljoin(PAGE, a['href'])
        title = a.select_one('.doc-title')
        if urlparse(url).hostname != 'elspallaresos.cat' or not urlparse(url).path.lower().endswith('.pdf') or not title:
            raise ValueError('Unexpected document provenance')
        docs[url] = {'titulo': title.get_text(' ', strip=True), 'url': url,
                     'source_url': PAGE, 'relacion': 'documentacion_participacion_POUM'}
    if not docs:
        raise ValueError('No available POUM participation documents')
    return list(docs.values())


class ElsPallaresosAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://elspallaresos.cat')

    def _fetch(self, url, name):
        response = requests.get(url, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-els-pallaresos/1.0')})
        with response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 8_000_000:
                    raise ValueError('Source exceeds reviewed response limit')
                chunks.append(chunk)
        data = b''.join(chunks)
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir']) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return data

    def backfill_proyectos(self, out_jsonl):
        notices = parse_inventory(self._fetch(INVENTORY, 'planning-inventory.html').decode('utf-8'))
        docs = parse_documents(json.loads(self._fetch(PARTICIPA, 'participation-page.json')))
        rows = {}
        for i, notice in enumerate(notices):
            pdf = self._fetch(notice['url'], f'notice-{i}.pdf')
            if not pdf.startswith(b'%PDF-'):
                raise ValueError('DOGC returned non-PDF content')
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'notice.pdf'
                path.write_bytes(pdf)
                text = subprocess.run(['pdftotext', '-layout', str(path), '-'], check=True,
                                      capture_output=True, timeout=30).stdout.decode('utf-8')
            parsed = parse_notice(text, notice['fecha_publicacion'])
            key = parsed['expediente']
            row = rows.setdefault(key, {
                'id': 'els-pallaresos-poum-' + key.replace('/', '-'),
                'municipio': 'Els Pallaresos', 'codigo_ine': '43100', 'provincia': 'Tarragona',
                'titulo': "Avanç del Pla d'Ordenació Urbanística Municipal dels Pallaresos",
                'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación del avance; información pública',
                'expediente': key, 'fecha': None, 'fecha_acuerdo': parsed['fecha_acuerdo'],
                'fecha_aprob': parsed['fecha_aprob'], 'fecha_publicacion': parsed['fecha_publicacion'],
                'url': notice['url'], 'url_documento': notice['url'], 'source': 'ayuntamiento',
                'origen': 'DOGC_via_CIDO', 'source_urls': [INVENTORY, PARTICIPA, PAGE],
                'anuncios': [], 'documentos': list(docs), 'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'coverage': 'POUM advance only', 'limitations': LIMITATIONS,
            })
            if row['fecha_acuerdo'] != parsed['fecha_acuerdo']:
                raise ValueError('Conflicting POUM agreements')
            row['anuncios'].append({**notice, **parsed})
            for url in notice['enlaces']:
                if url not in row['source_urls']:
                    row['source_urls'].append(url)
                if not any(d['url'] == url for d in row['documentos']):
                    row['documentos'].append({'titulo': 'Anunci DOGC — avanç POUM', 'url': url,
                                              'source_url': INVENTORY, 'relacion': 'anuncio_oficial'})
            row['fecha_publicacion'] = min(row['fecha_publicacion'], parsed['fecha_publicacion'])
        if len(rows) != 1:
            raise ValueError('Multiple POUM expedientes; scope requires review')
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows.values()), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(dict.fromkeys(
            u for r in rows.values() for u in r['source_urls'])), 'limitations': LIMITATIONS,
            'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
