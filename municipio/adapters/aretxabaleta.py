"""Municipal planning/physical urbanisation instruments, not granted licences."""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://www.aretxabaleta.eus/es/departamentos/participacion/'
          'normas-en-proceso-de-creacion')
MONTHS = dict(zip('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), range(1, 13)))
LIMITATIONS = [
    'Partial municipal coverage: only spatial planning, mobility and urbanisation agreements in the municipal norms inventory; not all works or historical planning.',
    'Inventory categories are editorial status, not proof of definitive approval. All dated events retain their source paragraph; no single overall approval date is inferred.',
    'Dates without an explicit year remain in the source text only. No date is inferred from a PDF URL, metadata or retrieval time.',
    'Linked documents are retained with provenance, not parsed or guaranteed accessible. Iturrigorri currently has a municipal narrative but no document attachment.',
    'No verified geometry or coordinates, no granted licences. No automatic publication.',
    'Shared entity policy may mark these instruments pending because no administrative expediente number is exposed; scraper IDs are not expediente numbers.',
]


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def clean(tag):
    return ' '.join(tag.get_text(' ', strip=True).split())


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('#parent-fieldname-text')
    if body is None or not clean(body):
        raise ValueError('Missing municipal content')
    # The reviewed source is a full editorial page. Fail visibly if pagination
    # appears rather than silently returning the first page.
    for a in soup.select('a[href]'):
        if (a.get('rel') and 'next' in a['rel']) or re.search(r'(?i)(b_start(?::int)?|page|pagina)=', a['href']) or norm(clean(a)) in {'siguiente', 'next', 'hurrengoa', 'hurrengoa »', 'siguiente »'}:
            raise ValueError('Unreviewed pagination; inventory cannot be accepted as complete')
    if soup.select_one('.pagination, .batching, .listingBar'):
        raise ValueError('Unreviewed pagination container')
    return soup, body


def instrument_type(title):
    t = norm(title)
    if re.match(r'^\d+\s*[ºªo]?\s*modificacion puntual', t):
        return 'modificacion_planeamiento'
    if re.match(r'^estudio (?:de )?detalle', t):
        return 'estudio_de_detalle'
    if t.startswith('plan general de ordenacion urbana'):
        return 'plan_general'
    if t.startswith('plan de movilidad'):
        return 'plan_movilidad'
    if t.startswith('convenio urbanistico'):
        return 'convenio_urbanistico'
    return None


def explicit_dates(text):
    """Only complete dates; never supply a year from surrounding context."""
    matches = []
    for m in re.finditer(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', text):
        matches.append((m.start(), date(int(m[3]), int(m[2]), int(m[1])).isoformat()))
    for m in re.finditer(r'\b(\d{1,2}) de (\w+) (?:de|del) (\d{4})\b', norm(text)):
        if m[2] in MONTHS:
            matches.append((m.start(), date(int(m[3]), MONTHS[m[2]], int(m[1])).isoformat()))
    return list(dict.fromkeys(value for _, value in sorted(matches)))


class AretxabaletaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        _, body = content(html)
        section = None
        found_sections = set()
        rows = {}
        for tag in body.find_all(['h3', 'a']):
            title = clean(tag)
            if tag.name == 'h3':
                heading = norm(title)
                section = {'normas en tramitacion': 'en_tramitacion', 'normas tramitadas': 'tramitadas'}.get(heading)
                if section:
                    found_sections.add(section)
                continue
            kind = instrument_type(title)
            if not kind:
                continue
            url = urldefrag(urljoin(SOURCE + '/', tag.get('href', '')))[0].rstrip('/')
            if not section or not url.startswith(SOURCE + '/') or urlparse(url).query:
                raise ValueError('Unsupported instrument location or section')
            row = {'url': url, 'titulo_inventario': title, 'tipo': kind, 'situacion_inventario': section}
            if url in rows and rows[url] != row:
                raise ValueError('Conflicting inventory entries')
            rows[url] = row
        if found_sections != {'en_tramitacion', 'tramitadas'} or not rows:
            raise ValueError('Incomplete or empty municipal inventory')
        return list(rows.values())

    @staticmethod
    def parse_detail(html, entry):
        soup, body = content(html)
        heading = soup.select_one('h1.documentFirstHeading, h1')
        if heading is None or not instrument_type(clean(heading)) or instrument_type(clean(heading)) != entry['tipo']:
            raise ValueError('Detail does not describe the expected instrument')
        docs = {}
        for a in body.select('a[href]'):
            url = urldefrag(urljoin(entry['url'], a['href']))[0]
            parsed = urlparse(url)
            # Document resolver URLs are retained as published; never treat the
            # generic electronic registry / application links as documents.
            is_doc = (
                parsed.hostname == 'www.aretxabaleta.eus' and (parsed.path.lower().endswith('.pdf') or '/es/dokumentuak/' in parsed.path)
                or parsed.hostname in {'uzt.gipuzkoa.eus', 'udal.egoitza.gipuzkoa.eus'} and parsed.path.startswith('/PortalV/r/0/13/')
                or parsed.hostname == 'egoitza.gipuzkoa.eus' and parsed.path.startswith('/gao-bog/') and parsed.path.lower().endswith('.pdf')
            )
            if parsed.scheme not in {'https', 'http'} or not is_doc:
                continue
            label = clean(a)
            if label.startswith(('http://', 'https://')):
                label = clean(a.parent)
            label = label or 'Documento enlazado sin título'
            if url not in docs or docs[url]['titulo'] == 'Documento enlazado sin título':
                docs[url] = {'titulo': label, 'url': url, 'source_url': entry['url']}
        events = []
        # Leaf list items and paragraphs avoid duplicate enclosing list text.
        for block in body.find_all(['p', 'li']):
            if block.name == 'li' and block.find(['p', 'li']):
                continue
            text = clean(block)
            # A paragraph can contain both an agreement and its subsequent
            # publication. Classify each sentence separately, keeping context.
            for sentence in re.split(r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚ])', text):
                dates = explicit_dates(sentence)
                if not dates:
                    continue
                t = norm(sentence)
                role = 'fecha_mencionada'
                publication = re.search(r'\b(?:publicacion|publico|publicad[oa]s?)\b', t)
                if publication and ('bog' in t or 'b.o.g' in t or 'boletin' in t):
                    role = 'fecha_publicacion'
                elif 'firmo' in t:
                    role = 'fecha_firma'
                elif any(term in t for term in ('aprobo', 'acordo', 'fecha del acuerdo', 'fecha del decreto')):
                    role = 'fecha_acuerdo'
                # More than one full date in a sentence is ambiguous: retain
                # the dates as mentions rather than assign all the same role.
                if len(dates) > 1:
                    role = 'fecha_mencionada'
                events.append({'tipo_fecha': role, 'fechas': dates, 'texto': sentence,
                               'texto_contexto': text, 'source_url': entry['url']})
        description = body.get_text('\n', strip=True)
        if len(clean(body)) < 100:
            raise ValueError('Detail lacks substantive instrument information')
        return {
            **entry,
            'id': 'aretxabaleta-proy-' + hashlib.sha256(entry['url'].encode()).hexdigest()[:20],
            'municipio': 'Aretxabaleta', 'codigo_ine': '20013', 'provincia': 'Gipuzkoa',
            'titulo': clean(heading), 'source': 'ayuntamiento',
            'origen': 'inventario_municipal_normas', 'source_url': SOURCE,
            'descripcion': description, 'documentos': list(docs.values()), 'eventos': events,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'fase': None, 'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'documentacion_status': 'enlaces_documentales' if docs else 'solo_ficha_municipal',
        }

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        source_urls = []
        captures = []
        capture_dir = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-aretxabaleta/1.0 (public planning inventory)'

            def fetch(url):
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if response.url.rstrip('/') != url.rstrip('/'):
                    raise ValueError('Unexpected municipal redirect')
                if 'html' not in response.headers.get('Content-Type', '').lower():
                    raise ValueError('Expected municipal HTML')
                source_urls.append(url)
                if capture_dir:
                    directory = Path(capture_dir)
                    directory.mkdir(parents=True, exist_ok=True)
                    filename = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
                    (directory / filename).write_bytes(response.content)
                    captures.append({'url': url, 'file': filename, 'sha256': hashlib.sha256(response.content).hexdigest()})
                return response.text

            entries = self.parse_inventory(fetch(SOURCE))
            rows = []
            for entry in entries:
                time.sleep(.25)
                rows.append(self.parse_detail(fetch(entry['url']), entry))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': source_urls,
                'captures': captures, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Full editorial inventory snapshot, not a date-filtered partial update.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
