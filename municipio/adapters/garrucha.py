"""Garrucha's official planning inventories (Domino/XPages category trees)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.garrucha.es'
INVENTORIES = tuple(
    BASE + '/Servicios/cmsdipro/index.nsf/tablon_view_categoria1.xsp?' +
    urlencode({'cat': category, 'p': 'Garrucha'})
    for category in ('Normas', 'Normas en Trámite de Aprobación')
)
PLANNING_TITLE = re.compile(
    r'^(?:AVANCE PLAN GENERAL|PLAN GENERAL|PLAN PARCIAL|PLAN ESPECIAL|'
    r'ESTUDIO DE DETALLE|MODIFICACI[OÓ]N (?:PUNTUAL|DEL PLAN)|'
    r'PROYECTO DE (?:URBANIZACI[OÓ]N|REPARCELACI[OÓ]N))\b', re.I
)


def official_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.netloc == 'www.garrucha.es'


def document_id(url: str) -> str:
    parsed = urlparse(url)
    ident = parse_qs(parsed.query).get('documentId', [''])[0]
    if (not official_url(url) or not parsed.path.endswith('/tablon.xsp') or
            parse_qs(parsed.query).get('p') != ['Garrucha'] or
            not re.fullmatch(r'[0-9A-Fa-f]{32}', ident)):
        raise ValueError('Unexpected municipal notice URL: ' + url)
    return ident.upper()


def parse_inventory(html: str, url: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    panel = soup.select_one('#cmsdip-pro-tablon-view1')
    if panel is None:
        raise ValueError('Missing official inventory panel')
    # Do not accept a silently truncated inventory after a portal layout change.
    for control in panel.select('a, button, input'):
        label = ' '.join((control.get_text(' ', strip=True), control.get('title', ''),
                          control.get('aria-label', ''), control.get('value', '')))
        classes = ' '.join(control.get('class', []))
        if (control.has_attr('disabled') or control.get('aria-disabled') == 'true'):
            continue
        if ('xspPager' in classes or control.get('rel') == ['next'] or
                re.search(r'\b(?:siguiente|next|última|last|página siguiente)\b', label, re.I) or
                control.find_parent(class_=re.compile('xspDataTableViewPanelFooter'))):
            raise ValueError('Inventory pagination requires explicit traversal; refusing partial output')
    rows = {}
    for anchor in panel.select('a[href]'):
        title = anchor.get_text(' ', strip=True)
        if not PLANNING_TITLE.match(title):
            continue
        target = urljoin(url, anchor['href'])
        ident = document_id(target)
        rows[ident] = {'id': 'garrucha-plan-' + ident.lower(), 'titulo': title,
                       'url': BASE + '/Servicios/cmsdipro/index.nsf/tablon.xsp?' +
                       urlencode({'p': 'Garrucha', 'documentId': ident}),
                       'inventory_url': url}
    return list(rows.values())


def parse_detail(html: str, row: dict) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('#doc-dipalme-titulo h1')
    if heading is None or heading.get_text(' ', strip=True) != row['titulo']:
        raise ValueError('Notice title does not match inventory')
    text = soup.get_text(' ', strip=True)
    if 'Ayuntamiento de Garrucha' not in text or 'Planeamiento Urbanístico' not in text:
        raise ValueError('Missing municipality/planning provenance')
    published = re.search(r'Publicado:\s*(\d{2}/\d{2}/\d{4})', text)
    if not published:
        raise ValueError('Missing explicit publication date')
    documents = {}
    for anchor in soup.select('#attachments a[href]'):
        target = urljoin(row['url'], anchor['href'])
        if not official_url(target) or '/Servicios/Tablon/anexos.nsf/' not in target or '/$file/' not in target:
            raise ValueError('Unexpected attachment URL')
        documents.setdefault(target, {'titulo': anchor.get('title') or anchor.get_text(' ', strip=True),
                                      'url': target, 'source_url': row['url']})
    if not documents:
        raise ValueError('Planning instrument has no attached documents')
    body = soup.select_one('[id$="fanuncio_Texto1"]')
    description = body.get_text(' ', strip=True) if body else ''
    phase = None
    if row['titulo'].upper().startswith('AVANCE PLAN GENERAL'):
        phase = 'avance'
    elif re.search(r'APROBACI[OÓ]N DEFINITIVA', description, re.I):
        phase = 'aprobacion_definitiva'
    result = {**row, 'municipio': 'Garrucha', 'codigo_ine': '04049', 'provincia': 'Almería',
              'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
              'origen': 'inventario_planeamiento', 'descripcion': description,
              'fecha_publicacion': datetime.strptime(published[1], '%d/%m/%Y').date().isoformat(),
              'fecha_acuerdo': None, 'fecha_aprob': None,
              'documentos': list(documents.values()), 'geometry_status': 'unavailable',
              'publication_ready': False}
    if phase:
        result['fase'] = phase
    return result


def expansion(html: str, root: str | None) -> tuple[str, str] | None:
    """Return a read-only category expansion event, restricted to planning's subtree."""
    soup = BeautifulSoup(html, 'html.parser')
    panel = soup.select_one('#cmsdip-pro-tablon-view1')
    if panel is None:
        raise ValueError('Missing category tree')
    for button in panel.select('button[id][title]'):
        if not button['title'].startswith('plegado '):
            continue
        match = re.search(r'__expand:([\d.]+)button$', button['id'])
        if not match:
            raise ValueError('Unknown category expansion format')
        position = match[1]
        if ((root is None and button['title'] == 'plegado Planeamiento Urbanístico') or
                (root is not None and position.startswith(root + '.'))):
            return button['id'][:-len('button')], root or position
    return None


class GarruchaAyuntamientoAdapter(AyuntamientoAdapter):
    def _capture(self, name: str, html: str) -> None:
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_text(html, encoding='utf-8')

    @staticmethod
    def _response(response):
        response.raise_for_status()
        if not official_url(response.url):
            raise ValueError('Unexpected portal redirect')
        return response.text

    def _inventory(self, session, url: str, number: int) -> list[dict]:
        html = self._response(session.get(url, timeout=45))
        root = None
        seen = set()
        for step in range(100):
            self._capture(f'inventory-{number}-{step}.html', html)
            rows = parse_inventory(html, url)  # Check pagination on every response.
            event = expansion(html, root)
            if event is None:
                if root is None or not rows:
                    raise ValueError('Planning branch absent or empty; review source coverage')
                return rows
            event_id, root = event
            if event_id in seen:
                raise ValueError('Category expansion did not advance')
            seen.add(event_id)
            soup = BeautifulSoup(html, 'html.parser')
            form = soup.select_one('form.xspForm')
            if form is None:
                raise ValueError('Missing XPages form')
            data = {a['name']: a.get('value', '') for a in form.select('input[name]')}
            data['$$xspsubmitid'] = event_id
            # XPages POST changes only the displayed category expansion state.
            html = self._response(session.post(url, data=data, timeout=45))
        raise ValueError('Category safety limit reached; refusing truncated inventory')

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = {}
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-garrucha-inventory/1.0'
            for number, url in enumerate(INVENTORIES):
                for row in self._inventory(session, url, number):
                    if row['id'] in rows:
                        continue
                    html = self._response(session.get(row['url'], timeout=45))
                    self._capture(row['id'] + '.html', html)
                    rows[row['id']] = parse_detail(html, row)
        return {**self._write(out_jsonl, list(rows.values())),
                'source_urls': list(INVENTORIES), 'coverage': 'current_planning_inventory',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full replacement snapshot; no unsupported claim of historical/incremental coverage.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**self._write(out_jsonl, []), 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
