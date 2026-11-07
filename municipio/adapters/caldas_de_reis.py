"""Caldas de Reis: complete SIOTUGA municipal urban-planning inventory."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://siotuga.xunta.gal/siotuga/'
INVENTORY = BASE + 'inventario.php?inv=1&idconcello=36005'
CLASSES = {14: 'planeamiento_general', 13: 'planeamiento_desarrollo',
           16: 'planeamiento_historico', 18: 'delimitacion_nucleo_rural'}
LIMITATIONS = [
    'Solo inventario municipal de planeamiento SIOTUGA, clases 14, 13, 16 y 18; no registro de obras ni licencias.',
    'Incluye instrumentos históricos; la presencia en el inventario no acredita vigencia actual.',
    'No incluye el inventario supramunicipal de ordenación del territorio ni expedientes en tramitación no inventariados.',
    'Fechas declaradas por SIOTUGA; DOG, BOP y normativa conservados por separado de aprobación.',
    'Se conservan enlaces documentales; no se extrae contenido ni geometría de los PDF.',
]


def parse_inventory(payload):
    """The public UI receives an entire JSON array and paginates it client-side."""
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError('Expected full inventory array (pagination/envelope changed)')
    for item in payload:
        if not isinstance(item, dict) or not str(item.get('id', '')).isdigit():
            raise ValueError('Invalid inventory instrument')
        if not item.get('docnome') or not item.get('figura'):
            raise ValueError('Missing instrument name/type')
    return payload


def parse_instrument(item, detail, category):
    general = detail['datos_xerais']
    if (str(general['id']) != str(item['id']) or
            general['folder'] != 'CALDASDEREIS' or
            general['menutitle'] != 'Caldas de Reis' or
            general['filesroot'] != 'documentos/urbanismo/'):
        raise ValueError('Instrument identity/municipality mismatch')
    docs = {}
    for group in detail['elementos'] or []:
        for component in group['componentes'] or []:
            filename = component['pathesperado']
            if not re.fullmatch(r'[A-Za-z0-9_. -]+\.(?:pdf|jpg|jpeg|png)', filename, re.I):
                raise ValueError('Unexpected document path')
            url = urljoin(BASE, general['filesroot'] + general['folder'] + '/documents/' + quote(filename))
            document = docs.setdefault(url, {'titulo': component['descripcion'], 'url': url, 'grupos': []})
            if group['description'] not in document['grupos']:
                document['grupos'].append(group['description'])
    row = {
        'id': 'caldas-de-reis-siotuga-' + str(item['id']),
        'municipio': 'Caldas de Reis', 'codigo_ine': '36005', 'provincia': 'Pontevedra',
        'titulo': item['docnome'].strip(), 'tipo': 'planeamiento_urbanistico',
        'figura': item['figura'], 'categoria_inventario': category,
        'source': 'xunta_galicia', 'origen': 'siotuga_inventario_municipal',
        'url': INVENTORY, 'source_id': str(item['id']),
        'detalle_fuente': {'url': BASE + 'assets/inventario/getIOTPU.php',
                           'method': 'POST', 'iddoc': str(item['id']), 'idp': '0'},
        'documentos': list(docs.values()),
        'documentos_status': 'linked' if docs else 'unavailable_in_inventory',
        'incidencias_iuris': item.get('incidencias_iuris'),
        'publication_ready': False, 'geometry_status': 'unavailable',
    }
    for original, target in [('fechaaddef', 'fecha_aprob'), ('fechadog', 'fecha_publicacion_dog'),
                             ('fechabop', 'fecha_publicacion_bop'),
                             ('fechanormativabop', 'fecha_publicacion_normativa_bop')]:
        value = item.get(original)
        if value:
            row[target] = date.fromisoformat(value).isoformat()
    return row


class CaldasDeReisAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        sources = [INVENTORY]

        def capture(name, body):
            if captures:
                path = Path(captures)
                path.mkdir(parents=True, exist_ok=True)
                (path / name).write_text(body, encoding='utf-8')

        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-caldas-de-reis/1.0'

            def fetch(url, data=None):
                r = session.get(url, timeout=(10, 40)) if data is None else session.post(url, data=data, timeout=(10, 40))
                r.raise_for_status()
                if not r.url.startswith(BASE):
                    raise ValueError('Unexpected source redirect')
                return r

            response = fetch(INVENTORY)
            soup = BeautifulSoup(response.text, 'html.parser')
            selected = soup.select_one('option[value="36005"]')
            if not selected or selected.get_text(strip=True) != 'Caldas de Reis':
                raise ValueError('Municipal inventory selector changed')
            # Public, anonymous form nonce supplied by SIOTUGA, never a stored credential.
            token = soup.select_one('#token')['value']
            if soup.select_one('#lang') is None:
                raise ValueError('Missing inventory language')
            language = soup.select_one('#lang')['value']
            if soup.select_one('#token'):
                soup.select_one('#token')['value'] = '[public nonce omitted]'
            capture('inventory.html', str(soup))
            records = {}
            for cls, category in CLASSES.items():
                url = BASE + 'assets/inventario/query_document.php'
                r = fetch(url, {'id': '36005', 'idclase': cls, 'token': token})
                capture(f'class-{cls}.json', r.text)
                sources.append(url + f'?id=36005&idclase={cls}')
                for item in parse_inventory(r.json()):
                    key = str(item['id'])
                    if key in records:
                        raise ValueError('Instrument appears in multiple categories; review grouping')
                    detail_url = BASE + 'assets/inventario/getIOTPU.php'
                    d = fetch(detail_url, {'iddoc': key, 'idp': '0', 'lang': language, 'token': token})
                    capture(f'detail-{key}.json', d.text)
                    sources.append(detail_url + '?iddoc=' + key + '&idp=0')
                    records[key] = parse_instrument(item, d.json(), category)
            if not records:
                raise ValueError('No usable municipal planning instruments')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records.values()), encoding='utf-8')
        temporary.replace(output)
        return {'count': len(records), 'live_records': len(records), 'source_urls': sources,
                'limitations': LIMITATIONS, 'coverage': 'complete_returned_urban_planning_inventory',
                'pagination': 'All four full JSON arrays; browser DataTables pagination is client-side.'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
