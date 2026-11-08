"""Cintruénigo's municipal planning inventory in the official Navarra SIUN."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import requests

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://administracionelectronica.navarra.es/SIUN_Consulta/'
INVENTORY = BASE + 'Index.html#/instrumentos'
MUNICIPAL_PAGE = 'https://www.cintruenigo.com/cintruenigo/urbanismo/'
FILTERS = {'municipios': [72], 'entidadesPoblacion': [],
           'tiposInstrumento': [], 'aprobadoPosterior': False}


def parse_instrument(data, expected_id):
    """One instrument, with all its documents and individually dated procedures."""
    if data['idInstrumento'] != expected_id:
        raise ValueError('Instrument identity changed')
    locations = data['instrumentosMunicipios']
    if not any(x['idProvincia'] == 31 and x['idMunicipio'] == 72
               and x['municipio']['denominacion'] == 'CINTRUÉNIGO' for x in locations):
        raise ValueError('Instrument does not belong to INE 31072')
    kind = data['tipoInstrumento']['denominacion']
    name = data['denominacion']
    if not kind or not name:
        raise ValueError('Missing instrument title or type')
    documents = {}
    for doc in data['instrumentosDocumentos']:
        link = doc.get('rutaFichero')
        if not link:
            continue
        if urlparse(link).scheme not in {'http', 'https'}:
            raise ValueError('Invalid source document URL')
        documents[doc['idDocumento']] = {
            'id_documento': doc['idDocumento'], 'titulo': doc['denominacion'],
            'url': link, 'tipo_documento_siun': doc['idTipoDocumento'],
            'escala_segun_siun': doc.get('escala'), 'procedencia': 'instrumentosDocumentos'}
    procedures = []
    for item in data['tramites']:
        # The public SIUN template labels fecha as Fecha BON, not agreement date.
        procedures.append({
            'id_tramite': item['idTramite'],
            'fase': (item.get('fase') or {}).get('denominacion'),
            'resolucion': (item.get('resolucion') or {}).get('denominacion'),
            'fecha_publicacion': item.get('fecha'),
            'fecha_resolucion': item.get('fechaResolucion'),
            'numero_bon': item.get('numBon'), 'numero_anuncio': item.get('numAnuncio'),
            'url_documento': item.get('rutaFichero'),
            'descripcion': item.get('descripcion'),
            'observaciones': (item.get('observaciones') or {}).get('denominacion')})
    return {
        'id': f'cintruenigo-siun-{expected_id}', 'municipio': 'Cintruénigo',
        'codigo_ine': '31072', 'provincia': 'Navarra',
        'id_instrumento_siun': expected_id,
        'numero_expediente_segun_siun': data.get('numExpediente'),
        'titulo': f'{kind}: {name}', 'tipo': kind,
        'descripcion': data.get('descripcion'),
        'url': BASE + f'Index.html#/instrumento/{expected_id}',
        'source_url': BASE + f'api/Instrumentos/{expected_id}',
        'inventory_url': INVENTORY, 'municipal_source_url': MUNICIPAL_PAGE,
        'source': 'ayuntamiento', 'organismo_fuente': 'Gobierno de Navarra — SIUN',
        'origen': 'inventario_oficial_planeamiento',
        'fecha_definitiva_segun_siun': data.get('fechaDefinitiva'),
        'fecha_registro_segun_siun': data.get('fechaRegistro'),
        'vigencia_segun_siun': data.get('vigencia'),
        'anulado': data.get('anulado'), 'extinguido': data.get('extinguido'),
        'documentos': list(documents.values()), 'tramites': procedures,
        'municipios_segun_siun': locations, 'geometry_status': 'unavailable',
        'publication_ready': False,
    }


def collect_inventory(fetch):
    """Follow SIUN's offset pagination and check its declared total."""
    rows, seen = [], set()
    offset, total = 0, None
    while total is None or offset < total:
        payload = fetch(f'api/Instrumentos/PG/default/false/{offset}/25', FILTERS)
        info, page = payload['pagedInfo'], payload['currentPage']
        count = info['totalElements']
        if not isinstance(count, int) or count < 0 or info['pageSize'] != 25:
            raise ValueError('Invalid pagination metadata')
        if total is not None and total != count:
            raise ValueError('Inventory changed during pagination; retry snapshot')
        total = count
        if not page and offset < total:
            raise ValueError('Premature empty inventory page')
        for item in page:
            key = item['idInstrumento']
            if key in seen:
                raise ValueError('Repeated instrument across inventory pages')
            seen.add(key)
            rows.append(item)
        offset += len(page)
        if offset > total:
            raise ValueError('Inventory exceeds declared total')
    if not rows:
        raise ValueError('Empty municipal inventory requires review')
    return rows


class CintruenigoAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, path, filters=None):
        url = BASE + path
        with requests.Session() as session:
            session.headers['User-Agent'] = 'MunicipalPlanningInventory/1.0'
            response = (session.get(url, timeout=40) if filters is None else
                        session.post(url, json=filters, timeout=40))
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(BASE).hostname:
            raise ValueError('Unexpected SIUN redirect')
        data = response.json()
        capture_dir = self.config.get('evidence_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (path.replace('/', '-') + '.json')).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        return data

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        inventory = collect_inventory(self._fetch)
        rows = [parse_instrument(self._fetch(f"api/Instrumentos/{x['idInstrumento']}"),
                                 x['idInstrumento']) for x in inventory]
        return {**self._write(out_jsonl, rows),
                'coverage': 'SIUN PG inventory filtered by municipality 72; all pages',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh: historical instrument documents can change in place.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
