"""Malagón planning inventory published by the regional planning authority.

Reads the public viewer's municipality inventory and the linked ZIP directory;
archive members are document provenance, not individually downloadable URLs.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlencode, urlparse

import requests

from municipio.adapters.portal import AyuntamientoAdapter

LAYER = 'https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/Planeamiento_Municipal/MapServer/0'
QUERY = LAYER + '/query'
WHERE = "COD_INE = '13052'"
SOURCE = QUERY + '?' + urlencode({'f': 'json', 'where': WHERE, 'outFields': '*', 'returnGeometry': 'false'})
LIMITATIONS = [
    'Cobertura parcial del depósito autonómico de planeamiento; puede faltar documentación municipal no remitida o no refundida.',
    'El listado ZIP acredita documentos publicados, no la vigencia actual de cada instrumento. No se interpreta el contenido de los documentos.',
    'Las fechas de carpetas de modificaciones se conservan como metadatos sin atribuirles significado de aprobación o publicación.',
    'Sin licencias concedidas, obras municipales ni geometrías verificadas; publication_ready=false.',
]


def parse_archive_directory(data: bytes, start: int, total: int) -> list[str]:
    """Require a complete ordinary ZIP central directory in a verified suffix."""
    end = data.rfind(b'PK\x05\x06')
    if end < 0 or len(data) < end + 22:
        raise ValueError('Missing ZIP end record')
    _, disk, cd_disk, disk_count, count, size, offset, comment = struct.unpack_from('<4s4H2LH', data, end)
    if (disk or cd_disk or disk_count != count or count == 65535
            or offset < start or offset + size != start + end
            or end + 22 + comment != len(data) or start + len(data) != total):
        raise ValueError('Incomplete, multipart or unsupported ZIP directory')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
    if len(members) != count:
        raise ValueError('ZIP entry count mismatch')
    names = []
    for member in members:
        path = PurePosixPath(member.filename)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unexpected archive member path')
        if any(p.startswith('.') for p in path.parts) or member.is_dir():
            continue
        if path.suffix.lower() in {'.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff'}:
            names.append(member.filename)
    if not names or len(names) != len(set(names)):
        raise ValueError('Empty or duplicate archive documents')
    return sorted(names)


def validate_attributes(attributes: dict) -> str:
    if (attributes.get('COD_INE') != '13052' or attributes.get('COD_PROV') != '13'
            or attributes.get('MUNICIPIO') != 'Malagón'):
        raise ValueError('Wrong municipality/province in planning inventory')
    archive_url = attributes.get('DESCARGA', '')
    parsed = urlparse(archive_url)
    if (parsed.scheme != 'https' or parsed.hostname != 'ficheroscomunes.castillalamancha.es'
            or not parsed.path.startswith('/planeamiento/CIUDAD_REAL/13052_MALAGON')
            or not parsed.path.endswith('.zip')):
        raise ValueError('Unexpected planning archive URL')
    if not attributes.get('NOM_PLAN') or not attributes.get('PLAN_'):
        raise ValueError('Missing planning instrument name')
    return archive_url


def parse_projects(attributes: dict, names: list[str]) -> list[dict]:
    archive_url = validate_attributes(attributes)
    groups = {}
    for name in names:
        parts = PurePosixPath(name).parts
        if len(parts) < 4 or parts[0] != '13052_MALAGON' or not parts[1].startswith('NNSS_'):
            raise ValueError('Unrecognized planning archive layout')
        key = parts[1]
        if parts[2] == '3_Modificaciones Puntuales':
            if len(parts) < 5 or not re.match(r'^\d{4}-\d{2}-\d{2} MP-\d+ ', parts[3]):
                raise ValueError('Unrecognized modification folder')
            key = parts[3]
        elif parts[2] not in {'1_Normativa', '2_Planos', 'Acuerdos'}:
            raise ValueError('Unrecognized instrument document group')
        groups.setdefault(key, []).append({'titulo': parts[-1], 'url': archive_url, 'archivo': name})
    if not groups or not any(k.startswith('NNSS_') for k in groups):
        raise ValueError('Missing base plan documents')
    rows = []
    for key, docs in sorted(groups.items()):
        base = key.startswith('NNSS_')
        approved = attributes.get('FECHA_APRO') if base else None
        approval = datetime.fromtimestamp(approved / 1000, timezone.utc).date().isoformat() if approved is not None else None
        rows.append({
            'id': 'malagon-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Malagón', 'provincia': 'Ciudad Real', 'codigo_ine': '13052',
            'titulo': (attributes['NOM_PLAN'] + ' de Malagón') if base else key[11:] + ' — Malagón',
            'tipo': 'planeamiento_urbanistico' if base else 'modificacion_planeamiento',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': approval, 'fase': None,
            'fecha_carpeta_sin_semantica': None if base else key[:10],
            'carpeta_instrumento': key, 'url': SOURCE, 'url_documento': archive_url,
            'documentos': docs, 'source': 'comunidad_autonoma',
            'organismo_fuente': 'Junta de Comunidades de Castilla-La Mancha — Consejería de Fomento',
            'origen': 'deposito_autonomico_planeamiento',
            'source_attributes': attributes,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    return rows


class MalagonAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='malagon', config=None, base_url=''):
        super().__init__(slug, config, base_url or LAYER)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        capture = self.config.get('capture_dir')
        capture = Path(capture) if capture else None
        if capture:
            capture.mkdir(parents=True, exist_ok=True)
        source_urls = [SOURCE]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-malagon/1.0'

            def fetch_json(params, filename):
                r = session.get(QUERY, params={'f': 'json', 'where': WHERE, **params}, timeout=40)
                r.raise_for_status()
                data = r.json()
                if 'error' in data or data.get('exceededTransferLimit'):
                    raise ValueError('Planning query failed or truncated')
                if capture:
                    (capture / filename).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
                source_urls.append(r.url)
                return data

            ids = fetch_json({'returnIdsOnly': 'true'}, 'inventory-ids.json').get('objectIds')
            if not ids or len(ids) != len(set(ids)):
                raise ValueError('Missing or duplicate inventory IDs')
            rows = []
            for offset in range(0, len(ids), 50):
                batch = ids[offset:offset + 50]
                data = fetch_json({'objectIds': ','.join(map(str, batch)), 'outFields': '*', 'returnGeometry': 'false'}, f'inventory-{offset}.json')
                features = data.get('features', [])
                if sorted(f['attributes']['OBJECTID'] for f in features) != sorted(batch):
                    raise ValueError('Inventory IDs do not match returned features')
                for feature in features:
                    attrs = feature['attributes']
                    # Validate identity and download host before any archive request.
                    validate_attributes(attrs)
                    url = attrs['DESCARGA']
                    with session.get(url, headers={'Range': 'bytes=-131072'}, timeout=40, stream=True) as r:
                        r.raise_for_status()
                        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', r.headers.get('Content-Range', ''))
                        if r.status_code != 206 or not match:
                            raise ValueError('Archive server must support bounded byte ranges')
                        start, end, total = map(int, match.groups())
                        if end != total - 1 or end - start + 1 > 131072:
                            raise ValueError('Unexpected archive range')
                        tail = r.raw.read(131073)
                    names = parse_archive_directory(tail, start, total)
                    if capture:
                        (capture / 'archive-tail.bin').write_bytes(tail)
                        (capture / 'archive-directory.json').write_text(json.dumps({'url': url, 'range_start': start, 'total_bytes': total, 'members': names}, ensure_ascii=False, indent=2), encoding='utf-8')
                    rows.extend(parse_projects(attrs, names))
                    source_urls.append(url)
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate planning instruments')
        result = {'status': 'ok', 'rows': len(rows), 'source_urls': list(dict.fromkeys(source_urls)), 'limitations': LIMITATIONS}
        self._write(out_jsonl, rows)
        return result

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
