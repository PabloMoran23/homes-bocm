"""Mora's general-planning inventory, officially linked by the municipality.

The regional feature is a general plan, not a construction licence or a work.
Its ZIP bundles historical modifications too; these are not independent feature
records and are not promoted to separate projects from filenames alone.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL_SOURCE = 'https://www.mora.es/areas/OBRAS/Normativa/planeamiento'
VIEWER = 'https://mapasjccmold.maps.arcgis.com/apps/webappviewer/index.html?id=e97e8c22f2044b1187051687f8f64d88'
LAYER = 'https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/Planeamiento_Municipal/MapServer/0'
WHERE = "COD_INE = '45106' AND COD_PROV = '45'"


def source_date(value):
    """ArcGIS dates are UTC milliseconds; null is not the Unix epoch."""
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError('Unexpected ArcGIS date')
    return datetime.fromtimestamp(value / 1000, timezone.utc).date().isoformat()


def parse_inventory(payload):
    if 'error' in payload or payload.get('exceededTransferLimit'):
        raise ValueError('ArcGIS error or truncated feature batch')
    records = {}
    for feature in payload.get('features', []):
        a = feature['attributes']
        if (a.get('COD_INE'), a.get('COD_PROV'), a.get('MUNICIPIO')) != ('45106', '45', 'Mora'):
            raise ValueError('Feature does not identify Mora, Toledo, INE 45106')
        title = a.get('NOM_PLAN', '').strip()
        code = a.get('PLAN_', '').strip()
        if not title or not code or title.lower() == 'sin planeamiento':
            raise ValueError('No identified general planning instrument')
        document = a.get('DESCARGA') or ''
        parsed = urlparse(document)
        if (parsed.scheme != 'https' or parsed.hostname != 'ficheroscomunes.castillalamancha.es'
                or not parsed.path.startswith('/planeamiento/TOLEDO/45106_')
                or not parsed.path.lower().endswith('.zip')):
            raise ValueError('Missing or unexpected official Mora document package')
        key = 'mora-plan-' + code.lower()
        if key in records:
            raise ValueError('Ambiguous duplicate general-plan identifier')
        records[key] = {
            'id': key, 'municipio': 'Mora', 'codigo_ine': '45106', 'provincia': 'Toledo',
            'titulo': title + ' de Mora', 'tipo': 'planeamiento_urbanistico',
            'plan_codigo': code, 'url': VIEWER, 'inventory_url': LAYER,
            'municipal_source_url': MUNICIPAL_SOURCE,
            'source': 'castilla-la-mancha', 'origen': 'inventario_planeamiento_municipal',
            'id_origen': a['OBJECTID'], 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': source_date(a.get('FECHA_APRO')),
            'fecha_actualizacion_fuente': source_date(a.get('FECHA_ACTU')),
            'date_provenance': {'fecha_aprob': 'FECHA_APRO (ArcGIS esriFieldTypeDate)',
                                'fecha_actualizacion_fuente': 'FECHA_ACTU; not publication or agreement'},
            'documentos': [{'titulo': a.get('ZIP') or 'Paquete oficial de planeamiento',
                            'url': document, 'tipo': 'archivo_zip',
                            'alcance': 'Paquete municipal con NNSS y documentación de modificaciones; no un PDF individual'}],
            'source_attributes': a,
            'coverage': 'Ficha de planeamiento general; no inventario exhaustivo de modificaciones ni obras',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'Municipal coverage polygon is not an individual project geometry',
        }
    if not records:
        raise ValueError('Empty Mora planning inventory; review source')
    return list(records.values())


class MoraAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, params, capture):
        response = requests.get(LAYER + '/query', params={'f': 'json', **params}, timeout=45,
                                headers={'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'})
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(LAYER).hostname:
            raise ValueError('Unexpected inventory redirect')
        payload = response.json()
        if 'error' in payload:
            raise ValueError(f'ArcGIS query failed: {payload["error"]}')
        if self.config.get('evidence_dir'):
            root = Path(self.config['evidence_dir'])
            root.mkdir(parents=True, exist_ok=True)
            (root / capture).write_text(json.dumps({'url': response.url, 'payload': payload}, ensure_ascii=False, indent=2), encoding='utf-8')
        return payload

    def backfill_proyectos(self, out_jsonl):
        # returnIdsOnly is unbounded by maxRecordCount. Fetch every returned ID,
        # then check exact set equality, rather than trusting a single first page.
        listing = self._get({'where': WHERE, 'returnIdsOnly': 'true'}, 'live-ids.json')
        ids = listing.get('objectIds')
        if listing.get('exceededTransferLimit') or not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
            raise ValueError('Missing, truncated or duplicate inventory IDs')
        features = []
        for offset in range(0, len(ids), 100):
            batch = self._get({'where': WHERE, 'objectIds': ','.join(map(str, ids[offset:offset + 100])),
                               'outFields': '*', 'returnGeometry': 'false'}, f'live-features-{offset}.json')
            if batch.get('exceededTransferLimit') or 'features' not in batch:
                raise ValueError('Incomplete feature batch')
            features.extend(batch['features'])
        observed = [f['attributes']['OBJECTID'] for f in features]
        if len(observed) != len(ids) or set(observed) != set(ids):
            raise ValueError('Returned features do not match complete inventory ID set')
        rows = parse_inventory({'features': features})
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [MUNICIPAL_SOURCE, VIEWER, LAYER],
                'coverage': 'general_planning_inventory', 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled',
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
