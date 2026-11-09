"""Municipal POM inventory; PDF content resolves incorrect municipal link labels.

Requires the existing pdftotext executable. Full current-page snapshot, not a
historical licence register or a claim of consolidated planning validity.
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

SOURCE = 'https://www.santacruzdelazarza.es/areas-y-servicios/urbanismo/plan-de-ordenaci%C3%B3n-municipal'
HOSTS = {'www.santacruzdelazarza.es', 'santacruzdelazarza.es'}
LIMITATIONS = [
    'Partial coverage: complete document table of the municipal POM page only; not a historical register or all municipal works.',
    'Municipal table mislabels PDFs: content distinguishes MP2, MP3 environmental resolution and PERI-3.',
    'Published documents do not establish current consolidated validity or subsequent approvals.',
    'No granted licence inventory or verified coordinates; licences and scheduling disabled.',
    'PDF plans retained as documents; no vector geometry extracted. pdftotext must be available.',
]
MONTHS = {m: i for i, m in enumerate('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), 1)}


def norm(text):
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


def spanish_date(text):
    match = re.search(r'(\d{1,2})\s+de\s+(\w+)\s+(?:de|ano)\s+(\d{4})', norm(text))
    if not match or match[2] not in MONTHS:
        return None
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


def official(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS:
        raise ValueError('Unexpected non-municipal source: ' + url)
    return url


def inventory(html, source=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('[itemprop="articleBody"]')
    heading = soup.select_one('h1')
    if body is None or heading is None or norm(heading.get_text()) != 'plan de ordenacion municipal':
        raise ValueError('Missing municipal POM article')
    if soup.select('.pagination, .pagenav, a[rel="next"], .article-index'):
        raise ValueError('Pagination detected: refusing incomplete inventory')
    docs = []
    seen = set()
    for row in body.select('table tr'):
        cells = row.find_all('td', recursive=False)
        if not cells:
            continue
        if len(cells) != 2 or not cells[1].select('a[href]'):
            raise ValueError('Changed document table row')
        label = cells[0].get_text(' ', strip=True)
        for a in cells[1].select('a[href]'):
            url = official(urljoin(source, a['href']))
            if not urlparse(url).path.lower().endswith('.pdf'):
                raise ValueError('Unexpected document format')
            if (label, url) not in seen:
                seen.add((label, url))
                docs.append({'titulo_fuente': label, 'url': url, 'inventory_url': source})
    if not docs:
        raise ValueError('No document inventory found')
    narrative = '\n'.join(p.get_text(' ', strip=True) for p in body.find_all('p'))
    return narrative, docs


def parse_projects(html, pdf_texts, source=SOURCE):
    """pdf_texts maps each non-base-POM PDF URL to its extracted actual content."""
    narrative, docs = inventory(html, source)
    groups = {}
    for doc in docs:
        label = norm(doc['titulo_fuente'])
        if label.startswith('plan de ordenacion municipal -'):
            key, title = 'pom', 'Plan de Ordenación Municipal de Santa Cruz de la Zarza'
        else:
            text = pdf_texts.get(doc['url'], '')
            prefix = norm(text[:3500])
            if 'santa cruz de la zarza' not in prefix:
                raise ValueError('Unverified PDF municipality or missing PDF text')
            if re.search(r'peri\s*-\s*3', prefix):
                key, title = 'peri-3', 'PERI-3 del Plan de Ordenación Municipal de Santa Cruz de la Zarza'
            elif re.search(r'modificacion puntual (?:no?\s*)?3\b', prefix):
                key, title = 'mp-3', 'Modificación puntual nº 3 del POM de Santa Cruz de la Zarza'
            elif re.search(r'modificacion puntual (?:numero|no?)\s*2\b', prefix):
                key, title = 'mp-2', 'Modificación puntual nº 2 del POM de Santa Cruz de la Zarza'
            else:
                raise ValueError('Unknown planning PDF; do not guess from table label')
            doc = {**doc, 'identificacion': 'contenido_pdf', 'extracto_identificacion': text[:700]}
        if key not in groups:
            groups[key] = {
                'id': 'santa-cruz-de-la-zarza-plan-' + key,
                'municipio': 'Santa Cruz de la Zarza', 'codigo_ine': '45156', 'provincia': 'Toledo',
                'titulo': title, 'tipo': 'instrumento de planeamiento',
                'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
                'url': source, 'inventory_url': source, 'documentos': [],
                'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'fase': None, 'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            }
        record = groups[key]
        record['documentos'].append(doc)
        if key == 'pom':
            match = re.search(r'El Plan de Ordenación Municipal de Santa Cruz de la Zarza se aprobó definitivamente[^.]+', narrative, re.I)
            if match:
                record.update(fase='aprobación definitiva', fecha_aprob=spanish_date(match[0]), fecha_aprob_fuente=source)
        elif key == 'mp-2':
            if 'aprobada definitivamente' not in norm(text):
                raise ValueError('MP2 approval narrative missing')
            approval = re.search(r'sesion de fecha ([^.]+)', norm(text))
            record.update(fase='aprobación definitiva', fecha_publicacion=spanish_date(text[:350]),
                          fecha_aprob=spanish_date(approval[1]) if approval else None,
                          fechas_fuente=doc['url'])
        elif key == 'mp-3':
            if 'no sometimiento a evaluacion ambiental' not in norm(text):
                raise ValueError('Unexpected MP3 resolution')
            resolution = re.search(r'Resolución de (\d{2})/(\d{2})/(\d{4})', text)
            record.update(fase='resolución ambiental de no sometimiento',
                          fecha_publicacion=spanish_date(text[:350]), fechas_fuente=doc['url'],
                          fecha_resolucion=date(int(resolution[3]), int(resolution[2]), int(resolution[1])).isoformat() if resolution else None)
    for record in groups.values():
        record['coverage'] = 'current_municipal_document_inventory_partial'
        record['limitations'] = LIMITATIONS
    return list(groups.values())


class SantaCruzDeLaZarzaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, url, capture_name):
        official(url)
        response = requests.get(url, timeout=60, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        official(response.url)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / capture_name).write_bytes(response.content)
        return response.content

    def backfill_proyectos(self, out_jsonl):
        html = self._get(SOURCE, 'plan-inventory.html').decode('utf-8')
        _, docs = inventory(html)
        texts = {}
        for doc in docs:
            if norm(doc['titulo_fuente']).startswith('plan de ordenacion municipal -'):
                continue
            raw = self._get(doc['url'], doc['url'].rsplit('/', 1)[-1])
            if not raw.startswith(b'%PDF-'):
                raise ValueError('Document response is not PDF')
            with tempfile.TemporaryDirectory() as directory:
                pdf = Path(directory) / 'source.pdf'
                pdf.write_bytes(raw)
                result = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], check=True, capture_output=True, timeout=45)
                texts[doc['url']] = result.stdout.decode('utf-8')
        rows = parse_projects(html, texts)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'documents': sum(len(r['documentos']) for r in rows),
                'source_urls': [SOURCE] + [d['url'] for d in docs], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
