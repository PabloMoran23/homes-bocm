"""Campos' municipal planning chronology, fetched through its public Wicket tree."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://ajcampos.sedelectronica.es/citizen-service/e897c0dd-6e2d-4dc6-ae80-a06d6de5e2a9'
LIMITATIONS = [
    'Partial coverage: municipal general-planning chronology updated by its publisher to November 2025; no exhaustive works or licence register.',
    'Chronology item 3 is annulled and excluded; item 4 groups several Son Durí amendments without individual identities and is excluded.',
    'Dates are transcribed municipal assertions, not independently verified against gazette PDFs. Multiple agreement/publication dates remain arrays.',
    'The HTML chronology is the documentary source; it supplies no direct gazette/PDF links. No verified geometry or coordinates.',
]
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def check_pagination(soup):
    for a in soup.select('a, button'):
        if (set(a.get('rel', [])) & {'next', 'last'} or
                re.fullmatch(r'(següent|siguiente|next|últim[ao]?|last|[»›])', a.get_text(' ', strip=True), re.I) or
                any('paginat' in c.lower() or 'paginator' in c.lower() for c in a.get('class', []))):
            raise ValueError('Pagination detected; chronology crawler must be reviewed')


def parse_chronology(html):
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    content = soup.select_one('.informativePage .markdown')
    if content is None or 'RELACIÓ D’INSTRUMENTS DE PLANEJAMENT APROVATS' not in content.get_text(' ', strip=True):
        raise ValueError('Missing official approved-planning chronology')
    entries = []
    for p in content.select('p'):
        text = p.get_text(' ', strip=True)
        match = re.match(r'^(\d+)-\s*(.+)', text)
        if match:
            entries.append((int(match[1]), [match[2]], list(p.select('a[href]'))))
        elif entries and text:
            entries[-1][1].append(text)
            entries[-1][2].extend(p.select('a[href]'))
    if not entries or [n for n, _, _ in entries] != list(range(1, len(entries) + 1)):
        raise ValueError('Missing or duplicate chronological items')
    rows = []
    for number, paragraphs, links in entries:
        description = '\n'.join(paragraphs)
        title = paragraphs[0]
        if 'ANUL·LADA' in description:
            continue
        # Source item 4 combines several instruments: do not invent individual identities.
        if title.startswith('MODIFICACIONS PUNTUALS'):
            continue
        if not re.match(r'^(NORMES SUBSIDIÀRIES|MODIFICACIÓ PUNTUAL|CONFORMITAT AMB EL TEXT REFÒS)', title):
            raise ValueError('Unreviewed chronology instrument: ' + title)
        agreements = []
        for d, month, y in re.findall(r'(\d{1,2})\s+(?:DE |D[’\x27])([A-ZÀ-Ü]+)\s+DE\s+(\d{4})', title):
            value = date(int(y), MONTHS[month.lower()], int(d)).isoformat()
            if value not in agreements:
                agreements.append(value)
        publications = []
        for paragraph in paragraphs[1:]:
            if paragraph.startswith('PUBLICACIÓ:'):
                publications.extend(date(int(y), int(m), int(d)).isoformat()
                                    for d, m, y in re.findall(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', paragraph))
        key = hashlib.sha256(title.encode()).hexdigest()[:16]
        docs = [{'titulo': 'Cronologia informativa — entrada ' + str(number),
                 'url': SOURCE, 'seccion': 'Cronologia informativa', 'tipo': 'html',
                 'procedencia': 'Ajuntament de Campos; relato municipal de acuerdos y publicaciones'}]
        for a in links:
            target = urljoin(SOURCE, a['href'])
            if urlparse(target).scheme in {'https', 'http'} and a['href'] != '#':
                if target not in {doc['url'] for doc in docs}:
                    docs.append({'titulo': a.get_text(' ', strip=True), 'url': target})
        rows.append({
            'id': 'campos-plan-' + key, 'municipio': 'Campos', 'codigo_ine': '07013',
            'provincia': 'Illes Balears', 'titulo': title, 'descripcion': description,
            'tipo': 'planeamiento_urbanistico',
            'fase': 'conformidad con texto refundido' if title.startswith('CONFORMITAT') else 'aprobación definitiva',
            'fecha': None, 'fecha_acuerdo': agreements[0] if len(agreements) == 1 else None,
            'fecha_aprob': agreements[0] if len(agreements) == 1 and not title.startswith('CONFORMITAT') else None,
            'fechas_acuerdo': agreements,
            'fecha_publicacion': publications[0] if len(publications) == 1 else None,
            'fechas_publicacion': publications, 'url': SOURCE, 'inventory_url': SOURCE,
            'source': 'ayuntamiento', 'origen': 'cronologia_municipal_planeamiento',
            'source_item': number, 'source_section': 'Cronologia informativa', 'documentos': docs,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'unavailable',
        })
    if not rows:
        raise ValueError('No usable planning instruments')
    return rows


class CamposAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch_chronology(self):
        capture = self.config.get('capture_dir')
        if capture:
            Path(capture).mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-campos/1.0 (public planning inventory)'

            def fetch(url, name, ajax=False):
                headers = {'Wicket-Ajax': 'true', 'Wicket-Ajax-BaseURL': urlparse(SOURCE).path.lstrip('/')} if ajax else {}
                response = session.get(url, headers=headers, timeout=40)
                response.raise_for_status()
                if urlparse(response.url).hostname != urlparse(SOURCE).hostname:
                    raise ValueError('Unexpected external redirect')
                if capture:
                    (Path(capture) / name).write_text(response.text, encoding='utf-8')
                return response.text

            soup = BeautifulSoup(fetch(SOURCE, 'live-inventory.html'), 'html.parser')
            check_pagination(soup)
            # Expand both levels, using fresh session-bound actions rather than saved URLs.
            for depth in range(2):
                anchors = [a for a in soup.select('a[onclick]') if a.get_text(' ', strip=True) == 'Cronologia informativa']
                if len(anchors) != 1:
                    raise ValueError('Ambiguous/missing chronology tree node')
                match = re.search(r"wicketAjaxGet\('([^']+)'", anchors[0]['onclick'])
                if not match:
                    raise ValueError('Unsupported Wicket action')
                target = urljoin(SOURCE, match[1])
                if urlparse(target).hostname != urlparse(SOURCE).hostname:
                    raise ValueError('External Wicket action')
                xml = fetch(target, f'live-chronology-{depth}.xml', ajax=True)
                root = ET.fromstring(xml)
                components = [c.text or '' for c in root.findall('component')]
                if not components:
                    raise ValueError('Wicket response contains no content')
                fragments = '\n'.join(components)
                if depth == 0:
                    result = parse_chronology(fragments)
                    # The parent node already includes the full narrative. The child
                    # duplicates it on this site; verify it rather than emit it twice.
                    tree = BeautifulSoup(fragments, 'html.parser')
                    candidates = [a for a in tree.select('a[onclick]')
                                  if a.get_text(' ', strip=True) == 'Cronologia informativa'
                                  and 'nameLinkExpanded' not in a.get('class', [])]
                    if len(candidates) != 1:
                        raise ValueError('Chronology tree structure changed')
                    soup = BeautifulSoup(str(candidates[0]), 'html.parser')
                else:
                    child = parse_chronology(fragments)
                    if child != result:
                        raise ValueError('Chronology parent/child differ; review coverage')
            return result

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = self._fetch_chronology()
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory; forms excluded'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
