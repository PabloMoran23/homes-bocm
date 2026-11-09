"""Municipal planning instruments from the municipality-linked public RPUC API."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://planejamenturbanisme.territori.gencat.cat'
API = BASE + '/RPUC-portal/rest/consulta/'
SOURCE = 'https://www.seu-e.cat/ca/web/macanetdelaselva/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic'
MUNICIPIO = 'Maçanet de la Selva'
PAGE_SIZE = 20


def _date(value):
    # Only explicitly named detail dates; the inventory's generic data is unused.
    if value is None or value == '':
        return None
    return date.fromisoformat(value).isoformat()


class MacanetDeLaSelvaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.massanetdelaselva.cat')
        self.source_urls = []

    def _get(self, endpoint, params):
        url = API + endpoint + '?' + urlencode(params)
        response = requests.get(url, timeout=40, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-macanet-de-la-selva/1.0')
        })
        response.raise_for_status()
        if len(response.content) > 10_000_000:
            raise ValueError('RPUC response exceeds reviewed size')
        payload = response.json()
        self.source_urls.append(response.url)
        if self.config.get('evidence_dir'):
            folder = Path(self.config['evidence_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            key = params.get('codiExpedient', params.get('firstRecord'))
            (folder / f'rpuc-{endpoint}-{key}.json').write_text(response.text, encoding='utf-8')
        return payload

    def inventory(self):
        rows, seen, total = [], set(), None
        # firstRecord is a ONE-BASED PAGE number, despite its name (as in the UI).
        for page in range(1, 501):
            payload = self._get('basica', {'municipi': '17103', 'idioma': 'ca',
                                         'firstRecord': page, 'rpp': PAGE_SIZE})
            count, batch = payload.get('totals'), payload.get('llistat')
            if type(count) is not int or count < 1 or not isinstance(batch, list):
                raise ValueError('Invalid/empty RPUC inventory')
            if MUNICIPIO not in payload.get('infoFiltre', ''):
                raise ValueError('RPUC municipality filter not confirmed')
            if total is None:
                total = count
            if count != total or not batch or len(batch) > PAGE_SIZE:
                raise ValueError('RPUC inventory changed or pagination is incomplete')
            for item in batch:
                code = item.get('codi')
                if not isinstance(code, str) or not code.isdigit() or code in seen:
                    raise ValueError('Invalid or repeated RPUC dossier across pages')
                seen.add(code)
                rows.append(item)
            if len(rows) == total:
                return rows
            if len(rows) > total or len(batch) < PAGE_SIZE:
                raise ValueError('RPUC total does not match page contents')
        raise ValueError('RPUC pagination exceeds reviewed limit; no partial output')

    @staticmethod
    def parse_project(item: dict[str, Any], detail: dict[str, Any]):
        code = item['codi']
        if (item.get('municipi') != MUNICIPIO or detail.get('municipi') != MUNICIPIO
                or str(detail.get('codintExp')) != code):
            raise ValueError('RPUC detail identity/municipality mismatch')
        title, kind = detail.get('tema'), detail.get('tipologiaCA')
        if not title or not kind or detail.get('codiRang') not in {'PG', 'PD', 'TUC'}:
            raise ValueError('Unrecognized local planning instrument')
        documents = {}
        if not isinstance(detail.get('documents'), list):
            raise ValueError('Missing RPUC document inventory')
        for doc in detail['documents']:
            doc_id = doc.get('idDocument')
            if type(doc_id) is not int or doc_id <= 0 or not doc.get('nomDocument'):
                raise ValueError('Invalid RPUC source document')
            documents[doc_id] = {
                'id_documento': str(doc_id), 'titulo': doc['nomDocument'],
                'url': API + 'documents?' + urlencode({
                    'documentId': doc_id, 'downloadType': 'attachment', 'idioma': 'ca'}),
                'provenance': 'RPUC detail.documents',
                'estado_fuente': {key: doc.get(key) for key in ('afectat', 'baixa', 'recurs')},
            }
        url = BASE + '/rpucportal/#/consulta/detallExpedient/' + code
        return {
            'id': 'macanet-de-la-selva-rpuc-' + code,
            'municipio': MUNICIPIO, 'provincia': 'Girona', 'codigo_ine': '17103',
            'titulo': title.strip(), 'tipo': kind.strip(), 'fase': None,
            'expediente': detail.get('numComplet'), 'rpuc_id': code,
            'fecha': None, 'fecha_aprob': _date(detail.get('dataAprovacio')),
            'fecha_acuerdo': None, 'fecha_publicacion': _date(detail.get('dataPublicacio')),
            'url': url, 'url_fuente_municipal': SOURCE,
            'url_detalle_api': API + 'detall?' + urlencode({
                'codiExpedient': code, 'idioma': 'ca', 'cercaPublic': 'false'}),
            'source': 'ayuntamiento', 'origen': 'rpuc_enlazado_por_sede_municipal',
            'vigencia_fuente': item.get('vigencia'),
            'documentos': list(documents.values()),
            'asientos_registro': detail.get('assentaments') or [],
            'referencias_boletines': detail.get('referenciaButlletins') or [],
            'expedientes_relacionados': [
                {'rpuc_id': str(other['codintExp']), 'titulo': other.get('tema'),
                 'relacion': other.get('tipusRelacio'),
                 'url': BASE + '/rpucportal/#/consulta/detallExpedient/' + str(other['codintExp'])}
                for other in detail.get('expedientsRelacionats') or []
                if other.get('codintExp') is not None
            ],
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'limitations': 'Planning inventory snapshot, not licences or all public works. '
                            'Document status may be unspecified; PDFs are linked, not parsed. '
                            'No verified project geometry. No approval phase inferred.',
        }

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = []
        inventory = self.inventory()
        rows = []
        excluded = []
        excluded_agreements = []
        for item in inventory:
            # The municipal search also returns regional plans headed by other municipalities.
            if item.get('municipi') != MUNICIPIO:
                excluded.append({'rpuc_id': item['codi'], 'municipio': item.get('municipi'),
                                 'titulo': item.get('tema')})
                continue
            detail = self._get('detall', {'codiExpedient': item['codi'],
                                         'idioma': 'ca', 'cercaPublic': 'false'})
            if detail.get('codiRang') == 'CNV':
                excluded_agreements.append({'rpuc_id': item['codi'], 'titulo': detail.get('tema'),
                                            'reason': 'Urban-planning agreement, not a planning instrument'})
                continue
            rows.append(self.parse_project(item, detail))
        if not rows:
            raise ValueError('No usable local planning instruments')
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temp = out_jsonl.with_suffix('.jsonl.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'inventory_records': len(inventory),
                'excluded_regional': excluded, 'excluded_agreements': excluded_agreements,
                'source_urls': self.source_urls,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Complete refreshed snapshot; no incremental cutoff or invented agreement date.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        raise NotImplementedError('Licences disabled: no verified granted-licence inventory')

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
