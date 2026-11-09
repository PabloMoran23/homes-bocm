"""Olvera's public planning register; no licence or current-validity inference."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

INVENTORY_URL = 'https://www.olvera.es/es/normativa-legal/instrumentos-urbanisticos'
LIMITATIONS = [
    'Partial municipal coverage: only the public Instrumentos Urbanísticos register; not all works or newer planning portals.',
    'Cancelled registrations are excluded. Approval and bulletin dates are transcribed from the register, not independently certified.',
    'Document links are retained; PDF contents and availability are not exhaustively verified. No coordinates or licences.',
    'Update performs a complete inventory refresh, not an incremental event feed.',
]


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def field(value, number):
    match = re.search(rf'{number}º\s*\.\s*-\s*[^:]+:\s*(.*?)(?=\s*[1-6]º\s*\.\s*-|$)', value, re.S)
    return match.group(1).strip() if match else ''


def register_date(value):
    """The register uses dd/mm/yy (1999 onward), occasionally four-digit years."""
    matches = re.findall(r'(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?!\d)', value)
    if len(matches) != 1:
        return None
    day, month, year = map(int, matches[0])
    if year < 100:
        year += 1900 if year >= 90 else 2000
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def documents(cell, url):
    result = {}
    for link in cell.select('a[href]'):
        target = urljoin(url, link['href'])
        if urlparse(target).scheme not in {'http', 'https'}:
            raise ValueError('Unexpected document URL')
        title = text(link) or link.get('title') or target
        if target in result:
            if title not in result[target]['titulos']:
                result[target]['titulos'].append(title)
        else:
            result[target] = {'url': target, 'titulos': [title], 'source_url': url}
    return list(result.values())


def parse_inventory(html, url=INVENTORY_URL):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.uk-article')
    if article is None or 'Instrumentos Urbanísticos' not in text(article):
        raise ValueError('Planning article missing')
    # Fail explicitly if the previously single-page register gains pagination.
    if article.select('.pagination, .pagenav, .pager, a[rel~=next], a[rel~=prev]') or soup.select('link[rel~=next]'):
        raise ValueError('Pagination detected; coverage must be reviewed')
    tables = [t for t in article.select('table') if 'INSCRIPCIÓN' in text(t) and 'CANCELACIONES' in text(t)]
    if len(tables) != 1:
        raise ValueError('Expected one planning register table')
    records, excluded, seen = [], [], set()
    for tr in tables[0].select('tr')[1:]:
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 5 or not re.fullmatch(r'\d+º?', text(cells[0])):
            raise ValueError('Unexpected register row')
        number = int(text(cells[0]).rstrip('º'))
        if number in seen:
            raise ValueError('Duplicate registration number')
        seen.add(number)
        registration, notes = text(cells[1]), text(cells[3])
        title, codes = field(registration, 3), field(registration, 2)
        if not title or not codes:
            raise ValueError('Missing instrument identification')
        if 'CANCELACIÓN' in notes.upper():
            excluded.append({'inscripcion': number, 'reason': 'cancelled_registration', 'nota': notes})
            continue
        kind = ('estudio de detalle' if re.search(r'\bED\b', codes) else
                'plan parcial' if re.search(r'\bPP\b', codes) else
                'modificación de planeamiento' if re.search(r'\bM\b', codes) else
                'planeamiento general' if re.search(r'\bTR\b', codes) else 'instrumento de planeamiento')
        row = {
            'id': f'olvera-registro-{number}', 'municipio': 'Olvera', 'codigo_ine': '11024',
            'provincia': 'Cádiz', 'titulo': f'{kind.capitalize()}: {title}', 'tipo': kind,
            'inscripcion': number, 'expediente_grupo': f'Registro de instrumentos urbanísticos, inscripción {number}',
            'source_locator': f'tabla de inscripciones, fila {number}',
            'url': url, 'source': 'ayuntamiento',
            'origen': 'registro_instrumentos_urbanisticos', 'inventory_url': url,
            'clase_planeamiento_fuente': codes, 'notas_registro': notes,
            'referencia_publicacion': text(cells[2]),
            'aprobacion_definitiva_fuente': field(registration, 5),
            'documentos': documents(cells[4], url),
            'publication_ready': False, 'geometry_status': 'unavailable',
            'vigencia_verificada': False,
        }
        approval = register_date(row['aprobacion_definitiva_fuente'])
        publication = register_date(row['referencia_publicacion'])
        if approval:
            row['fecha_aprob'] = approval
        if publication:
            row['fecha_publicacion'] = publication
            row['fecha_publicacion_tipo'] = 'boletin_oficial_segun_registro'
        # Registration 1 also contains a distinct partial adaptation. Keep its
        # documents separate; the 1999 approval does not apply to that adaptation.
        adaptation = [d for d in row['documentos'] if '/NNSS_adaptacion_parcial-1/' in d['url']]
        if adaptation:
            row['documentos'] = [d for d in row['documentos'] if d not in adaptation]
            note_date = re.search(r'acuerdo Plenario de fecha (\d{1,2}) de mayo de (\d{4})', notes)
            adapted = {
                'id': f'olvera-registro-{number}-adaptacion-parcial',
                'municipio': 'Olvera', 'codigo_ine': '11024', 'provincia': 'Cádiz',
                'titulo': '1ª Adaptación Parcial NN.SS.', 'tipo': 'adaptación parcial de planeamiento',
                'inscripcion': number, 'relacionado_con': row['id'],
                'expediente_grupo': f'Registro de instrumentos urbanísticos, inscripción {number}: adaptación parcial',
                'source_locator': f'tabla de inscripciones, fila {number}, 1ª Adaptación Parcial NN.SS.', 'url': url,
                'inventory_url': url, 'source': 'ayuntamiento',
                'origen': 'registro_instrumentos_urbanisticos', 'notas_registro': notes,
                'documentos': adaptation, 'publication_ready': False,
                'geometry_status': 'unavailable', 'vigencia_verificada': False,
            }
            if note_date:
                adapted['fecha_acuerdo'] = date(int(note_date[2]), 5, int(note_date[1])).isoformat()
            records.append(adapted)
        records.append(row)
    if not records or seen != set(range(1, max(seen) + 1)):
        raise ValueError('Empty or incomplete register sequence')
    return records, excluded


class OlveraAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        response = requests.get(INVENTORY_URL, timeout=60, headers={'User-Agent': 'MunicipalPlanningInventory/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != 'www.olvera.es':
            raise ValueError('Unexpected source redirect')
        rows, excluded = parse_inventory(response.text, response.url)
        if self.config.get('evidence_dir'):
            captures = Path(self.config['evidence_dir'])
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'instrumentos.html').write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [response.url],
                'coverage': 'public_planning_register', 'limitations': LIMITATIONS,
                'excluded': excluded, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
