"""Municipal general planning from the official Castilla-La Mancha inventory."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from municipio.adapters.portal import AyuntamientoAdapter

LAYER = 'https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/Planeamiento_Municipal/MapServer/0'
SOURCE = 'https://urbanismo.castillalamancha.es/planeamiento-municipal-cloned'
WHERE = "COD_INE = '13096'"
LIMITATIONS = [
    'Only general planning in the regional inventory; no exhaustive works, derived plans or licence coverage.',
    'Regional documentation is informative and does not replace legally authenticated administrative files.',
    'FECHA_APRO is the inventory approval date; approval stage and publication/agreement dates are not supplied.',
    'No project geometry: the service polygon represents the municipal area, not a verified plan boundary.',
    'ZIP document bundle retained as one instrument; its internal documents are not separate projects.',
]


def inventory_date(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Invalid ArcGIS date')
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()


def parse_features(payload):
    if payload.get('error') or payload.get('exceededTransferLimit'):
        raise ValueError('ArcGIS error or truncated response')
    if not isinstance(payload.get('features'), list):
        raise ValueError('Missing ArcGIS features')
    records = {}
    for feature in payload['features']:
        a = feature['attributes']
        if (a.get('COD_INE'), a.get('COD_PROV'), a.get('MUNICIPIO')) != (
            '13096', '13', 'Villarrubia de los Ojos'
        ):
            raise ValueError('Unexpected municipality/province')
        if a.get('PLAN_') not in {'POM', 'PGOU', 'PDSU', 'NNSS-A', 'NNSS-B', 'DSU'} or not a.get('NOM_PLAN'):
            raise ValueError('Unsupported or missing planning instrument')
        archive = a.get('DESCARGA') or ''
        parsed = urlparse(archive)
        if (a.get('DISPONIBLE') != 'SI' or parsed.scheme != 'https'
                or parsed.hostname != 'ficheroscomunes.castillalamancha.es'
                or not parsed.path.startswith('/planeamiento/CIUDAD_REAL/13096_')
                or not parsed.path.lower().endswith('.zip')):
            raise ValueError('Missing verified municipal planning bundle')
        record = {
            'id': 'villarrubia-de-los-ojos-plan-' + hashlib.sha256(archive.encode()).hexdigest()[:16],
            'municipio': 'Villarrubia de los Ojos', 'codigo_ine': '13096',
            'provincia': 'Ciudad Real', 'titulo': a['NOM_PLAN'] + ' de Villarrubia de los Ojos',
            'tipo': a['PLAN_'], 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': inventory_date(a.get('FECHA_APRO')),
            'fase': None, 'url': SOURCE, 'url_documento': archive,
            'source': 'administracion_autonomica', 'origen': 'inventario_planeamiento_municipal_jccm',
            'documentos': [{'titulo': a.get('ZIP') or parsed.path.rsplit('/', 1)[-1],
                            'url': archive, 'tipo': 'archivo_zip_planeamiento', 'source_url': LAYER}],
            'source_url': LAYER,
            'source_attributes': {k: a.get(k) for k in (
                'COD_INE', 'COD_PROV', 'MUNICIPIO', 'PLAN_', 'NOM_PLAN', 'FECHA_APRO',
                'FECHA_ACTU', 'ZIP', 'DISPONIBLE', 'DESCARGA', 'OBSERVAC')},
            'fecha_actualizacion_inventario': inventory_date(a.get('FECHA_ACTU')),
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'unavailable: municipal polygon is not project geometry',
            'cobertura': 'parcial: planeamiento general del inventario autonómico',
            'limitations': LIMITATIONS,
        }
        if archive in records and records[archive] != record:
            raise ValueError('Conflicting documents for the same instrument')
        records[archive] = record
    if not records:
        raise ValueError('No usable planning instruments for INE 13096')
    return list(records.values())


class VillarrubiaDeLosOjosAyuntamientoAdapter(AyuntamientoAdapter):
    def _capture(self, name, content):
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_bytes(content)

    def _query(self, session, params, capture):
        response = session.get(LAYER + '/query', params={'f': 'json', **params}, timeout=40)
        response.raise_for_status()
        self._capture(capture, response.content)
        payload = response.json()
        if payload.get('error') or payload.get('exceededTransferLimit'):
            raise ValueError('ArcGIS query failed or truncated')
        return payload

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-villarrubia-de-los-ojos/1.0'
            listing = self._query(session, {'where': WHERE, 'returnIdsOnly': 'true'}, 'live-ids.json')
            ids = listing.get('objectIds')
            if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
                raise ValueError('Missing or duplicate inventory IDs')
            oid_field = listing.get('objectIdFieldName')
            if not oid_field:
                raise ValueError('Missing object ID field')
            features = []
            # Enumerating IDs first avoids default ArcGIS record limits. Every ID
            # must be retrieved, even if the source grows beyond one response.
            for offset in range(0, len(ids), 100):
                batch = ids[offset:offset + 100]
                data = self._query(session, {
                    'where': WHERE, 'objectIds': ','.join(str(i) for i in batch),
                    'outFields': '*', 'returnGeometry': 'false',
                }, f'live-features-{offset // 100}.json')
                found = data.get('features', [])
                actual = [f['attributes'][oid_field] for f in found]
                if len(actual) != len(batch) or set(actual) != set(batch):
                    raise ValueError('Incomplete or duplicate inventory batch')
                features.extend(found)
            rows = parse_features({'features': features})
            for index, row in enumerate(rows):
                # Verify the linked document is actually a ZIP without downloading
                # the entire (potentially hundreds of MB) planning bundle.
                with session.get(row['url_documento'], headers={'Range': 'bytes=0-3'},
                                 stream=True, timeout=40) as response:
                    response.raise_for_status()
                    signature = next(response.iter_content(4), b'')
                    if signature != b'PK\x03\x04':
                        raise ValueError('Planning download is not a ZIP document')
                    self._capture(f'live-archive-{index}-signature.bin', signature)
        result = self._write(out_jsonl, rows)
        return {**result, 'inventory_features': len(features), 'source_urls': [SOURCE, LAYER] +
                [r['url_documento'] for r in rows], 'limitations': LIMITATIONS}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
