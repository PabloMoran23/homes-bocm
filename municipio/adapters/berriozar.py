"""Berriozar planning inventory from the municipal-linked public Navarra SIUN."""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
from municipio.adapters.portal import AyuntamientoAdapter

PORTAL = 'https://www.berriozar.es/transparencia/informacion-sobre-ordenacion-territorial-urbanismo-medio-ambiente-y-vivienda/'
BASE = 'https://administracionelectronica.navarra.es/SIUN_Consulta/'
FILTERS = {'municipios': [903], 'entidadesPoblacion': [], 'tiposInstrumento': [], 'aprobadoPosterior': False}
LIMITATIONS = [
    'Cobertura: pestaña PG de SIUN para municipio 903, provincia 31; no pestaña OT, obras municipales ni licencias.',
    'Inventario histórico y en tramitación, no garantía de exhaustividad municipal ni de vigencia jurídica.',
    'Fecha BON y fecha de resolución se conservan por trámite; fechaDefinitiva no se convierte en fecha de acuerdo.',
    'Documentos y visores enlazados; no se extrae geometría vectorial ni se inventan coordenadas.',
    'Actualización mediante instantánea completa; no elimina registros externos ni publica datos.',
]


def iso_date(value):
    return date.fromisoformat(value[:10]).isoformat() if value else None


def parse_page(payload):
    """Validate server pagination metadata rather than assuming a first-page snapshot."""
    rows, info = payload['currentPage'], payload['pagedInfo']
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError('Invalid SIUN page')
    total, size, pages = (info[k] for k in ('totalElements', 'pageSize', 'totalPages'))
    if any(type(v) is not int for v in (total, size, pages)) or total < 1 or size < 1:
        raise ValueError('Empty or invalid SIUN inventory requires review')
    if pages != (total + size - 1) // size or len(rows) > size:
        raise ValueError('Inconsistent SIUN pagination')
    for row in rows:
        if type(row.get('idInstrumento')) is not int:
            raise ValueError('Missing SIUN instrument identifier')
    return rows, (total, size, pages)


def parse_instrument(data, expected_id):
    if data.get('idInstrumento') != expected_id:
        raise ValueError('SIUN detail identifier mismatch')
    municipalities = data.get('instrumentosMunicipios') or []
    if not any(m.get('idProvincia') == 31 and m.get('idMunicipio') == 903
               and m.get('municipio', {}).get('denominacion') == 'BERRIOZAR' for m in municipalities):
        raise ValueError('SIUN detail is not Berriozar, Navarra')
    title = data.get('denominacion')
    kind = (data.get('tipoInstrumento') or {}).get('denominacion')
    if not title or not kind:
        raise ValueError('SIUN instrument lacks title/type')
    source_url = BASE + 'api/Instrumentos/' + str(expected_id)
    documents = {}
    for doc in data['instrumentosDocumentos']:
        link = doc.get('rutaFichero')
        if not link or urlparse(link).scheme not in ('http', 'https'):
            raise ValueError('Invalid SIUN document link')
        documents.setdefault(link, {
            'id_documento': doc['idDocumento'], 'titulo': doc.get('denominacion'),
            'url': link, 'tipo_documento_siun': doc.get('idTipoDocumento'),
            'escala': doc.get('escala'), 'source_url': source_url,
        })
    procedures = []
    for proc in data['tramites']:
        item = {
            'id_tramite': proc['idTramite'],
            'fase': (proc.get('fase') or {}).get('denominacion'),
            'resolucion': (proc.get('resolucion') or {}).get('denominacion'),
            'fecha_bon': iso_date(proc.get('fecha')),
            'fecha_resolucion': iso_date(proc.get('fechaResolucion')),
            'numero_bon': proc.get('numBon'), 'numero_anuncio': proc.get('numAnuncio'),
            'descripcion': proc.get('descripcion'), 'url_documento': proc.get('rutaFichero'),
        }
        if item['numero_bon'] and item['fecha_bon']:
            item['url_bon'] = ('https://bon.navarra.es/es/' +
                ('anuncio/-/texto/' + item['fecha_bon'][:4] + '/' + str(item['numero_bon']) + '/' + str(item['numero_anuncio'])
                 if item['numero_anuncio'] else 'boletin/-/sumario/' + item['fecha_bon'][:4] + '/' + str(item['numero_bon'])))
        procedures.append(item)
    published = sorted({p['fecha_bon'] for p in procedures if p['numero_bon'] and p['fecha_bon']})
    approved = sorted({p['fecha_resolucion'] for p in procedures
                       if p['fase'] == 'Definitiva' and p['resolucion'] == 'Aprobación' and p['fecha_resolucion']})
    return {
        'id': f'berriozar-siun-{expected_id}', 'siun_id': expected_id,
        'municipio': 'Berriozar', 'codigo_ine': '31903', 'provincia': 'Navarra',
        'titulo': f'{kind} — {title}', 'tipo': kind, 'descripcion': data.get('descripcion'),
        'expediente': data.get('numExpediente'), 'id_instrumento_padre': data.get('idPadre'),
        'fecha': None, 'fecha_publicacion': published[0] if published else None,
        'fecha_acuerdo': None, 'fecha_aprob': approved[-1] if approved else None,
        'fechas_siun': {k: data.get(k) for k in ('fechaInicial', 'fechaDefinitiva', 'fechaRegistro', 'fechaAnulado', 'fechaExtinguido')},
        'estado_siun': {k: data.get(k) for k in ('vigencia', 'anulado', 'extinguido', 'exposicionPublica', 'planGeneralVigente')},
        'url': BASE + f'Index.html#/instrumento/{expected_id}',
        'source': 'ayuntamiento', 'origen': 'siun_navarra_enlazado_por_ayuntamiento',
        'source_url': source_url, 'inventario_municipal_url': PORTAL,
        'municipios_siun': municipalities, 'tramites': procedures,
        'documentos': list(documents.values()),
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False,
    }


class BerriozarAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('capture_dir')
        source_urls = [PORTAL]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-berriozar/1.0 (public planning inventory)'

            def fetch(url, name, payload=None):
                response = session.get(url, timeout=35) if payload is None else session.post(url, json=payload, timeout=35)
                response.raise_for_status()
                source_urls.append(url)
                if captures:
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / name).write_bytes(response.content)
                time.sleep(0.1)
                return response

            # Confirm provenance from the current municipal inventory on every run.
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(fetch(PORTAL, 'municipal-inventory.html').content, 'html.parser')
            content = soup.select_one('main .contenido.content')
            if content is None or not any(a['href'].startswith(BASE + 'Index.html') for a in content.select('a[href]')):
                raise ValueError('Municipal SIUN inventory link missing')
            municipalities = fetch(BASE + 'api/Municipios', 'municipalities.json').json()
            if not any(m.get('idMunicipio') == 903 and m.get('denominacion') == 'BERRIOZAR' for m in municipalities):
                raise ValueError('SIUN municipality code changed')
            inventory, seen, metadata = [], set(), None
            offset = 0
            while True:
                url = BASE + f'api/Instrumentos/PG/default/false/{offset}/25'
                page, info = parse_page(fetch(url, f'inventory-{offset}.json', FILTERS).json())
                if metadata is not None and info != metadata:
                    raise ValueError('SIUN inventory changed during pagination')
                metadata = info
                total, size, pages = info
                if len(page) != min(size, total - offset):
                    raise ValueError('Missing records in SIUN page')
                for row in page:
                    key = row['idInstrumento']
                    if key in seen:
                        raise ValueError('Repeated SIUN record across pages')
                    seen.add(key)
                    inventory.append(row)
                offset += len(page)
                if offset == total:
                    break
                if not page or offset > total:
                    raise ValueError('SIUN pagination failed to advance')
            rows = []
            for item in inventory:
                key = item['idInstrumento']
                detail = fetch(BASE + f'api/Instrumentos/{key}', f'instrument-{key}.json').json()
                rows.append(parse_instrument(detail, key))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(dict.fromkeys(source_urls)),
                'pages': metadata[2], 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
