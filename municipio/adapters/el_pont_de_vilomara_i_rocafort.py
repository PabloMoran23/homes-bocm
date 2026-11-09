"""Municipal RPUC instruments, from the register linked by municipal transparency."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import requests

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPIO = 'El Pont de Vilomara i Rocafort'
INE = '08182'
PORTAL = 'https://planejamenturbanisme.territori.gencat.cat'
API = PORTAL + '/RPUC-portal/rest/consulta/'
SOURCE = 'https://seu-e.cat/ca/web/elpontdevilomarairocafort/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic'


def source_date(value):
    if value is None or value == '':
        return None
    return date.fromisoformat(value).isoformat()


class ElPontDeVilomaraIRocafortAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.elpont.cat')
        self.source_urls = []

    def _get(self, endpoint, params):
        url = API + endpoint + '?' + urlencode(params)
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-08182/1.0'})
        response.raise_for_status()
        data = response.json()
        self.source_urls.append(url)
        if self.config.get('evidence_dir'):
            folder = Path(self.config['evidence_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            key = params.get('codiExpedient', params.get('firstRecord', 'snapshot'))
            (folder / f'rpuc-{endpoint}-{key}.json').write_text(response.text, encoding='utf-8')
        return data

    @staticmethod
    def parse_page(payload):
        total, items = payload.get('totals'), payload.get('llistat')
        if type(total) is not int or total < 1 or not isinstance(items, list):
            raise ValueError('RPUC inventory missing or invalid')
        if any(not isinstance(r, dict) or not str(r.get('codi', '')).isdigit() for r in items):
            raise ValueError('Invalid RPUC dossier identity')
        return total, items

    @staticmethod
    def parse_instrument(item, detail):
        identifier = str(item['codi'])
        if (item.get('municipi') != MUNICIPIO or detail.get('municipi') != MUNICIPIO
                or str(detail.get('codintExp')) != identifier
                or not detail.get('tema') or not detail.get('numComplet')):
            raise ValueError('RPUC detail identity or municipality mismatch')
        documents = {}
        for doc in detail.get('documents') or []:
            doc_id = str(doc.get('idDocument', ''))
            if not doc_id.isdigit() or not doc.get('nomDocument'):
                raise ValueError('Invalid RPUC document')
            documents[doc_id] = {
                'id': doc_id, 'titulo': doc['nomDocument'],
                'url': API + 'documents?' + urlencode({
                    'documentId': doc_id, 'downloadType': 'inline', 'idioma': 'ca'}),
            }
        if not documents:
            raise ValueError('RPUC instrument has no source documents')
        detail_url = API + 'detall?' + urlencode({
            'codiExpedient': identifier, 'idioma': 'ca', 'cercaPublic': 'false'})
        return {
            'id': 'el-pont-de-vilomara-i-rocafort-rpuc-' + identifier,
            'municipio': MUNICIPIO, 'codigo_ine': INE, 'provincia': 'Barcelona',
            'titulo': detail['tema'], 'tipo': detail.get('tipologiaCA') or item.get('instrumentca'),
            'fase': None, 'expediente': detail['numComplet'], 'rpuc_id': identifier,
            'fecha': None, 'fecha_publicacion': source_date(detail.get('dataPublicacio')),
            'fecha_aprob': source_date(detail.get('dataAprovacio')), 'fecha_acuerdo': None,
            'url': PORTAL + '/rpucportal/#/consulta/detallExpedient/' + identifier,
            'url_fuente': detail_url, 'inventario_url': SOURCE,
            'documentos': list(documents.values()),
            'source': 'ayuntamiento', 'origen': 'rpuc_planejament_municipal',
            'vigencia_rpuc': item.get('vigencia'), 'registrat_rpuc': item.get('registrat'),
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'No verified instrument geometry extracted',
        }

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        inventory, seen = [], set()
        page, expected, page_size = 1, None, 10
        while True:
            total, items = self.parse_page(self._get('basica', {
                'municipi': INE, 'idioma': 'ca', 'firstRecord': page, 'rpp': page_size,
                'sortColumn': 'data', 'sortDirection': 'asc',
            }))
            if expected is None:
                expected = total
            if total != expected or not items or len(items) > page_size:
                raise ValueError('RPUC pagination changed or incomplete')
            for item in items:
                if item['codi'] in seen:
                    raise ValueError('Repeated dossier during RPUC pagination')
                seen.add(item['codi'])
                inventory.append(item)
            if len(inventory) >= total:
                if len(inventory) != total:
                    raise ValueError('RPUC inventory count mismatch')
                break
            if len(items) != page_size:
                raise ValueError('RPUC prematurely short page')
            page += 1
        rows = []
        for item in inventory:
            # Associated regional plans can have a different lead municipality.
            # Do not relabel that municipality or imply full regional coverage.
            if item.get('municipi') != MUNICIPIO:
                continue
            detail = self._get('detall', {
                'codiExpedient': item['codi'], 'idioma': 'ca', 'cercaPublic': 'false'})
            rows.append(self.parse_instrument(item, detail))
        if not rows:
            raise ValueError('No municipal planning instruments in RPUC inventory')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_records': len(inventory),
                'excluded_other_lead_municipalities': len(inventory) - len(rows),
                'source_urls': [SOURCE, *self.source_urls], 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
