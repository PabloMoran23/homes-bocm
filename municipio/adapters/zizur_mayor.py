"""Zizur Mayor's published planning document inventories; no licence inference."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.zizurmayor.es'
INVENTORY = BASE + '/plan-municipal/'
EXPOSURE = BASE + '/ayuntamiento/exposicion-publica-de-normativas/'
MONTHS = dict(zip(('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split(), range(1, 13)))
LIMITATIONS = [
    'Partial coverage: published Plan Municipal/Ardoi inventory and the new PUM exposure only; no complete municipal project or licence register.',
    'Some historical graphical documents are available only at municipal offices. Linked files are retained, not interpreted as separate projects.',
    'BON dates are publication dates; only the explicit PUM plenary session supplies an agreement date. Upload paths and text-refundido years are not approval dates.',
    'No verified vector geometry or coordinates. Current exposure page does not establish that the consultation period remains open.',
    'Document URLs are preserved from the inventory; continuing availability of every historical attachment is not guaranteed.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.select('a[href]'):
        if (set(a.get('rel', [])) & {'next'} or
                re.fullmatch(r'siguiente|next|hurrengoa|[»›]', _text(a), re.I) or
                a.find_parent(class_=re.compile(r'pagination|paginacion|nav-links', re.I))):
            if a['href'] not in ('', '#'):
                raise ValueError('Pagination detected: review traversal before accepting partial output')
    content = soup.select_one('main .contenido.content')
    if content is None:
        raise ValueError('Missing official inventory content')
    return content


def _doc(a, source):
    target = urljoin(source, a['href'])
    parsed = urlparse(target)
    if parsed.scheme not in {'https', 'http'} or parsed.hostname not in {'www.zizurmayor.es', 'www.navarra.es', 'bon.navarra.es'}:
        raise ValueError('Unexpected planning document URL: ' + target)
    return {'titulo': _text(a), 'url': target, 'source_url': source}


def _row(title, key, source):
    return {'id': 'zizur-mayor-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Zizur Mayor / Zizur Nagusia', 'codigo_ine': '31907',
            'provincia': 'Navarra', 'titulo': title, 'tipo': 'planeamiento_urbanistico',
            'url': source, 'inventory_url': source, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_planeamiento', 'documentos': [],
            'geometry_status': 'unavailable', 'publication_ready': False}


def _spanish_date(text):
    m = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', text, re.I)
    if not m:
        raise ValueError('Missing explicit Spanish date: ' + text)
    return date(int(m[3]), MONTHS[m[2].lower()], int(m[1])).isoformat()


def parse_inventory(html, source=INVENTORY):
    content = _content(html)
    content = content.select_one('.mt-3') or content
    rows, by_key = [], {}
    current = None
    headings = {'PLAN MUNICIPAL:': 'Plan Municipal de Zizur Mayor / Zizur Nagusia',
                'PLAN PARCIAL DEL SECTOR ARDOI:': 'Plan Parcial del Sector Ardoi'}
    seen_headings = set()
    for node in content.find_all(['p', 'li']):
        if node.name == 'p':
            label = _text(node).upper()
            if label in headings:
                seen_headings.add(label)
                current = _row(headings[label], label, source)
                rows.append(current)
            continue
        # Nested modifications have their own li; do not attach their docs/dates to the parent.
        links = [a for a in node.select('a[href]') if a.find_parent('li') is node]
        if not links:
            continue
        title = _text(links[0])
        if re.match(r'^Modificaci[oó]n\b', title, re.I):
            first = _doc(links[0], source)
            key = first['url']
            current_mod = by_key.get(key)
            if current_mod is None:
                current_mod = _row(title, key, source)
                current_mod['url'] = key
                rows.append(current_mod)
                by_key[key] = current_mod
            own = BeautifulSoup(str(node), 'html.parser').li
            for nested in own.find_all(['ul', 'ol']):
                nested.decompose()
            own_text = _text(own)
            match = re.search(r'Publicad[ao] en el BON.*', own_text, re.I)
            if match:
                current_mod['fecha_publicacion'] = _spanish_date(match[0])
                current_mod['fecha_publicacion_fuente'] = match[0]
            target = current_mod
        else:
            target = current
            if target is None:
                raise ValueError('Document outside a recognised planning instrument')
        for a in links:
            doc = _doc(a, source)
            if doc['url'] not in {d['url'] for d in target['documentos']}:
                target['documentos'].append(doc)
    if seen_headings != set(headings) or any(not row['documentos'] for row in rows):
        raise ValueError('Incomplete planning inventory')
    return rows


def parse_exposure(html, source=EXPOSURE):
    content = _content(html)
    headings = [p for p in content.select('p') if p.select_one('strong') and
                re.match(r'^Aprobación inicial del Plan Urbanístico Municipal', _text(p))]
    if len(headings) != 1:
        raise ValueError('PUM exposure heading missing or ambiguous')
    block = headings[0].parent
    text = _text(block)
    agreement = re.search(r'por acuerdo adoptado por el Pleno en sesión de fecha ([^.]+)', text)
    if not agreement:
        raise ValueError('PUM explicit agreement provenance missing')
    row = _row(_text(headings[0]), 'PUM-aprobacion-inicial', source)
    row.update(fase='aprobacion_inicial', fecha_acuerdo=_spanish_date(agreement[1]),
               fecha_acuerdo_fuente=agreement[0])
    for a in block.select('a[href]'):
        doc = _doc(a, source)
        if not urlparse(doc['url']).path.lower().endswith('.pdf'):
            raise ValueError('Unexpected PUM annex format')
        if doc['url'] not in {d['url'] for d in row['documentos']}:
            row['documentos'].append(doc)
    if not row['documentos']:
        raise ValueError('PUM exposure has no documents')
    return [row]


class ZizurMayorAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'MunicipalPlanningInventory/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != 'www.zizurmayor.es':
            raise ValueError('Unexpected inventory redirect')
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            name = urlparse(url).path.strip('/').replace('/', '-')
            (capture / (name + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(output)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        rows = parse_inventory(self._fetch(INVENTORY))
        rows.extend(parse_exposure(self._fetch(EXPOSURE)))
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [INVENTORY, EXPOSURE], 'limitations': LIMITATIONS,
                'coverage': 'published_planning_document_inventories', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
