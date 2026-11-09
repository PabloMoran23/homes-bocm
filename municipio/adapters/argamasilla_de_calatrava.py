"""Municipal planning inventory from the official JCCM SIU public map service.

One instrument per municipal inventory entry, never one project per land-use zone.
The municipal website currently serves a verification page to direct HTTP clients.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import requests

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/SIU_municipios/MapServer/0'
INVENTORY = 'https://urbanismo.castillalamancha.es/planeamiento/sistema-de-informacion-urbana'
VIEWER = 'https://castillalamancha.maps.arcgis.com/apps/webappviewer/index.html?id=8089ffeebd184d19b8b329daee501626'
WHERE = "COD_INE = '13020'"


def parse_inventory(payload: dict) -> list[dict]:
    if payload.get('error') or payload.get('exceededTransferLimit'):
        raise ValueError('SIU error or truncated inventory response')
    features = payload.get('features')
    if not isinstance(features, list) or not features:
        raise ValueError('No municipal planning inventory entries')
    rows = {}
    for feature in features:
        a = feature['attributes']
        if (a.get('COD_INE'), a.get('COD_PROV'), a.get('PROVINCIA'), a.get('MUNICIPIO')) != (
            '13020', '13', 'CIUDAD REAL', 'Argamasilla de Calatrava'
        ):
            raise ValueError('Unexpected municipality/province in SIU response')
        # Unknown planning types require review, rather than inventing a title.
        if (a.get('PLAN_'), a.get('NOM_PLAN')) != ('NNSS', 'Normas Subsidiarias_b'):
            raise ValueError('Municipal planning instrument changed; review SIU inventory')
        document = str(a.get('DESCARGA') or '')
        parsed = urlparse(document)
        if (parsed.scheme != 'https' or parsed.hostname != 'ficheroscomunes.castillalamancha.es'
                or parsed.path != '/planeamiento/SIU/13020_ARGAMASILLA_DE_CALATRAVA.zip'
                or parsed.query or parsed.fragment):
            raise ValueError('Missing or unexpected municipal SIU package')
        # The package identifies the instrument, not the transient map OBJECTID.
        key = 'argamasilla-de-calatrava-plan-' + hashlib.sha256(document.encode()).hexdigest()[:16]
        if key in rows and rows[key]['source_attributes'] != a:
            raise ValueError('Conflicting inventory entries for the same instrument')
        rows[key] = {
            'id': key, 'municipio': 'Argamasilla de Calatrava', 'codigo_ine': '13020',
            'provincia': 'Ciudad Real',
            'titulo': 'Normas Subsidiarias tipo b de Argamasilla de Calatrava',
            'tipo': 'planeamiento_urbanistico',
            'url': SOURCE + '/query?f=json&where=COD_INE%20%3D%20%2713020%27&outFields=*&returnGeometry=false',
            'inventory_url': INVENTORY, 'visor_url': VIEWER,
            'source': 'jccm-siu', 'origen': 'inventario_autonomico_planeamiento_municipal',
            'source_attributes': a,
            'documentos': [{'titulo': 'Paquete cartográfico SIU municipal (ZIP)',
                            'url': document, 'tipo': 'cartografia_refundida',
                            'source_field': 'DESCARGA'}],
            'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'coverage': 'partial_current_siu_inventory',
            'descripcion': 'Instrumento identificado por el inventario SIU de la Junta de Comunidades '
                           'de Castilla-La Mancha. Cartografía informativa; no acredita vigencia '
                           'jurídica actual, aprobación, licencia ni ejecución de obras.',
        }
    return list(rows.values())


class ArgamasillaDeCalatravaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, session, params):
        response = session.get(SOURCE + '/query', params=params, timeout=30)
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(SOURCE).hostname:
            raise ValueError('Unexpected SIU redirect')
        payload = response.json()
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(response.url.encode()).hexdigest()[:16]
            (directory / ('siu-' + name + '.json')).write_text(json.dumps({
                'url': response.url, 'status': response.status_code, 'payload': payload
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if not isinstance(payload, dict) or payload.get('error') or payload.get('exceededTransferLimit'):
            raise ValueError('SIU error or truncated response')
        return payload

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'municipio-argamasilla-de-calatrava/1.0'})
            # ArcGIS returnIdsOnly is not subject to the feature transfer limit.
            # Fetch every returned ID in batches and verify exact completeness.
            index = self._get(session, {'f': 'json', 'where': WHERE, 'returnIdsOnly': 'true'})
            ids = index.get('objectIds')
            if not isinstance(ids, list) or not ids or any(type(i) is not int for i in ids):
                raise ValueError('Empty or invalid SIU object ID inventory')
            if len(set(ids)) != len(ids) or index.get('objectIdFieldName') != 'OBJECTID':
                raise ValueError('Invalid SIU object ID inventory')
            features = []
            for start in range(0, len(ids), 100):
                batch = ids[start:start + 100]
                payload = self._get(session, {'f': 'json', 'where': WHERE,
                    'objectIds': ','.join(map(str, batch)), 'outFields': '*', 'returnGeometry': 'false'})
                found = payload.get('features', [])
                found_ids = [f['attributes']['OBJECTID'] for f in found]
                if len(found_ids) != len(batch) or set(found_ids) != set(batch):
                    raise ValueError('Incomplete SIU feature batch; output not replaced')
                features.extend(found)
        rows = parse_inventory({'features': features})
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'coverage': 'partial_current_siu_inventory', 'publication_ready': False,
                'source_urls': [INVENTORY, VIEWER, SOURCE]}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full current snapshot; state is deliberately not a historical cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'count': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
