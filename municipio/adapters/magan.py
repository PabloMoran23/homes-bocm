"""Magán's general planning inventory in the official JCCM deposit."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from municipio.adapters.portal import AyuntamientoAdapter

LAYER = 'https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/Planeamiento_Municipal/MapServer/0'
ARCHIVE = 'https://ficheroscomunes.castillalamancha.es/planeamiento/TOLEDO/45088_MAGAN.zip'
QUERY = {'where': "COD_INE='45088'", 'f': 'json'}
LIMITATIONS = [
    'Partial coverage: regional general-planning deposit only; not a complete municipal project or licence register.',
    'Deposit is informational and may omit municipal amendments or documents not remitted to JCCM.',
    'Archive amendments are retained with the parent NNSS; their individual approval dates and current legal status are not inferred.',
    'FECHA_APRO is the catalogue approval date; FECHA_ACTU is a catalogue update, not publication or agreement.',
    'No verified instrument geometry; municipal inventory polygons are not substituted for project geometry.',
]


def _date(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Invalid ArcGIS date')
    return datetime.fromtimestamp(value / 1000, timezone.utc).date().isoformat()


class MaganAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='magan', config=None, base_url=''):
        super().__init__(slug, config, base_url or LAYER)

    @staticmethod
    def parse_inventory(payload: dict[str, Any], count: int) -> list[dict[str, Any]]:
        if 'error' in payload or payload.get('exceededTransferLimit'):
            raise ValueError('ArcGIS error or truncated inventory')
        features = payload.get('features')
        if not isinstance(features, list) or len(features) != count or count != 1:
            raise ValueError('Expected exactly one complete Magán general-plan inventory entry; review changed inventory')
        a = features[0]['attributes']
        if (a.get('COD_INE'), a.get('COD_PROV'), a.get('MUNICIPIO')) != ('45088', '45', 'Magán'):
            raise ValueError('Wrong municipality/province')
        if (a.get('PLAN_'), a.get('NOM_PLAN'), a.get('DISPONIBLE'), a.get('DESCARGA')) != (
                'NNSS-B', 'Normas Subsidiarias tipo b', 'SI', ARCHIVE):
            raise ValueError('General plan or document location changed; review source')
        return [{
            'id': 'magan-proy-45088-nnss-b', 'municipio': 'Magán',
            'codigo_ine': '45088', 'provincia': 'Toledo',
            'titulo': 'Normas Subsidiarias tipo b de Magán',
            'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': _date(a.get('FECHA_APRO')),
            'fecha_actualizacion_catalogo': _date(a.get('FECHA_ACTU')),
            'url': LAYER + '/query?' + requests.compat.urlencode({**QUERY, 'outFields': '*', 'returnGeometry': 'false'}),
            'url_documento': ARCHIVE,
            'source': 'jccm', 'origen': 'deposito_regional_planeamiento_municipal',
            'descripcion': 'Instrumento general del catálogo JCCM. Archivo conjunto de normativa, memoria, planos y modificaciones; no implica aprobación nueva de sus documentos.',
            'source_attributes': a,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'No verified instrument geometry extracted',
            'limitations': LIMITATIONS,
        }]

    @staticmethod
    def parse_archive(content: bytes) -> list[dict[str, str]]:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            if not members or any(not m.filename.startswith('45088_MAGAN/') or
                                  '..' in m.filename.split('/') or
                                  not m.filename.lower().endswith('.pdf') for m in members):
                raise ValueError('Unexpected planning archive contents')
            if len({m.filename for m in members}) != len(members):
                raise ValueError('Duplicate archive members')
            # Paths are archive member names, not invented individually downloadable URLs.
            return [{'titulo': m.filename.rsplit('/', 1)[-1], 'url': ARCHIVE,
                     'archivo_interno': m.filename, 'contenedor': 'zip'} for m in members]

    def _fetch(self, url, params=None, limit=2_000_000):
        with requests.get(url, params=params, stream=True, timeout=(15, 60),
                          headers={'User-Agent': self.config.get('user_agent', 'municipio-magan/1.0')}) as response:
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > limit:
                    raise ValueError('Source exceeds response limit; no partial output accepted')
            body = bytes(content)
            capture_dir = self.config.get('capture_dir')
            if capture_dir:
                path = Path(capture_dir)
                path.mkdir(parents=True, exist_ok=True)
                name = ('archive.zip' if url == ARCHIVE else
                        'count.json' if params and params.get('returnCountOnly') else 'inventory.json')
                (path / name).write_bytes(body)
            return body

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        count = json.loads(self._fetch(LAYER + '/query', {**QUERY, 'returnCountOnly': 'true'}))
        if 'error' in count or type(count.get('count')) is not int:
            raise ValueError('ArcGIS count unavailable')
        payload = json.loads(self._fetch(LAYER + '/query', {**QUERY, 'outFields': '*', 'returnGeometry': 'false'}))
        rows = self.parse_inventory(payload, count['count'])
        content = self._fetch(ARCHIVE, limit=80_000_000)
        rows[0]['documentos'] = self.parse_archive(content)
        rows[0]['archivo_sha256'] = hashlib.sha256(content).hexdigest()
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [rows[0]['url'], ARCHIVE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
