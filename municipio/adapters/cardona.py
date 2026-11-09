"""Cardona planning instruments from the municipally linked public RPUC API."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import requests

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'https://planejamenturbanisme.territori.gencat.cat'
API = HOST + '/RPUC-portal/rest/consulta/'
INVENTORY = API + 'basica'
MUNICIPAL_SOURCE = 'https://www.cardona.cat/ajuntament/plans-i-campanyes-municipals/pla-dordenacio-urbanistica-poum.html'


def _date(value):
    # Only explicitly named date fields are passed here, never generic `data`.
    return date.fromisoformat(value).isoformat() if value else None


def parse_inventory(payload):
    if not isinstance(payload, dict) or payload.get('infoFiltre') != 'Cardona':
        raise ValueError('RPUC municipality filter is missing or changed')
    total, entries = payload.get('totals'), payload.get('llistat')
    if type(total) is not int or total < 0 or not isinstance(entries, list):
        raise ValueError('Invalid RPUC pagination schema')
    for row in entries:
        if not isinstance(row, dict) or not str(row.get('codi', '')).isdigit():
            raise ValueError('Invalid RPUC dossier identifier')
    return total, entries


def selected(row):
    return (row.get('municipi') == 'Cardona'
            and (row.get('instrumentca') or '').strip().startswith(('Pla ', 'Modificació ')))


def parse_project(entry, detail, tree):
    code = str(entry['codi'])
    if (not selected(entry) or str(detail.get('codintExp')) != code
            or detail.get('municipi') != 'Cardona'
            or detail.get('numComplet') != entry.get('nomComplet')
            or not detail.get('tema') or not detail.get('tipologiaCA')):
        raise ValueError('RPUC detail identity mismatch or incomplete instrument')
    documents = {}

    def walk(nodes, parents=()):
        if not isinstance(nodes, list):
            raise ValueError('Invalid RPUC document tree')
        for node in nodes:
            path = parents + (node['label'],)
            for doc in node.get('data') or []:
                ident = str(doc.get('idDocument', ''))
                if not ident.isdigit() or not doc.get('nomDocument'):
                    raise ValueError('Invalid RPUC document')
                item = documents.setdefault(ident, {
                    'id_documento': ident, 'titulo': doc['nomDocument'],
                    'url': API + 'documents?' + urlencode({
                        'documentId': ident, 'downloadType': 'inline', 'idioma': 'ca'}),
                    'categorias': [], 'source_metadata': doc,
                })
                if list(path) not in item['categorias']:
                    item['categorias'].append(list(path))
            walk(node.get('children') or [], path)

    walk(tree)
    if not documents:
        raise ValueError('Instrument has no source documents')
    return {
        'id': 'cardona-rpuc-' + code, 'rpuc_id': code,
        'municipio': 'Cardona', 'codigo_ine': '08047', 'provincia': 'Barcelona',
        'titulo': detail['tema'], 'tipo': detail['tipologiaCA'].strip(),
        'expediente': detail['numComplet'],
        'fase': 'vigente' if entry.get('vigencia') == 'SI' else None,
        'fecha': None, 'fecha_aprob': _date(detail.get('dataAprovacio')),
        'fecha_publicacion': _date(detail.get('dataPublicacio')),
        'url': HOST + '/rpucportal/#/consulta/detallExpedient/' + code,
        'url_fuente_municipal': MUNICIPAL_SOURCE,
        'source': 'ayuntamiento', 'origen': 'rpuc_enlazado_por_ayuntamiento',
        'source_urls': [INVENTORY, API + 'detall?' + urlencode({
            'codiExpedient': code, 'idioma': 'ca', 'cercaPublic': 'false'}),
            API + 'arbre?' + urlencode({
                'codiExpedient': code, 'idioma': 'ca', 'cercaPublic': 'false'})],
        'documentos': sorted(documents.values(), key=lambda d: int(d['id_documento'])),
        'source_metadata': {'inventory': entry,
                            'assentaments': detail.get('assentaments'),
                            'referenciaButlletins': detail.get('referenciaButlletins')},
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified instrument geometry extracted',
    }


class CardonaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='cardona', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.cardona.cat')

    def _fetch(self, endpoint, params):
        response = requests.get(API + endpoint, params=params, timeout=40,
                                headers={'User-Agent': 'municipio-cardona/1.0'})
        response.raise_for_status()
        payload = response.json()
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            suffix = params.get('codiExpedient', params.get('firstRecord', 0))
            (directory / f'{endpoint}-{suffix}.json').write_text(
                json.dumps({'url': response.url, 'payload': payload}, ensure_ascii=False, indent=2),
                encoding='utf-8')
        return payload

    def backfill_proyectos(self, out_jsonl):
        entries, seen, expected = [], set(), None
        page_number = 1
        # Despite its name, firstRecord is a one-based page number in this API.
        while expected is None or len(entries) < expected:
            total, page = parse_inventory(self._fetch('basica', {
                'municipi': '08047', 'idioma': 'ca', 'firstRecord': page_number,
                'rpp': 10, 'sortDirection': 'asc'}))
            if expected is not None and expected != total:
                raise ValueError('RPUC total changed during pagination; retry snapshot')
            expected = total
            if not page and len(entries) < total:
                raise ValueError('RPUC pagination ended before declared total')
            for entry in page:
                if str(entry['codi']) in seen:
                    raise ValueError('Repeated RPUC dossier across inventory pages')
                seen.add(str(entry['codi']))
                entries.append(entry)
            if len(entries) > total:
                raise ValueError('RPUC pagination exceeds declared total')
            page_number += 1
        rows = []
        for entry in entries:
            if selected(entry):
                params = {'codiExpedient': entry['codi'], 'idioma': 'ca', 'cercaPublic': 'false'}
                detail = self._fetch('detall', params)
                tree = self._fetch('arbre', params)
                rows.append(parse_project(entry, detail, tree))
        if not rows:
            raise ValueError('No usable Cardona planning instruments')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_records': expected,
                'excluded_records': expected - len(rows), 'source': INVENTORY,
                'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
