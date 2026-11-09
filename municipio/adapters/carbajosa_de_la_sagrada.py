"""Snapshot of the official urbanismo inventory; documents grouped by instrument."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://carbajosadelasagrada.es/urbanismo/'


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


def date_value(value):
    day, month, year = map(int, re.split(r'[/\-]', value))
    if year < 100:
        year += 2000
    return date(year, month, day).isoformat()


DATE = r'\d{1,2}[/\-]\d{1,2}[/\-](?:\d{4}|\d{2})\b'


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find('h2', string=re.compile('PLAN GENERAL DE ORDENACIÓN URBANA'))
    if heading is None:
        raise ValueError('Official planning inventory heading missing')
    content = heading.find_parent('div', class_='margin-bottom-30')
    if content is None:
        raise ValueError('Official inventory container missing')
    # This inventory is a complete static page. Fail closed if pagination appears.
    if soup.select('[rel~=next], .pagination, .pager'):
        raise ValueError('Pagination appeared; inventory coverage needs review')
    groups = {}
    current = None
    pending = None
    for block in content.select('h2, p, li'):
        text = ' '.join(block.get_text(' ', strip=True).split())
        if not text:
            continue
        n = norm(text)
        links = [a for a in block.select('a[href]') if a.get_text(' ', strip=True)]
        is_heading = (block.name == 'h2' or
                      (not links and re.search(r'PLAN|PROYECTO|ESTUDIO|MODIFICACIÓN|CONVENIO', text)) or
                      (links and (n.startswith('modificacion') and 'bocyl' in n or
                                  n.startswith('peri sector') or
                                  n.startswith('proyecto de actuacion de la u.a.'))))
        if is_heading:
            # Initial/final notices for the same instrument share its identity.
            if 'convenio urbanistico' in n:
                current = None  # management agreement is outside this inventory's scope
                pending = None
                continue
            if 'estudio de detalle' in n:
                identity = re.sub(r'^.*?estudio de detalle', 'estudio de detalle', n)
            elif 'proyecto de normalizacion' in n:
                identity = re.sub(r'^.*?proyecto de normalizacion', 'proyecto de normalizacion', n)
            else:
                identity = n
            identity = re.split(r'\s*\(|:\s*$|\. aprobacion| aprobacion definitiva', identity)[0].strip()
            identity = re.sub(r'^anuncio aprobacion (?:inicial|definitiva)\s+', '', identity)
            title = re.split(r'\s*\(|\. Aprobación| Aprobación definitiva', text)[0].rstrip(': ')
            key = hashlib.sha256(identity.encode()).hexdigest()[:16]
            current = groups.setdefault(key, {
                'id': 'carbajosa-plan-' + key, 'titulo': title,
                'municipio': 'Carbajosa de la Sagrada', 'codigo_ine': '37085',
                'provincia': 'Salamanca', 'tipo': 'instrumento o proyecto urbanístico',
                'url': url, 'inventory_url': url, 'source': 'ayuntamiento',
                'origen': 'inventario_planeamiento', 'source_entity_type': 'documento',
                'documentos': [], 'source_statements': [],
                'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'geometry_status': 'unavailable',
            })
            pending = text
        elif not links and 'aprobado definitivamente por orden' in n and current:
            pending = text
        if current is None:
            continue
        if is_heading or (not links and 'aprobado definitivamente por orden' in n):
            current['source_statements'].append(text)
            if 'definitiva' in n or 'definitivamente' in n:
                current['fase'] = 'aprobación definitiva'
            elif 'aprobacion inicial' in n:
                current.setdefault('fase', 'aprobación inicial')
            # Only dates explicitly tied to BOCyL publication or approval.
            pub = re.search(r'bocyl[^()]*?(' + DATE + ')', n)
            approval = re.search(r'(?:acuerdo de pleno de|aprobacion definitiva)\s+(' + DATE + ')', n)
            if pub:
                current['fecha_publicacion'] = date_value(pub[1])
            if approval:
                current['fecha_aprob'] = date_value(approval[1])
                if 'acuerdo de pleno de' in n:
                    current['fecha_acuerdo'] = date_value(approval[1])
        for a in links:
            target = urljoin(url, a['href'])
            parsed = urlparse(target)
            if parsed.hostname not in ('carbajosadelasagrada.es', 'drive.google.com'):
                raise ValueError('Unexpected document host: ' + target)
            doc = {'titulo': a.get_text(' ', strip=True), 'url': target,
                   'provenance_url': url, 'contexto': pending or text}
            if not any(d['url'] == target for d in current['documentos']):
                current['documentos'].append(doc)
    rows = list(groups.values())
    if not rows or any(not row['documentos'] for row in rows):
        raise ValueError('Empty instrument or missing documentary links')
    return rows


class CarbajosaDeLaSagradaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        response = requests.get(SOURCE, timeout=60, headers={
            'User-Agent': 'municipio-inventory/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(SOURCE).hostname:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_text(response.text, encoding='utf-8')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'source_urls': [response.url],
                'coverage': 'current_static_planning_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
