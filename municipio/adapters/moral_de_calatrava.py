"""Current official planning inventory; documents are grouped by instrument."""
from __future__ import annotations

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

HOST = 'moraldecalatrava.sedelectronica.es'
ROOT = f'https://{HOST}'
INVENTORY = ROOT + '/transparency/e13025be-2d42-4311-89ce-ca0df4791a34/'
NORMAS = ROOT + '/transparency/ef8dd259-fbaa-4e55-af23-0ee3da99ad73/'
SECTOR8 = ROOT + '/transparency/ec8b8c7a-6e3b-4f06-8348-94942c3fa563/'
LIMITATIONS = [
    'Partial coverage: current transparency planning folder only; not a historical project or licence register.',
    'SECTOR RA (scanned PDF, insufficient instrument identity) and Trámite de consulta pública excluded.',
    'No verified geometry; no coordinates or geocoding inferred.',
    'Publication dates unavailable. PDF signature/creation dates and filename dates are not publication or agreement dates.',
    'MP 1/2021 definitive PDF is scanned; approval date and legal effectiveness not established.',
    'Inventory pagination or unexpected structure causes an error rather than a partial successful snapshot.',
]


def official_url(url):
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != HOST:
        raise ValueError('Unexpected non-municipal source URL')
    return url


def parse_inventory(html, url):
    """Read every visible entry; refuse paginated/changed inventories."""
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content')
    if content is None or 'PLANEAMIENTO URBANÍSTICO' not in content.get_text(' ', strip=True):
        raise ValueError('Missing planning inventory identity')
    if re.search(r'Mostrar\s+más|Siguiente|Página\s+\d+\s+de', content.get_text(' ', strip=True), re.I) or content.select('.pagination, .navigator, a[rel="next"]'):
        raise ValueError('Pagination detected: refusing incomplete inventory')
    documents, folders = [], []
    for a in content.select('a.gIconLink'):
        label = a.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            count = re.search(r'\(\s*(\d+)\s*\)$', label)
            if not count:
                raise ValueError('Folder without document count')
            folders.append({'titulo': label[:count.start()].strip(), 'count': int(count[1])})
        else:
            target = official_url(urljoin(url, a.get('href', '')))
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(target).path):
                raise ValueError('Unexpected document link')
            documents.append({'titulo': label, 'url': target, 'inventory_url': url})
    if not documents and not folders:
        raise ValueError('Empty inventory')
    return documents, folders


def parse_sector8_agreement(text):
    text = ' '.join(text.split())
    reference = re.search(r'Expte\.:\s*(\d+/\d{4})', text)
    meeting = re.search(r'sesión ordinaria celebrada el día (\d{1,2}) de septiembre de (\d{4})', text, re.I)
    adopted = re.search(r'ningún voto en contra\), ACUERDA:\s*(.*)', text, re.I)
    decision = adopted and re.search(r'Primero\.\s*-\s*Aprobar definitivamente el Plan parcial de mejora del sector 8 industrial', adopted[1], re.I)
    if not reference or not meeting or not decision or 'Moral de Calatrava' not in text:
        raise ValueError('Sector 8 agreement evidence missing or changed')
    return reference[1], date(int(meeting[2]), 9, int(meeting[1])).isoformat()


def group_projects(main, normas, sector8, agreement):
    documents, folders = main
    if {f['titulo'] for f in folders} != {'NORMAS SUBSIDIARIAS', 'Plan parcial de mejora. SECTOR 8 INDUSTRIAL'}:
        raise ValueError('Planning folder set changed; review new instruments')
    for title, children in [('NORMAS SUBSIDIARIAS', normas), ('Plan parcial de mejora. SECTOR 8 INDUSTRIAL', sector8)]:
        if children[1] or len(children[0]) != next(f['count'] for f in folders if f['titulo'] == title):
            raise ValueError('Incomplete child folder')
    allowed = {'SECTOR RA', 'Trámite de consulta pública', 'MP_1_2021_Moral_2021_08_01_completo', 'MODIFICACION_PUNTUAL_1_2021_DEFINITIVA'}
    if {d['titulo'] for d in documents} != allowed or len(documents) != len(allowed):
        raise ValueError('Top-level planning documents changed; review grouping')
    mp = [d for d in documents if d['titulo'] in {'MP_1_2021_Moral_2021_08_01_completo', 'MODIFICACION_PUNTUAL_1_2021_DEFINITIVA'}]
    if not any(d['titulo'] == 'NORMATIVA' for d in normas[0]):
        raise ValueError('Normas document missing')
    if not any(d['titulo'] == 'Certficado acuerdo plenario' for d in sector8[0]):
        raise ValueError('Sector 8 certificate missing')
    reference, agreement_date = parse_sector8_agreement(agreement)
    rows = []
    for key, title, kind, url, docs in [
        ('normas-subsidiarias', 'Normas Subsidiarias de Moral de Calatrava', 'Normas Subsidiarias', NORMAS, normas[0]),
        ('mp-1-2021', 'Modificación puntual 1/2021 de las Normas Subsidiarias de Moral de Calatrava', 'Modificación puntual', INVENTORY, mp),
        ('sector-8-industrial', 'Plan parcial de mejora del Sector 8 Industrial', 'Plan parcial de mejora', SECTOR8, sector8[0]),
    ]:
        row = {'id': 'moral-de-calatrava-plan-' + key, 'municipio': 'Moral de Calatrava',
               'codigo_ine': '13058', 'provincia': 'Ciudad Real', 'titulo': title, 'tipo': kind,
               'url': url, 'inventory_url': INVENTORY, 'source': 'ayuntamiento',
               'origen': 'portal_transparencia_planeamiento', 'documentos': docs,
               'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
               'fase': None, 'lat': None, 'lon': None, 'geometry': None,
               'geometry_status': 'unavailable', 'publication_ready': False,
               'coverage': 'current_planning_inventory_partial'}
        if key == 'sector-8-industrial':
            row.update(expediente=reference, fecha_acuerdo=agreement_date,
                       fecha_aprob=agreement_date, fase='aprobación definitiva',
                       acuerdo_source_url=next(d['url'] for d in docs if d['titulo'] == 'Certficado acuerdo plenario'))
        rows.append(row)
    return rows


class MoralDeCalatravaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, session, url, capture):
        official_url(url)
        response = session.get(url, timeout=60)
        response.raise_for_status()
        official_url(response.url)
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / capture).write_bytes(response.content)
        return response

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-moral-de-calatrava/1.0'
            parsed = []
            for name, url in [('planeamiento', INVENTORY), ('normas', NORMAS), ('sector8', SECTOR8)]:
                response = self._get(session, url, name + '.html')
                parsed.append(parse_inventory(response.text, url))
            certs = [d for d in parsed[2][0] if d['titulo'] == 'Certficado acuerdo plenario']
            if len(certs) != 1:
                raise ValueError('Expected one Sector 8 certificate')
            preview = self._get(session, certs[0]['url'], 'sector8-acuerdo-preview.html')
            frame = BeautifulSoup(preview.text, 'html.parser').select_one('#pdfPreview iframe[src]')
            if frame is None:
                raise ValueError('Certificate PDF unavailable')
            pdf = self._get(session, urljoin(preview.url, frame['src']), 'sector8-acuerdo.pdf')
            if not pdf.content.startswith(b'%PDF-'):
                raise ValueError('Certificate is not a PDF')
            with tempfile.TemporaryDirectory() as folder:
                source = Path(folder) / 'certificate.pdf'
                source.write_bytes(pdf.content)
                result = subprocess.run(['pdftotext', '-layout', str(source), '-'], check=True,
                                        capture_output=True, timeout=60)
                agreement = result.stdout.decode('utf-8')
            if self.config.get('capture_dir'):
                (Path(self.config['capture_dir']) / 'sector8-acuerdo.txt').write_text(agreement, encoding='utf-8')
            rows = group_projects(*parsed, agreement)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [INVENTORY, NORMAS, SECTOR8, certs[0]['url']],
                'inventory_documents': sum(len(p[0]) for p in parsed), 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current snapshot, including removals; no invented date cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
