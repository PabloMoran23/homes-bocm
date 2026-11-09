"""Firgas municipal NNSS inventory: instruments, not individual PDF projects."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.villadefirgas.es/urbanismo/'
COVERAGE = 'NNSS, revisiones/modificaciones y planes parciales del inventario municipal'


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _date(value):
    value = value.strip()
    if not value:
        return None
    return datetime.strptime(value.replace('-', '/'), '%d/%m/%Y').date().isoformat()


def _links(node):
    documents = {}
    for a in node.select('a[href]'):
        url = urljoin(SOURCE, a['href'])
        if urlparse(url).scheme in ('http', 'https'):
            documents.setdefault(url, {'titulo': _text(a), 'url': url, 'source_url': SOURCE})
    return list(documents.values())


def _record(title, kind, identity):
    return {
        'id': 'firgas-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
        'municipio': 'Firgas', 'codigo_ine': '35008', 'provincia': 'Las Palmas',
        'titulo': title, 'tipo': kind, 'url': SOURCE,
        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
        'coverage': COVERAGE, 'fecha': None,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'vigencia_verificada': False,
    }


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    # Scope to NNSS only: the following PGO has historical, conflicting phases
    # and a notice of caducidad. Never apply its dates or documents to NNSS.
    active = False
    panels = {}
    for node in soup.find_all(['h2', 'div']):
        if node.name == 'h2':
            heading = _text(node)
            if heading.startswith('NNSS ('):
                active = True
            elif active:
                break
        if active and 'wgl-accordion_panel' in node.get('class', []):
            header = node.select_one('.wgl-accordion_header')
            if header is None:
                raise ValueError('Missing Firgas inventory panel header')
            title = re.sub(r'^\d+\.\s*', '', _text(header))
            if title in panels:
                raise ValueError('Duplicate Firgas inventory panel')
            panels[title] = node
    required = {'Aprobación y Publicación', 'Modificaciones / Revisiones',
                'Archivos del Planeamiento', 'Planes Parciales'}
    if not required.issubset(panels):
        raise ValueError('Firgas NNSS inventory missing required sections')
    for panel in panels.values():
        for a in panel.select('a[href]'):
            query = parse_qs(urlparse(a['href']).query)
            if ('next' in a.get('rel', []) or
                    any(k in query for k in ('page', 'paged', 'offset', 'start')) or
                    a.find_parent(class_=re.compile(r'pagination|pager'))):
                raise ValueError('Unexpected pagination in Firgas inventory; refusing partial output')

    approval = panels['Aprobación y Publicación']
    # Each event retains all its publications; publication != agreement date.
    narrative = _text(approval)
    pattern = (r'(Aprobación Definitiva(?: Parcial)?)\s+Aprobado el\s+'
               r'(\d{1,2}/\d{1,2}/\d{4})(.*?)(?=Aprobación Definitiva|$)')
    events = []
    for match in re.finditer(pattern, narrative):
        publications = []
        for pub in re.finditer(r'Publicado en el (BOC|BOP) del día (\d{1,2}/\d{1,2}/\d{4}) Nº (\d+)', match[3]):
            linked = [a for a in approval.select('a[href]') if pub[0] in _text(a)]
            if len(linked) != 1:
                raise ValueError('Unlinked/ambiguous Firgas NNSS publication')
            publications.append({'boletin': pub[1], 'fecha_publicacion': _date(pub[2]),
                                 'numero': pub[3], 'url': urljoin(SOURCE, linked[0]['href'])})
        if not publications:
            raise ValueError('NNSS approval without publication provenance')
        events.append({'fase': match[1], 'fecha_aprob': _date(match[2]), 'publicaciones': publications})
    documents = _links(panels['Archivos del Planeamiento'])
    if not events or not documents:
        raise ValueError('NNSS lacks approval events or linked documents')
    nnss = _record('Normas Subsidiarias de Planeamiento del Municipio de Firgas', 'NNSS', 'NNSS')
    nnss.update({'eventos': events, 'documentos': documents + _links(approval),
                 'descripcion': narrative})
    rows = [nnss]
    # Parse named table entries by their explicit columns, preserving all links.
    for section in ('Modificaciones / Revisiones', 'Planes Parciales'):
        tables = panels[section].find_all('table')
        if not tables:
            raise ValueError('Firgas inventory tables missing')
        for table in tables:
            trs = table.find_all('tr')
            headers = [_text(c) for c in trs[0].find_all(['th', 'td'], recursive=False)]
            partial = headers[:3] == ['Nombre', 'Fase', 'Fecha de aprobación']
            modification = headers[:2] in (['Fase', 'Revisión'], ['Fase', 'Modificación'])
            expected = 7 if partial else 8
            if not (partial or modification) or len(headers) != expected:
                raise ValueError('Unknown Firgas inventory columns')
            found = 0
            for tr in trs[1:]:
                cells = tr.find_all(['td', 'th'], recursive=False)
                if len(cells) != expected:
                    raise ValueError('Malformed Firgas inventory row')
                values = [_text(c) for c in cells]
                name, phase = (values[0], values[1]) if partial else (values[1], values[0])
                if not name.startswith(('Plan Parcial', 'Avance.', 'Aprobación Inicial.')):
                    raise ValueError('Unexpected non-instrument in Firgas table')
                kind = 'plan parcial' if partial else headers[1].lower()
                row = _record(name, kind, kind + ':' + name)
                pubs = []
                for bulletin in ('BOC', 'BOP'):
                    index = headers.index('Fecha ' + bulletin)
                    pub_date = _date(values[index])
                    if pub_date:
                        links = _links(cells[index + 1])
                        if len(links) > 1:
                            raise ValueError('Ambiguous bulletin links')
                        pubs.append({'boletin': bulletin, 'fecha_publicacion': pub_date,
                                     'numero': values[index + 1],
                                     'url': links[0]['url'] if links else None,
                                     'source_url': SOURCE})
                row.update({'fase': phase, 'publicaciones': pubs, 'documentos': _links(tr),
                            'descripcion': ' | '.join(values), 'columnas_fuente': dict(zip(headers, values))})
                if partial:
                    row['fecha_aprob'] = _date(values[2])
                else:
                    row['fecha_acuerdo'] = _date(values[3])
                    # COTMAC and plenary agreement are separate columns.
                    row['fecha_acuerdo_cotmac'] = _date(values[2])
                if not row['documentos'] or not pubs:
                    raise ValueError('Instrument without documentary provenance')
                rows.append(row)
                found += 1
            if not found:
                raise ValueError('Empty Firgas inventory table')
    identities = [row['id'] for row in rows]
    if len(identities) != len(set(identities)):
        raise ValueError('Duplicate instruments in Firgas inventory')
    return rows


class FirgasAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; FirgasMunicipalInventory/1.0)'})
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(SOURCE).hostname:
            raise ValueError('Unexpected Firgas source redirect')
        rows = parse_inventory(response.text)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_text(response.text, encoding='utf-8')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'source_urls': [SOURCE],
                'coverage': COVERAGE, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
