"""Montblanc municipal planning in the official RPUC linked by its transparency seat."""
from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import requests

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'https://planejamenturbanisme.territori.gencat.cat'
API = HOST + '/RPUC-portal/rest/consulta/'
SEAT = 'https://seu-e.cat/ca/web/montblanc/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic'
LIMITATIONS = [
    'Partial coverage: municipal general and derived planning registered in RPUC; not all works or pending instruments.',
    'Supramunicipal instruments, agreements and TUC delimitations excluded; no granted licence register.',
    'Document links and register metadata retained; PDF contents and vector geometry not extracted.',
    'No verified coordinates; publication_ready is false. Updates replace the complete snapshot.',
]


def source_date(value):
    if value is None or value == '':
        return None
    # These detail fields are explicit calendar dates, never the inventory data field.
    return date.fromisoformat(value).isoformat()


def parse_documents(tree):
    if not isinstance(tree, list):
        raise ValueError('Unexpected RPUC document tree')
    docs = {}

    def walk(nodes, trail):
        for node in nodes:
            path = trail + [html.unescape(node['label'])]
            for doc in node.get('data') or []:
                ident = str(doc['idDocument'])
                if not ident.isdigit() or not doc.get('nomDocument'):
                    raise ValueError('Invalid RPUC document identity')
                entry = docs.setdefault(ident, {
                    'id': ident, 'titulo': html.unescape(doc['nomDocument']),
                    'url': API + 'documents?' + urlencode({'documentId': ident, 'downloadType': 'inline', 'idioma': 'ca'}),
                    'origen': 'RPUC', 'categorias': [],
                    'source_metadata': {k: doc.get(k) for k in ('portal', 'afectat', 'baixa', 'recurs')},
                })
                if path not in entry['categorias']:
                    entry['categorias'].append(path)
            walk(node.get('children') or [], path)
    walk(tree, [])
    return list(docs.values())


def parse_project(item, detail, tree):
    ident = str(item['codi'])
    if str(detail.get('codintExp')) != ident or detail.get('municipi') != 'Montblanc':
        raise ValueError('RPUC detail identity/municipality mismatch')
    # Do not turn agreements, appeals or other administrative entries into plans.
    if detail.get('codiRang') not in {'PG', 'PD'}:
        return None
    if not detail.get('tema') or not detail.get('tipologiaCA'):
        raise ValueError('Missing planning description')
    docs = parse_documents(tree)
    if not docs:
        raise ValueError('Planning instrument without source documents')
    return {
        'id': 'montblanc-rpuc-' + ident, 'rpuc_id': ident,
        'municipio': 'Montblanc', 'codigo_ine': '43086', 'provincia': 'Tarragona',
        'titulo': html.unescape(detail['tema']).strip(),
        'tipo': detail['tipologiaCA'].strip(), 'fase': None,
        'categoria': 'planeamiento urbanístico',
        'expediente': detail.get('numComplet'),
        'fecha': None, 'fecha_aprob': source_date(detail.get('dataAprovacio')),
        'fecha_publicacion': source_date(detail.get('dataPublicacio')),
        'url': HOST + '/rpucportal/#/consulta/detallExpedient/' + ident,
        'source': 'ayuntamiento', 'origen': 'rpuc_planeamiento_municipal',
        'source_urls': [SEAT, API + 'detall?' + urlencode({'codiExpedient': ident, 'idioma': 'ca', 'cercaPublic': 'false'})],
        'documentos': docs,
        'source_metadata': {
            'rang': detail.get('rang'), 'codiRang': detail['codiRang'],
            'vigencia': item.get('vigencia'), 'registrat': item.get('registrat'),
            'competencia': detail.get('competenciaCA'),
            'referenciaButlletins': detail.get('referenciaButlletins'),
            'assentaments': detail.get('assentaments'),
        },
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified geometry extracted from RPUC documents',
    }


class MontblancAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.montblanc.cat')
        self.source_urls = []

    def _get(self, session, endpoint, params, capture_name):
        response = session.get(API + endpoint, params=params, timeout=40)
        response.raise_for_status()
        self.source_urls.append(response.url)
        data = response.json()  # HTML/login/error responses fail closed.
        if self.config.get('capture_dir'):
            target = Path(self.config['capture_dir']) / capture_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(response.text, encoding='utf-8')
        return data

    def _inventory(self, session):
        items, seen, total, page = [], set(), None, 1
        while True:
            payload = self._get(session, 'basica', {
                'municipi': '43086', 'idioma': 'ca', 'firstRecord': page,
                'rpp': 20, 'sortColumn': 'tema', 'sortDirection': 'asc',
            }, f'inventory-{page}.json')
            expected, batch = payload['totals'], payload['llistat']
            if type(expected) is not int or expected <= 0 or not isinstance(batch, list):
                raise ValueError('Invalid or empty RPUC inventory')
            if total is not None and expected != total:
                raise ValueError('Inventory changed during pagination; retry full snapshot')
            total = expected
            if not batch:
                raise ValueError('Pagination ended before advertised total')
            for item in batch:
                ident = str(item['codi'])
                if not ident.isdigit() or ident in seen:
                    raise ValueError('Invalid/duplicate RPUC identity or repeated page')
                seen.add(ident)
                items.append(item)
            if len(items) > total:
                raise ValueError('RPUC total exceeded')
            if len(items) == total:
                return items
            page += 1

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        rows = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-montblanc/1.0'
            items = self._inventory(session)
            for item in items:
                if item.get('municipi') != 'Montblanc':
                    continue
                ident = str(item['codi'])
                params = {'codiExpedient': ident, 'idioma': 'ca', 'cercaPublic': 'false'}
                detail = self._get(session, 'detall', params, f'detail-{ident}.json')
                if str(detail.get('codintExp')) != ident or detail.get('municipi') != 'Montblanc':
                    raise ValueError('RPUC detail identity/municipality mismatch')
                if detail.get('codiRang') not in {'PG', 'PD'}:
                    continue
                tree = self._get(session, 'arbre', params, f'documents-{ident}.json')
                rows.append(parse_project(item, detail, tree))
        if not rows:
            raise ValueError('No usable Montblanc planning instruments')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_records': len(items),
                'source_urls': self.source_urls, 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
