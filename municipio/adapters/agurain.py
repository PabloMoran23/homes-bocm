"""Agurain's development-planning inventory; one record per instrument.

Uses existing requests/BeautifulSoup and the installed pdftotext executable for
BOTHA documents. No licence, procurement or news discovery is performed.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://agurain.eus/es/servicios-municipales/urbanismo"
MONTHS = dict(zip("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), range(1, 13)))
LIMITATIONS = [
    "Only the complete Planeamiento de desarrollo card, not a municipality-wide historical inventory.",
    "PGOU, general-plan modifications, municipal works and urban-management sections are outside this adapter's scope.",
    "Cemetery register currently has no approval date or downloadable documents.",
    "Register BOTHA labels are retained verbatim, not treated as verified publication dates; Opakua label and URL years disagree.",
    "Linked technical files are retained as document links, not downloaded or interpreted as separate projects.",
    "No granted-licence register or verified project geometry; dates absent from sources remain null.",
]


def _no_pagination(node):
    for a in node.select('a[href]'):
        if ("next" in a.get("rel", []) or
                a.get_text(" ", strip=True).lower() in {"siguiente", "next", "hurrengoa", "siguiente página"}):
            if a['href'] not in {"", "#"}:
                raise ValueError("Planning inventory is paginated; extend crawler before extraction")
    if node.select_one('.pagination, .lfr-pagination, .pagination-bar'):
        raise ValueError("Unexpected planning pagination controls")


def parse_inventory(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = [p.parent for p in soup.select('.content > .title')
             if p.get_text(' ', strip=True) == 'Planeamiento de desarrollo']
    if len(cards) != 1:
        raise ValueError("Missing or ambiguous development-planning card")
    _no_pagination(cards[0])
    # A page-level next relation would also make a single-page snapshot unsafe.
    if soup.select_one('link[rel="next"], a[rel="next"]'):
        raise ValueError("Unexpected next page")
    body = cards[0].select_one('.content_basic')
    if body is None:
        raise ValueError("Missing planning list")
    entries = {}
    for a in body.select('a[href]'):
        title = a.get_text(' ', strip=True)
        url = urljoin(SOURCE, a['href'])
        parsed = urlparse(url)
        registry = (parsed.hostname == 'web.araba.eus' and
                    re.fullmatch(r'/es/urbanismo/planeamiento-urbanistico/-/reg/\d{4}-\d+', parsed.path))
        bulletin = (parsed.hostname == 'www.araba.eus' and
                    re.fullmatch(r'/botha/boletines/\d{4}/\d+/\d{4}_\d+_\d+_c.pdf', parsed.path.lower()))
        if not title or not (registry or bulletin) or 'plan especial' not in title.lower():
            raise ValueError(f"Unreviewed planning link: {title} {url}")
        entries.setdefault(url, {'titulo': title, 'url': url, 'kind': 'registry' if registry else 'bulletin'})
    if not entries:
        raise ValueError("Empty planning inventory")
    return list(entries.values())


def _base(asiento, title, url):
    year, number = asiento.split('/')
    return {
        'id': f'agurain-plan-{year}-{int(number):03d}',
        'municipio': 'Agurain / Salvatierra', 'codigo_ine': '01051', 'provincia': 'Álava',
        'titulo': title, 'tipo': 'plan especial', 'numero_asiento': asiento,
        'url': url, 'source': 'ayuntamiento', 'origen': 'planeamiento_de_desarrollo',
        'url_inventario': SOURCE, 'fecha': None, 'fecha_publicacion': None,
        'fecha_acuerdo': None, 'fecha_aprob': None, 'fase': None,
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'documentos': [],
    }


def parse_registry(html, entry):
    soup = BeautifulSoup(html, 'html.parser')
    marker = soup.find('dt', string='Número de asiento')
    body = marker.find_parent('div', class_='container') if marker else None
    if body is None or body.select_one('h2') is None:
        raise ValueError('Missing registry detail')
    _no_pagination(body)
    fields = {}
    for dt in body.select('dt'):
        dd = dt.find_next_sibling('dd')
        if dd is None:
            raise ValueError('Malformed registry metadata')
        fields[dt.get_text(' ', strip=True)] = dd.get_text(' ', strip=True)
    asiento = fields.get('Número de asiento', '')
    if not re.fullmatch(r'\d{4}/\d+', asiento):
        raise ValueError('Missing official registry identity')
    year, number = asiento.split('/')
    expected = entry['url'].rsplit('/', 1)[-1]
    if f'{year}-{int(number):03d}' != expected:
        raise ValueError('Registry identity disagrees with requested URL')
    if fields.get('Municipio') not in {'Salvatierra', 'Agurain', 'Agurain/Salvatierra', 'Agurain / Salvatierra'}:
        raise ValueError('Registry belongs to another municipality')
    row = _base(asiento, body.select_one('h2').get_text(' ', strip=True), entry['url'])
    row.update(titulo_inventario=entry['titulo'], expediente=fields.get('Número de expediente') or None,
               metadatos_registro=fields, estado=fields.get('Estado') or None)
    raw_date = fields.get('Fecha de aprobación')
    if raw_date:
        row['fecha_aprob'] = datetime.strptime(raw_date, '%d/%m/%Y').date().isoformat()
    headings = [h.get_text(' ', strip=True) for h in body.select('h3')]
    if 'Aprobación definitiva' in headings and fields.get('Tipo de acuerdo') == 'APROBACIÓN':
        row['fase'] = 'aprobación definitiva'
    docs = {}
    for a in body.select('a[data-download], a[href]'):
        href = a.get('data-download') or a.get('href', '')
        url = urljoin(entry['url'], href)
        parsed = urlparse(url)
        if not (a.has_attr('data-download') or parsed.path.lower().endswith('.pdf')):
            continue
        if parsed.scheme != 'https' or parsed.hostname not in {'web.araba.eus', 'www.araba.eus'}:
            raise ValueError('Unexpected document host')
        docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                              'url_procedencia': entry['url']})
    row['documentos'] = list(docs.values())
    row['referencias_publicacion_registro'] = [d for d in docs.values() if 'BOTHA' in d['titulo']]
    return row


def _spanish_date(text):
    match = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', text.lower())
    if not match or match[2] not in MONTHS:
        raise ValueError('Unrecognized bulletin date')
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


def parse_bulletin(text, entry):
    text = ' '.join(text.split())
    # Require the act, municipality, named instrument and registry reference;
    # neither the signature date nor an environmental-report date is approval.
    if not all(s in text.lower() for s in ['ayuntamiento de agurain', 'aprobar definitivamente',
                                          'casco histórico de agurain', 'rehabilitación']):
        raise ValueError('Unverified planning bulletin')
    asiento = re.search(r'número de asiento (\d{4}/\d+)', text)
    agreement = re.search(r'en fecha (\d{1,2} de \w+ de \d{4}), se acordó', text)
    publication = re.search(r'(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo), (\d{1,2} de \w+ de \d{4}) [•·] Núm\.', text)
    if not asiento or not agreement or not publication:
        raise ValueError('Bulletin lacks unambiguous identity or dates')
    row = _base(asiento[1], entry['titulo'], entry['url'])
    row.update(fecha_publicacion=_spanish_date(publication[1]),
               fecha_acuerdo=_spanish_date(agreement[1]), fecha_aprob=_spanish_date(agreement[1]),
               fase='aprobación definitiva',
               documentos=[{'titulo': entry['titulo'], 'url': entry['url'], 'url_procedencia': SOURCE}],
               evidencia_fechas={'publicacion': publication[0], 'acuerdo': agreement[0]})
    return row


class AgurainAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, capture_name):
        with session.get(url, timeout=40, stream=True) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 10_000_000:
                    raise ValueError('Source exceeds 10 MB; no partial extraction written')
            data = bytes(data)
        if self.config.get('evidence_dir'):
            folder = Path(self.config['evidence_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / capture_name).write_bytes(data)
        return data

    def backfill_proyectos(self, out_jsonl):
        rows = {}
        sources = [SOURCE]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-agurain/1.0 (public planning inventory)'
            entries = parse_inventory(self._fetch(session, SOURCE, 'urbanismo.html').decode('utf-8'))
            for entry in entries:
                sources.append(entry['url'])
                if entry['kind'] == 'registry':
                    key = entry['url'].rsplit('/', 1)[-1]
                    data = self._fetch(session, entry['url'], f'registro-{key}.html')
                    row = parse_registry(data.decode('utf-8'), entry)
                else:
                    capture_name = 'botha-' + entry['url'].rsplit('/', 1)[-1]
                    data = self._fetch(session, entry['url'], capture_name)
                    if not data.startswith(b'%PDF-'):
                        raise ValueError('Expected a genuine BOTHA PDF')
                    with tempfile.TemporaryDirectory() as tmp:
                        pdf = Path(tmp) / 'bulletin.pdf'
                        pdf.write_bytes(data)
                        result = subprocess.run(['pdftotext', '-layout', str(pdf), '-'],
                                                check=True, capture_output=True, timeout=30)
                    row = parse_bulletin(result.stdout.decode('utf-8'), entry)
                if row['id'] in rows:
                    existing = rows[row['id']]
                    # A second link for an existing instrument is not another project.
                    if existing['fecha_aprob'] and row['fecha_aprob'] and existing['fecha_aprob'] != row['fecha_aprob']:
                        raise ValueError('Conflicting approval dates for one instrument')
                    for field in ('fecha_aprob', 'fecha_acuerdo', 'fecha_publicacion'):
                        existing[field] = existing[field] or row[field]
                    existing['documentos'] = list({d['url']: d for d in existing['documentos'] + row['documentos']}.values())
                else:
                    rows[row['id']] = row
        result = self._write(out_jsonl, list(rows.values()))
        return {**result, 'source_urls': sources, 'limitations': LIMITATIONS}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
