"""Arnedo's public STA PGM document inventory, grouped as one instrument."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://sede.arnedo.es'
SOURCE = BASE + '/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=TRANSPAR_PLANGENURB'
EVENT = BASE + '/sta/CarpetaPublic/submitAjax.aa'
LIMITATIONS = [
    'Cobertura parcial municipal: solo el inventario documental del Plan General; no incluye todas las modificaciones, obras ni licencias.',
    'La publicación de documentos en la sede no acredita aprobación ni vigencia; resolutionDate no se interpreta como fecha de acuerdo.',
    'Sin geometría verificada ni coordenadas; publication_ready=false.',
    'Los enlaces documentales CUD/HASH_CUD se redescubren en cada ejecución y pueden cambiar.',
]


def _soup(html):
    return BeautifulSoup(html, 'html.parser')


def _date(value):
    return date(value['year'], value['month'], value['day']).isoformat() if value else None


class ArnedoAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='arnedo', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html):
        if 'PLAN GENERAL DE ORDENACIÓN URBANA' not in _soup(html).get_text(' ', strip=True):
            raise ValueError('Missing municipal PGM heading')
        match = re.search(r'var\s+dataset_TR_PLAN_GENURB\s*=\s*(\[.*?\]);', html, re.S)
        if not match or re.search(r'serverSide\s*:\s*true', html):
            raise ValueError('Missing complete client-side PGM inventory')
        rows = json.loads(match[1])
        if not rows:
            raise ValueError('Empty PGM inventory')
        ids, counts, actual = set(), {}, {}
        for row in rows:
            key = row['dboid']
            category = row['tablon']
            if not re.fullmatch(r'\d+', key) or key in ids or not row['descriptionProc'].strip():
                raise ValueError('Invalid or duplicate document identity')
            ids.add(key)
            if category['description'] not in {'Normativa', 'Planos', 'Carátula'}:
                raise ValueError('Unreviewed category in PGM inventory')
            cid = category['dboid']
            count = category['numOpenResolutions']
            if cid in counts and counts[cid] != count:
                raise ValueError('Inconsistent inventory totals')
            counts[cid] = count
            actual[cid] = actual.get(cid, 0) + 1
            _date(row.get('pubDateIni'))
        if counts != actual:
            raise ValueError('Incomplete PGM inventory; pagination or count changed')
        if not any(r['descriptionProc'] == 'Normativa PGM' for r in rows):
            raise ValueError('PGM normative document missing')
        return rows

    @staticmethod
    def parse_documents(html, entry):
        soup = _soup(html)
        if entry['descriptionProc'] not in soup.get_text(' ', strip=True):
            raise ValueError('Detail does not identify requested PGM document')
        docs = {}
        for a in soup.select('a[href]'):
            url = urljoin(BASE, a['href'])
            parsed = urlparse(url)
            if parsed.hostname != 'sede.arnedo.es' or parsed.path != '/sta/docs/GetDocumentServlet':
                continue
            query = parse_qs(parsed.query)
            if not query.get('CUD') or not query.get('HASH_CUD'):
                raise ValueError('Document lacks public CUD locator')
            docs[url] = {
                'titulo': entry['descriptionProc'], 'url': url,
                'enlace_texto': a.get_text(' ', strip=True),
                'publicacion_id': entry['dboid'],
                'categoria': entry['tablon']['description'],
                'fecha_publicacion': _date(entry.get('pubDateIni')),
                'procedencia': entry.get('remitent', {}).get('description'),
                'source_url': SOURCE,
                'source_event': {'eventScreenId': 'TR_PLAN_GENURB', 'eventAction': 'ACCION_DETALLE',
                                 'eventArguments': 'KEY=' + entry['dboid']},
            }
        if not docs:
            raise ValueError('PGM detail has no downloadable source document')
        return list(docs.values())

    @staticmethod
    def build_projects(entries, documents):
        if not entries or {d['publicacion_id'] for d in documents} != {r['dboid'] for r in entries}:
            raise ValueError('Not all PGM entries have documents')
        dates = sorted({d['fecha_publicacion'] for d in documents if d['fecha_publicacion']})
        return [{
            'id': 'arnedo-proy-pgm', 'municipio': 'Arnedo', 'codigo_ine': '26018',
            'provincia': 'La Rioja', 'titulo': 'Plan General Municipal de Arnedo',
            'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': dates[0] if len(dates) == 1 else None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_documental_pgm',
            'documentos': documents, 'numero_entradas_documentales': len(entries),
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'limitations': LIMITATIONS,
        }]

    def _capture(self, name, content):
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text(content, encoding='utf-8')

    def _fetch(self, session, url, data=None):
        with session.request('POST' if data is not None else 'GET', url, data=data,
                             timeout=40, stream=True) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'sede.arnedo.es':
                raise ValueError('Unexpected redirect away from municipal sede')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 5_000_000:
                    raise ValueError('Source exceeds response size limit')
                chunks.append(chunk)
            return b''.join(chunks).decode('utf-8')

    def _event(self, session, html, obj, action, arguments):
        form = _soup(html).select_one('form#webAppPageForm')
        if not form:
            raise ValueError('STA public form missing')
        data = {i['name']: i.get('value', '') for i in form.select('input[type=hidden][name]')}
        data.update(eventScreenId='TR_PLAN_GENURB', eventObject=obj,
                    eventAction=action, eventArguments=arguments)
        return self._fetch(session, EVENT, data)

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-arnedo/1.0'
            html = self._fetch(session, SOURCE)
            self._capture('pgm-home.html', html)
            # KEY=all is the site's own "Todos los documentos" control.
            if not re.search(r"callWidgetEvent\('TR_PLAN_GENURB','LISTATABLON','LISTATABLON','KEY=all'\)", html):
                raise ValueError('All-documents control changed')
            html = self._event(session, html, 'LISTATABLON', 'LISTATABLON', 'KEY=all')
            self._capture('pgm-inventory.html', html)
            entries = self.parse_inventory(html)
            documents = []
            for entry in entries:
                html = self._event(session, html, '', 'ACCION_DETALLE', 'KEY=' + entry['dboid'])
                self._capture('pgm-detail-' + entry['dboid'] + '.html', html)
                documents.extend(self.parse_documents(html, entry))
            projects = self.build_projects(entries, documents)
        self._write(out_jsonl, projects)
        return {'status': 'ok', 'rows': len(projects), 'inventory_entries': len(entries),
                'documents': len(documents), 'source_urls': [SOURCE, EVENT], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
