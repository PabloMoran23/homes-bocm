"""Partial snapshot of Boqueixón's official municipal planning documents."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.boqueixon.gal/servizos-municipais/urbanismo/'
STATUS_SOURCE = 'https://www.boqueixon.gal/pxom-nnss-1996/'
LIMITATIONS = [
    'Partial coverage: municipal Urbanismo document list only; not all SIOTUGA dossiers or public works.',
    'Modification 4 phase is the published document stage, not a claim about its latest legal status.',
    'Exact dates are not extracted from linked PDFs; upload paths and page metadata are not agreement dates.',
    'No granted-licence register or verified project geometry; no coordinates inferred.',
]


def parse_inventory(html: str, status_html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    section = soup.select_one('article.bqx-serv-urbanismo-gl #urbanismo-gl-documentos')
    if section is None:
        raise ValueError('Municipal planning document section missing')
    if soup.select('a[rel~=next], .pagination a, .nav-links .nav-next a'):
        raise ValueError('Pagination detected: single-page inventory coverage must be reviewed')
    status = BeautifulSoup(status_html, 'html.parser')
    # Require the visible municipal notice, not search metadata or navigation.
    notice = next((p.get_text(' ', strip=True) for p in status.select('p, h2')
                   if 'PXOM está anulado' in p.get_text(' ', strip=True)
                   and 'normativa en vigor son as NNSS 1996' in p.get_text(' ', strip=True)), None)
    if not notice:
        raise ValueError('Current NNSS / annulled PXOM municipal notice missing')
    base, modification, attachments = [], [], []
    for a in section.select('a[href]'):
        title = a.get_text(' ', strip=True)
        target = urljoin(SOURCE, a['href'])
        parsed = urlparse(target)
        if title.startswith('NORMAS SUBSIDIARIAS DE PLANEAMENTO'):
            if (parsed.hostname != 'siotuga.xunta.gal' or parsed.path != '/siotuga/inventario'
                    or parse_qs(parsed.query).get('idconcello') != ['15012']):
                raise ValueError('Wrong municipality or unexpected planning inventory URL')
            base.append({'titulo': title, 'url': target, 'rol': 'inventario_autonomico'})
        elif re.match(r'Modificación puntual Nº\s*4\b', title):
            if parsed.hostname != 'www.boqueixon.gal' or not parsed.path.lower().endswith('.pdf'):
                raise ValueError('Unexpected modification certificate URL')
            modification.append({'titulo': title, 'url': target, 'rol': 'certificado_acuerdo'})
        elif '15012_MP04NNSSPP_' in parsed.path or 'Anexo-9-Declaracion-responsable-concello' in parsed.path:
            if parsed.hostname != 'www.boqueixon.gal':
                raise ValueError('Unexpected attachment host')
            attachments.append({'titulo': title, 'url': target, 'rol': 'documentacion_modificacion_4'})
        else:
            # Fail visibly if the document inventory grows or changes grouping.
            raise ValueError(f'Unclassified municipal document: {title}')
    base = list({d['url']: d for d in base}.values())
    modification = list({d['url']: d for d in modification}.values())
    if len(base) != 1 or len(modification) != 1:
        raise ValueError('Expected one NNSS inventory and one modification 4 certificate')
    if 'Aprobación inicial' not in modification[0]['titulo']:
        raise ValueError('Modification document stage changed')
    rows = []
    for key, title, kind, phase, docs in [
        ('nnss-1996', base[0]['titulo'].removesuffix(' (ENLACE)'), 'normas subsidiarias',
         'normativa en vigor según aviso municipal', base),
        ('nnss-1996-mp04', modification[0]['titulo'].removesuffix(' (PDF)'),
         'modificación puntual de planeamiento', 'aprobación inicial', modification + attachments),
    ]:
        docs = list({d['url']: d for d in docs}.values())
        rows.append({
            'id': 'boqueixon-plan-' + key, 'municipio': 'Boqueixón',
            'codigo_ine': '15012', 'provincia': 'A Coruña',
            'titulo': title, 'tipo': kind, 'fase': phase,
            'url': SOURCE, 'url_documento': docs[0]['url'], 'documentos': docs,
            'source_urls': [SOURCE, STATUS_SOURCE], 'source': 'ayuntamiento',
            'origen': 'inventario_municipal_planeamiento',
            'descripcion': notice if key == 'nnss-1996' else modification[0]['titulo'],
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'date_status': 'No exact dates extracted from the HTML inventory; PDFs not date-parsed',
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False, 'coverage': 'partial_municipal_document_inventory',
        })
    return rows


class BoqueixonAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='boqueixon', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def _fetch(self, url: str, capture: str) -> str:
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'municipio-boqueixon/1.0 (public planning inventory)'})
        response.raise_for_status()
        if urlparse(response.url).hostname != 'www.boqueixon.gal':
            raise ValueError('Unexpected municipal source redirect')
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML planning source')
        response.encoding = 'utf-8'
        if self.config.get('evidence_dir'):
            folder = Path(self.config['evidence_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / capture).write_bytes(response.content)
        return response.text

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        html = self._fetch(SOURCE, 'urbanismo.html')
        status_html = self._fetch(STATUS_SOURCE, 'nnss.html')
        rows = parse_inventory(html, status_html)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, STATUS_SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full replacement of the small current inventory, with stable instrument IDs.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
