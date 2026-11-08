"""Pego's published planning-document inventory, grouped by instrument.

This is an archive snapshot, not a claim of current legal validity or licences.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://pego.org/area/urbanisme-i-medi-ambient/'
GROUPS = {
    'Revisió del Pla General Ordenació Urbana de Pego': ('pgou-revisio', 'plan_general'),
    "Pla parcial modificatiu d'alineacions del sector Calvari I": ('calvari-i', 'plan_parcial'),
    'Modificacions puntuals': (None, 'modificacion_planeamiento'),
    'Plans Especials': (None, 'plan_especial'),
}
EXCLUDED = {"Béns d'interès cultural", 'Normativa'}


def publication_date(label):
    """Only bulletin labels supply publication dates; upload paths never do."""
    if not re.match(r'^(?:BOP|DOGV|DOCV)\b', label):
        return None
    iso = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', label)
    dmy = re.search(r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b', label)
    if not iso and not dmy:
        return None
    try:
        return (date(*map(int, iso.groups())) if iso else
                date(int(dmy[3]), int(dmy[2]), int(dmy[1]))).isoformat()
    except ValueError as exc:
        raise ValueError(f'Invalid bulletin publication date: {label}') from exc


def document_url(href):
    if href.startswith('#elementor-action'):
        try:
            decoded = unquote(href)
            encoded = decoded.split('settings=', 1)[1]
            url = json.loads(base64.b64decode(encoded, validate=True))['url']
        except (ValueError, KeyError, IndexError) as exc:
            raise ValueError('Changed Elementor document link') from exc
    else:
        url = urljoin(SOURCE, href)
    parsed = urlparse(url)
    if parsed.scheme not in {'https', 'http'} or not parsed.netloc or parsed.fragment:
        raise ValueError(f'Unsupported planning document URL: {url}')
    return url


class PegoAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='pego', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://pego.org')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.find('h2', string=lambda s: s and s.strip() == 'Pla General Ordenació Urbana')
        if heading is None:
            raise ValueError('Missing municipal planning inventory heading')
        accordion = heading.find_next('div', class_='e-n-accordion')
        if accordion is None:
            raise ValueError('Missing planning accordion')
        if soup.select('link[rel~=next], a[rel~=next]'):
            raise ValueError('Source pagination requires crawler review')
        for a in accordion.select('a[href]'):
            if ('next' in a.get('rel', []) or
                    a.get_text(' ', strip=True).lower() in {'siguiente', 'següent', 'next'}):
                raise ValueError('Planning inventory pagination requires crawler review')
        if accordion.select('[data-next-page], .pagination, .load-more'):
            raise ValueError('Planning inventory pagination requires crawler review')
        rows, seen = {}, set()
        for block in accordion.find_all('details', recursive=False):
            summary = block.find('summary', recursive=False)
            if summary is None:
                raise ValueError('Planning inventory item without heading')
            group = summary.get_text(' ', strip=True)
            if group in EXCLUDED:
                continue
            if group not in GROUPS or group in seen:
                raise ValueError(f'Unreviewed or duplicate planning group: {group}')
            seen.add(group)
            key, kind = GROUPS[group]
            group_start_count = len(rows)
            current = None

            def start(identity, title):
                if identity in rows:
                    raise ValueError(f'Duplicate planning instrument: {identity}')
                row = {
                    'id': 'pego-proy-' + identity,
                    'municipio': 'Pego', 'codigo_ine': '03102', 'provincia': 'Alicante',
                    'titulo': title, 'tipo': kind, 'fase': None,
                    'fecha': None, 'fecha_publicacion': None,
                    'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': SOURCE, 'source': 'ayuntamiento',
                    'origen': 'inventario_documental_planeamiento',
                    'source_entity_type': 'documento',
                    'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                    'publication_ready': False,
                    'coverage': 'Partial municipal planning archive; legal validity not verified',
                }
                rows[identity] = row
                return row

            if key:
                current = start(key, group)
            for node in block.find_all(['h3', 'a']):
                if node.name == 'h3':
                    title = node.get_text(' ', strip=True)
                    if group == 'Modificacions puntuals' and title.startswith('MP '):
                        match = re.match(r'^MP (\d+)\b', title)
                        if not match:
                            raise ValueError('Unrecognized modification heading')
                        current = start('mp-' + str(int(match[1])).zfill(2), title)
                    elif group == 'Plans Especials' and title.startswith('Pla Especial'):
                        match = re.match(r'^Pla Especial Num\. (\d+)\b', title)
                        if not match:
                            raise ValueError('Unrecognized special-plan heading')
                        current = start('pla-especial-' + match[1], title)
                    continue
                href = node['href'] if node.has_attr('href') else ''
                if not href:
                    continue
                if current is None:
                    raise ValueError('Document not assigned to a planning instrument')
                label = node.get_text(' ', strip=True) or node.get('aria-label', '')
                if not label:
                    raise ValueError('Planning document without label')
                url = document_url(href)
                if any(d['url'] == url for d in current['documentos']):
                    continue  # Icon and text anchors are the same document.
                current['documentos'].append({
                    'titulo': label, 'url': url, 'source_url': SOURCE,
                    'source_href': href, 'fecha_publicacion': publication_date(label),
                    'hosting': ('municipal' if urlparse(url).hostname in {'pego.org', 'www.pego.org'}
                                else 'external_linked_by_municipality'),
                })
            if len(rows) == group_start_count:
                raise ValueError('Planning group without instruments')
        if seen != set(GROUPS) or not rows:
            raise ValueError('Incomplete planning inventory groups')
        for row in rows.values():
            if not row['documentos']:
                raise ValueError('Planning instrument without documents')
            dates = sorted({d['fecha_publicacion'] for d in row['documentos'] if d['fecha_publicacion']})
            row['fechas_publicacion_documentos'] = dates
            # Multiple bulletin dates remain attached to their respective documents.
            row['fecha_publicacion'] = dates[0] if len(dates) == 1 else None
        return list(rows.values())

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        request = Request(SOURCE, headers={'User-Agent': self.config.get('user_agent', 'municipio-pego/1.0')})
        with urlopen(request, timeout=45) as response:
            content = response.read(4_000_001)
            if len(content) > 4_000_000:
                raise ValueError('Planning inventory exceeds response limit')
            if urlparse(response.url).hostname not in {'pego.org', 'www.pego.org'}:
                raise ValueError('Inventory redirected away from municipality')
            html = content.decode(response.headers.get_content_charset() or 'utf-8')
        rows = self.parse_projects(html)
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanisme.html').write_bytes(content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'source_sha256': hashlib.sha256(content).hexdigest(), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Refresh the entire unpaginated inventory; state does not filter records.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
