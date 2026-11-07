"""Coria's current PGM/PECH document inventory, not a licence register."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://coria.org/ayuntamiento/index.php/plan-general-municipal-y-pepch/'
DOE = 'https://doe.juntaex.es/otrosFormatos/html.php?anio=2026&doe=440o&xml=2026080310'
LIMITATIONS = [
    'Partial snapshot: new PGM and PECH revision only; historic/current NNSS, modifications and public works are outside this adapter.',
    'No granted licences; no verified geometry or coordinates; publication_ready=false.',
    'PDF links and publisher-supplied metadata retained; PDF contents and checksums are not verified.',
    'The inventory labels Documento Inicial Estratégico and Memoria de Participación Ciudadana point to the same PDF; both labels retained.',
    'PGM dates refer to initial approval of the advance, not final approval of the PGM. No PECH agreement date is inferred.',
]
MONTHS = {m: n for n, m in enumerate('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), 1)}


def _spanish_date(value):
    match = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', value.lower())
    if not match:
        return None
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


def parse_notice(html):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    if 'AYUNTAMIENTO DE CORIA' not in text or 'documento de avance del Plan General Municipal de Coria' not in text:
        raise ValueError('Unexpected DOE notice identity')
    agreement = re.search(r'Aprobado inicialmente por el Ayuntamiento-Pleno, en sesión ordinaria de (\d{1,2} de \w+ de \d{4})', text)
    publication = re.search(r'Fecha Publicación:\s*[^,]+,\s*(\d{1,2} de \w+ de \d{4})', text)
    pdf = [urljoin(DOE, a['href']) for a in soup.select('a[href]') if a.get_text(strip=True) == 'PDF']
    if not agreement or not publication or len(pdf) != 1 or not pdf[0].startswith('https://doe.juntaex.es/pdfs/doe/'):
        raise ValueError('DOE date/provenance structure changed')
    return {'fecha_acuerdo': _spanish_date(agreement[1]), 'fecha_publicacion': _spanish_date(publication[1]), 'url_documento': pdf[0]}


def parse_inventory(html, notice):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.entry-content')
    title = soup.select_one('h1')
    if content is None or title is None or 'Plan General Municipal y PEPCH' not in title.get_text(' ', strip=True):
        raise ValueError('Missing Coria planning inventory')
    if soup.select('a[rel~=next], .page-links, .pagination, .nav-links .nav-next'):
        raise ValueError('Paginated inventory detected; refusing incomplete extraction')
    heading = content.find(lambda tag: tag.name in ('h2', 'h3') and tag.get_text(strip=True) == 'Documentación')
    if heading is None:
        raise ValueError('Missing document section')
    section = heading.parent
    if 'AVANCE DEL PLAN' not in section.get_text(' ', strip=True):
        raise ValueError('Inventory no longer identifies an advance')
    groups = {'pgm': [], 'pech': []}
    for a in section.select('a[href]'):
        target = urljoin(SOURCE, a['href'])
        if not urlsplit(target).path.lower().endswith('.pdf'):
            continue
        if urlsplit(target).hostname not in ('coria.org', 'www.coria.org'):
            raise ValueError('Unverified document host')
        target = quote(target, safe=':/%?=&')
        label = a.get_text(' ', strip=True)
        key = 'pech' if 'Plan Especial del Casco Histórico' in label else 'pgm'
        container = a.find_parent('p')
        document = {'titulo': label, 'url': target, 'source_url': SOURCE,
                    'metadata_fuente': container.get_text(' ', strip=True) if container else label}
        if document not in groups[key]:
            groups[key].append(document)
    if not groups['pech'] or not any('Ordenación Urbanística' in d['titulo'] for d in groups['pgm']):
        raise ValueError('Missing named PGM/PECH technical documents')
    rows = []
    for key, docs in groups.items():
        row = {
            'id': 'coria-plan-' + key + '-revision-2025',
            'municipio': 'Coria', 'provincia': 'Cáceres', 'codigo_ine': '10067',
            'titulo': 'Plan General Municipal de Coria' if key == 'pgm' else 'Revisión del Plan Especial del Casco Histórico de Coria',
            'tipo': 'PGM' if key == 'pgm' else 'PECH',
            'fase': 'aprobación inicial del avance' if key == 'pgm' else 'documentación de revisión en el avance del PGM',
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'documentos': docs, 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'coverage': 'partial_current_pgm_pech_inventory', 'limitations': LIMITATIONS,
        }
        if key == 'pgm':
            row.update({k: notice[k] for k in ('fecha_acuerdo', 'fecha_publicacion')})
            row['provenance_fechas'] = DOE
            row['documentos'].append({'titulo': 'Anuncio DOE: aprobación inicial del avance del PGM y documento inicial estratégico', 'url': notice['url_documento'], 'source_url': DOE})
        rows.append(row)
    return rows


class CoriaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, name):
        with requests.get(url, timeout=40, stream=True, headers={'User-Agent': 'municipio-coria/1.0'}) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname != urlsplit(url).hostname:
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 2_000_000:
                    raise ValueError('Source exceeds response limit; extraction aborted')
                chunks.append(chunk)
            body = b''.join(chunks)
            if self.config.get('capture_dir'):
                directory = Path(self.config['capture_dir'])
                directory.mkdir(parents=True, exist_ok=True)
                (directory / name).write_bytes(body)
            # DOE serves Latin-1 HTML; the municipal site serves UTF-8.
            return BeautifulSoup(body, 'html.parser').decode()

    def backfill_proyectos(self, out_jsonl: Path):
        html = self._fetch(SOURCE, 'pgm.html')
        notice = parse_notice(self._fetch(DOE, 'doe.html'))
        rows = parse_inventory(html, notice)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, DOE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Complete refresh of the two-instrument inventory; no date cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
