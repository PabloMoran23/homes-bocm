"""Punta Umbría: current public planning folders in the municipal e-office.

Wicket links are read as data, never executed. Plain GET resolves folders to
stable UUID URLs; 'Mostrar más' returns XML containing new HTML rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'umbria.sedelectronica.es'
SOURCE = f'https://{HOST}/transparency/fd6042f5-c1a2-4aa0-af1b-92906ac0cb95/'
INSTRUMENT = re.compile(
    r'^(?:ESTUDIO DE DETALLE|PROYECTO DE URBANIZACIÓN|APROBACIÓN PROYECTO DE ACTUACIÓN|'
    r'ACTUACIÓN TRANSFORMACIÓN URBANÍSTICA|REORDENACIÓN PARCELAS)', re.I
)


def official_url(base, href):
    url = urljoin(base, href)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != HOST:
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def action_url(element, base):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing Wicket navigation URL')
    return official_url(base, match[1])


def parse_page(text, base):
    """Parse full HTML or Wicket incremental components, preserving provenance."""
    if text.lstrip().startswith('<?xml'):
        root = ElementTree.fromstring(text)
        if root.tag != 'ajax-response':
            raise ValueError('Unexpected XML response')
        components = root.findall('component')
        if not components:
            raise ValueError('Missing pagination components')
        text = ''.join(c.text or '' for c in components)
    soup = BeautifulSoup(text, 'html.parser')
    entries = []
    for a in soup.select('td a.gIconLink'):
        title = a.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            match = re.search(r'\s*\(\s*(\d+)\s*\)\s*$', title)
            if not match:
                raise ValueError('Folder lacks advertised document count')
            entries.append({'kind': 'folder', 'titulo': title[:match.start()].strip(),
                            'count': int(match[1]), 'url': action_url(a, base)})
        else:
            url = official_url(base, a.get('href', ''))
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(url).path):
                raise ValueError('Unexpected document link')
            entries.append({'kind': 'document', 'titulo': title, 'url': url,
                            'descripcion_fuente': a.get('title', ''), 'inventory_url': base})
    buttons = [b for b in soup.select('button') if b.get_text(' ', strip=True) == 'Mostrar más'
               and not b.has_attr('disabled')]
    if len(buttons) > 1:
        raise ValueError('Ambiguous pagination')
    return entries, action_url(buttons[0], base) if buttons else None


def make_record(title, url, documents):
    if not documents:
        raise ValueError('Instrument without documents')
    return {
        'id': 'punta-umbria-plan-' + hashlib.sha256(url.encode()).hexdigest()[:20],
        'municipio': 'Punta Umbría', 'provincia': 'Huelva', 'codigo_ine': '21060',
        'titulo': title, 'tipo': 'instrumento o proyecto urbanístico',
        'url': url, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
        'origen': 'inventario_planeamiento_municipal',
        'documentos': [{k: v for k, v in d.items() if k != 'kind'} for d in documents],
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class PuntaUmbriaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, session, url):
        response = session.get(url, timeout=40)
        response.raise_for_status()
        official_url(response.url, response.url)
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = f'live-{len(self.captures):03}.html'
            (directory / name).write_text(response.text, encoding='utf-8')
            self.captures.append({'url': response.url, 'path': name})
        return response.text, response.url

    def _inventory(self, session, url):
        entries, seen, page, canonical = [], set(), url, None
        # A safety bound raises rather than silently returning partial coverage.
        for _ in range(100):
            text, base = self._get(session, page)
            if canonical is None:
                canonical = base
            chunk, next_url = parse_page(text, base)
            identities = {(e['kind'], e['url']) for e in chunk}
            if not chunk or len(identities) != len(chunk) or identities & seen:
                raise ValueError('Empty, repeated or duplicate inventory page')
            seen.update(identities)
            for entry in chunk:
                if entry['kind'] == 'document':
                    entry['inventory_url'] = canonical
            entries.extend(chunk)
            if not next_url:
                return entries, canonical
            page = next_url
        raise ValueError('Pagination exceeded safety bound; no output written')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.captures = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-punta-umbria/1.0 (public planning inventory)'
            entries, _ = self._inventory(session, SOURCE)
            rows, modification = [], []
            for entry in entries:
                if entry['kind'] == 'folder':
                    # Always inspect all planning folders; fail on a new unreviewed type.
                    if not INSTRUMENT.match(entry['titulo']):
                        raise ValueError('Unreviewed planning folder: ' + entry['titulo'])
                    documents, canonical = self._inventory(session, entry['url'])
                    if any(d['kind'] != 'document' for d in documents):
                        raise ValueError('Nested planning folder requires review')
                    if len(documents) != entry['count']:
                        raise ValueError('Advertised document count mismatch: ' + entry['titulo'])
                    rows.append(make_record(entry['titulo'], canonical, documents))
                elif re.search(r'MODIFICACIÓN PUNTUAL\s+(?:N[º°.]?\s*)?16\b',
                               entry['titulo'] + ' ' + entry['descripcion_fuente'], re.I):
                    modification.append(entry)
                elif 'Servicios de Temporada de Playas 2023' not in entry['descripcion_fuente']:
                    raise ValueError('Unreviewed loose planning document: ' + entry['titulo'])
            if modification:
                # Canonical, stable document identity, independent of listing order.
                url = min(d['url'] for d in modification)
                rows.append(make_record('Modificación puntual nº 16 del PGOU', url, modification))
            if not rows:
                raise ValueError('No usable planning instruments')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'coverage': 'current_planning_inventory_only',
                'source_urls': [SOURCE] + [r['url'] for r in rows], 'captures': self.captures,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot: the portal exposes no reliable modification cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
