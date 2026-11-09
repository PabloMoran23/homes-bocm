"""Santa Susanna planning instruments from the municipally linked public RPUC."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'https://planejamenturbanisme.territori.gencat.cat'
API = HOST + '/RPUC-portal/rest/consulta/'
INVENTORY = HOST + '/rpucportal/index.html#/consulta/cercaPublic?reqCode=cerca&municipiSel=08261'
MUNICIPAL_SOURCE = 'https://www.seu-e.cat/web/santasusanna/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic'


def source_date(value):
    if value is None or value == '':
        return None
    # Only explicit detail dates are used, never generic listing "data".
    return date.fromisoformat(value).isoformat()


def parse_page(payload):
    if not isinstance(payload, dict) or type(payload.get('totals')) is not int:
        raise ValueError('Invalid RPUC inventory response')
    rows = payload.get('llistat')
    if not isinstance(rows, list) or payload['totals'] < 0:
        raise ValueError('Invalid RPUC inventory rows/total')
    for row in rows:
        if not isinstance(row, dict) or not re.fullmatch(r'\d+', str(row.get('codi', ''))):
            raise ValueError('Invalid RPUC dossier identifier')
        if not row.get('municipi') or not row.get('instrumentca') or not row.get('tema'):
            raise ValueError('Missing RPUC inventory metadata')
    return payload['totals'], rows


def is_local_instrument(row):
    return (row['municipi'].strip() == 'Santa Susanna'
            and re.match(r'^(Pla |Modificació (?:de |del |pla )|Revisió pla )', row['instrumentca']) is not None
            and row['instrumentca'].strip() != 'Modificació de les TUC')


def parse_project(row, detail):
    ident = str(row['codi'])
    if (not is_local_instrument(row) or not isinstance(detail, dict)
            or str(detail.get('codintExp')) != ident
            or detail.get('municipi') != 'Santa Susanna'
            or not detail.get('tema') or not detail.get('tipologiaCA')
            or not detail.get('numComplet')):
        raise ValueError('RPUC detail does not match Santa Susanna instrument')
    docs = detail.get('documents')
    if not isinstance(docs, list):
        raise ValueError('Missing RPUC document list')
    documents = {}
    for doc in docs:
        doc_id = str(doc.get('idDocument', ''))
        if not doc_id.isdigit() or not doc.get('nomDocument'):
            raise ValueError('Invalid RPUC document metadata')
        document = dict(doc)
        document['url'] = API + 'documents?' + urlencode({
            'documentId': doc_id, 'downloadType': 'inline', 'idioma': 'ca'})
        if doc_id in documents and documents[doc_id] != document:
            raise ValueError('Conflicting document metadata')
        documents[doc_id] = document
    url = HOST + '/rpucportal/#/consulta/detallExpedient/' + ident
    return {
        'id': 'santa-susanna-rpuc-' + ident, 'municipio': 'Santa Susanna',
        'codigo_ine': '08261', 'provincia': 'Barcelona',
        'titulo': detail['tema'].strip(), 'tipo': detail['tipologiaCA'].strip(),
        'expediente': detail['numComplet'], 'rpuc_id': ident,
        'fecha': None, 'fecha_aprob': source_date(detail.get('dataAprovacio')),
        'fecha_publicacion': source_date(detail.get('dataPublicacio')), 'fase': None,
        'url': url, 'inventory_url': INVENTORY, 'municipal_source_url': MUNICIPAL_SOURCE,
        'detail_source_url': API + 'detall?' + urlencode({
            'codiExpedient': ident, 'idioma': 'ca', 'cercaPublic': 'false'}),
        'source': 'ayuntamiento', 'origen': 'rpuc_planeamiento',
        'source_authority': 'Generalitat de Catalunya — RPUC',
        'vigencia_source': row.get('vigencia'), 'registrat_source': row.get('registrat'),
        'documentos': list(documents.values()),
        'referencia_butlletins': detail.get('referenciaButlletins'),
        'assentaments': detail.get('assentaments'),
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified instrument geometry extracted',
    }


class SantaSusannaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.stasusanna.cat')
        self.source_urls = []

    def _get(self, endpoint, params, capture):
        with requests.get(API + endpoint, params=params, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-santa-susanna/1.0'}) as response:
            response.raise_for_status()
            if response.url.split('?', 1)[0] != API + endpoint:
                raise ValueError('Unexpected RPUC redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 10_000_000:
                    raise ValueError('RPUC response exceeds size limit')
                chunks.append(chunk)
            content = b''.join(chunks)
            self.source_urls.append(response.url)
            if self.config.get('evidence_dir'):
                path = Path(self.config['evidence_dir']) / capture
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            return json.loads(content)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        self.source_urls = []
        inventory, seen, total, page = [], set(), None, 1
        while total is None or len(inventory) < total:
            payload = self._get('basica', {'municipi': '08261', 'idioma': 'ca',
                'firstRecord': page, 'rpp': 10, 'sortColumn': 'codi',
                'sortDirection': 'asc'}, f'inventory-page-{page}.json')
            count, rows = parse_page(payload)
            if total is not None and count != total:
                raise ValueError('RPUC total changed during pagination; retry snapshot')
            total = count
            if not rows and len(inventory) < total:
                raise ValueError('RPUC pagination ended before advertised total')
            for row in rows:
                if str(row['codi']) in seen:
                    raise ValueError('Repeated RPUC dossier across pages')
                seen.add(str(row['codi']))
                inventory.append(row)
            if len(inventory) > total:
                raise ValueError('RPUC returned more rows than advertised')
            page += 1
        projects = []
        for row in inventory:
            if is_local_instrument(row):
                detail = self._get('detall', {'codiExpedient': row['codi'],
                    'idioma': 'ca', 'cercaPublic': 'false'}, f"detail-{row['codi']}.json")
                projects.append(parse_project(row, detail))
        if not projects:
            raise ValueError('No Santa Susanna planning instruments found')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in projects), encoding='utf-8')
        return {'status': 'ok', 'rows': len(projects), 'inventory_rows': total,
                'excluded_rows': total - len(projects), 'pages': page - 1,
                'source_urls': self.source_urls, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
