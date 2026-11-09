"""Snapshot of the municipal planning inventory, not a register of licences."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.argamasilladealba.es/servicios-municipales/urbanismo/urbanismo'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
LIMITATIONS = [
    'Snapshot of the municipal Urbanismo inventory only; not all municipal works or historical planning.',
    'Sector normative extracts do not establish current validity or a complete technical dossier.',
    'CMS card dates are retained as fecha_catalogo, never treated as agreement/publication dates.',
    'Linked Google Drive files/folders retained, not enumerated or downloaded.',
    'Dates and phases extracted from municipal HTML narratives; PDFs retained as documentary provenance.',
    'No verified project geometry or public register of granted licences; publication_ready=false.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _date(value):
    value = value.strip().lower()
    for fmt in ('%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    match = re.fullmatch(r'(\d{1,2}) de (\w+) de (\d{4})', value)
    if match and match[2] in MONTHS:
        return datetime(int(match[3]), MONTHS.index(match[2]) + 1, int(match[1])).date().isoformat()
    raise ValueError(f'Unrecognized source date: {value}')


def _section(heading):
    """Content until next heading of equal/higher level, including nested headings."""
    nodes = []
    level = int(heading.name[1])
    for node in heading.next_elements:
        if getattr(node, 'name', None) in ('h1', 'h2', 'h3') and int(node.name[1]) <= level:
            break
        nodes.append(node)
    return nodes


def _documents(nodes, url):
    docs = {}
    context = ''
    for node in nodes:
        if getattr(node, 'name', None) == 'p' and not node.find('a'):
            context = _text(node)
        if getattr(node, 'name', None) != 'a' or not node.get('href'):
            continue
        target = urljoin(url, node['href'])
        parsed = urlparse(target)
        if parsed.scheme != 'https' or parsed.hostname not in ('www.argamasilladealba.es', 'drive.google.com'):
            raise ValueError(f'Unexpected document destination: {target}')
        docs.setdefault(target, {'titulo': _text(node), 'url': target, 'contexto': context,
                                 'inventory_url': url})
    return list(docs.values())


def _record(title, identity, docs, url, description=''):
    if not docs:
        raise ValueError(f'Instrument without documents: {title}')
    return {
        'id': 'argamasilla-de-alba-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
        'municipio': 'Argamasilla de Alba', 'codigo_ine': '13019', 'provincia': 'Ciudad Real',
        'titulo': title, 'tipo': 'instrumento o proyecto urbanístico',
        'url': docs[0]['url'], 'inventory_url': url, 'documentos': docs,
        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
        'descripcion': description, 'fecha': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'fecha_publicacion': None,
        'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False,
    }


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.find('main')
    if main is None:
        raise ValueError('Missing municipal main content')
    headings = main.find_all(['h2', 'h3'])
    norm = next((h for h in headings if _text(h) == 'Normativa urbanística'), None)
    pom = next((h for h in headings if _text(h) == 'Plan de Ordenación Municipal'), None)
    area = next((h for h in headings if _text(h) == 'Área de Actuación A3'), None)
    if norm is None or pom is None or area is None:
        raise ValueError('Planning inventory sections missing or changed')
    sections = [_section(h) for h in (norm, pom, area)]
    # The current inventory is unpaginated. Fail closed if this changes, rather
    # than quietly emitting only the first page. News pagination is out of scope.
    for nodes in sections:
        for node in nodes:
            if getattr(node, 'attrs', None) and (
                'next' in node.get('rel', []) or
                any(re.search(r'paginat|paginator|pagebrowser', c, re.I) for c in node.get('class', []))
            ):
                raise ValueError('Planning pagination requires explicit traversal')
    rows = {}
    for node in sections[0]:
        if getattr(node, 'name', None) != 'div' or 'card-file' not in node.get('class', []):
            continue
        link = node.select_one('.card-file__title a[href]')
        if link is None:
            raise ValueError('Malformed inventory card')
        title = _text(link)
        if not re.match(r'^(Modificación Puntual|Sector Industrial|Sector Residencial)\b', title):
            continue  # Generic building ordinance is not a specific instrument.
        docs = _documents(node.find_all('a'), url)
        row = _record(title, docs[0]['url'], docs, url)
        stamp = node.find('time')
        if stamp is not None:
            row['fecha_catalogo'] = _date(stamp['datetime'])
        rows[row['id']] = row

    project_headings = [pom] + [n for n in sections[2] if getattr(n, 'name', None) == 'h3'
                               and _text(n).startswith('Proyecto de ')]
    if len(project_headings) < 3:
        raise ValueError('A3 project headings missing')
    for heading in project_headings:
        nodes = _section(heading)
        paragraphs = [_text(n) for n in nodes if getattr(n, 'name', None) == 'p' and not n.find('a')]
        description = '\n'.join(paragraphs)
        title = _text(heading)
        docs = _documents(nodes, url)
        row = _record(title, title.casefold(), docs, url, description)
        if heading is pom:
            approved = re.search(r'Aprobado definitivamente.*?de fecha (\d{1,2} de \w+ de \d{4})', description)
            published = re.search(r'publicado en el DOCM.*?de fecha (\d{1,2} de \w+ de \d{4})', description)
            if approved:
                row['fecha_acuerdo'] = row['fecha_aprob'] = _date(approved[1])
                row['fase'] = 'aprobación definitiva'
            if published:
                row['fecha_publicacion'] = _date(published[1])
        else:
            agreement = re.search(r'Junta de Gobierno Local de fecha (\d{1,2} de \w+ de \d{4})', description, re.I)
            if agreement:
                row['fecha_acuerdo'] = _date(agreement[1])
            if 'se aprueba definitivamente el Proyecto de Urbanización' in description:
                row['fase'] = 'aprobación definitiva'
                row['fecha_aprob'] = row['fecha_acuerdo']
            # 06/10/2025 is ambiguously labelled "Acuerdo" in the HTML;
            # do not reinterpret it as publication. Bulletin verified in RESEARCH.
        rows[row['id']] = row
    if not rows:
        raise ValueError('No genuine planning records found')
    return list(rows.values())


class ArgamasillaDeAlbaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': 'municipio-argamasilla-de-alba/1.0 (public planning inventory)'})
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        capture_dir = self.config.get('evidence_dir')
        if capture_dir:
            Path(capture_dir).mkdir(parents=True, exist_ok=True)
            Path(capture_dir, 'urbanismo.html').write_text(response.text, encoding='utf-8')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE],
                'coverage': 'current_municipal_planning_inventory', 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
