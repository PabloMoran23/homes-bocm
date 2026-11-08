"""Rafelbunyol's official inventory of amendments to its planning rules."""
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

SOURCE = 'https://gobiernoabierto.rafelbunyol.es/t/planeamiento'
HOST = 'gobiernoabierto.rafelbunyol.es'
LIMITATIONS = [
    'Partial coverage: only Modificacions puntuals in the current planning inventory; '
    'not a complete history of projects, public works or licences.',
    'Portal Fecha values have unspecified semantics: retained per document as '
    'fecha_catalogo; publication and agreement dates remain null.',
    'Catalogue 8.2 is a second publication of amendment 8; catalogue 12 links '
    'the technical document of amendment 11. Original labels and links retained.',
    'Catalogue 7 contains a stray reference to 8; original label retained in documentos.',
    'No verified instrument geometry or coordinates; no geocoding or jitter.',
]


class RafelbunyolAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        # This reviewed inventory is a single, server-rendered document table.
        # Fail closed if it becomes paginated rather than silently losing pages.
        for a in soup.select('a[href]'):
            label = a.get_text(' ', strip=True).casefold()
            if ('next' in a.get('rel', []) or label in
                    {'siguiente', 'següent', 'next', '»', '›'} or
                    re.search(r'[?&](?:page|pagina)=', a['href'], re.I)):
                if a['href'] not in {'', '#'}:
                    raise ValueError('Planning inventory pagination requires crawler review')
        tables = []
        for body in soup.select('tbody'):
            cells = body.find_all('td', recursive=False)
            if cells and cells[0].get_text(' ', strip=True) == 'Modificacions puntuals':
                tables.append(cells)
        if len(tables) != 1 or len(tables[0]) != 2:
            raise ValueError('Expected one official amendments inventory')
        cell = tables[0][1]
        rows = {}
        for a in cell.select('a[href]'):
            paragraphs = []
            for sibling in a.previous_siblings:
                if getattr(sibling, 'name', None) == 'hr':
                    break
                if getattr(sibling, 'name', None) == 'p':
                    paragraphs.insert(0, sibling.get_text(' ', strip=True))
            if len(paragraphs) != 2:
                raise ValueError('Changed amendment document/date structure')
            title, date_label = paragraphs
            match = re.match(r'^Número (\d+(?:\.\d+)?) - (.+)$', title)
            if not match:
                raise ValueError('Unrecognized amendment title: ' + title)
            date_match = re.fullmatch(r'Fecha\s*:\s*(\d{2}-\d{2}-\d{4})', date_label)
            if not date_match:
                raise ValueError('Unrecognized catalogue date: ' + date_label)
            date = datetime.strptime(date_match[1], '%d-%m-%Y').date().isoformat()
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            if (parsed.scheme != 'https' or parsed.hostname != HOST or
                    not parsed.path.startswith('/storage/uploads/') or
                    not parsed.path.lower().endswith('.pdf')):
                raise ValueError('Unexpected official document URL: ' + url)
            number = match[1]
            note = None
            if number == '8.2':
                if not parsed.path.endswith('modificacion_puntual_8.2.pdf'):
                    raise ValueError('Review revised catalogue 8.2')
                number = '8'
                note = 'PDF is the DOGV notice for amendment 8 (PL-57/2006), not a new instrument.'
            elif number == '12':
                if not parsed.path.endswith('Mod_11_NNSS.pdf'):
                    raise ValueError('Review revised catalogue 12')
                number = '11'
                note = 'Catalogue says 12; reviewed PDF cover identifies MODIFICACIÓN Nº 11, JULIO 2010.'
            row = rows.setdefault(number, {
                'id': 'rafelbunyol-proy-mod-' + number,
                'municipio': 'Rafelbunyol', 'codigo_ine': '46207', 'provincia': 'Valencia',
                'titulo': 'Modificació puntual ' + number + ' de les normes subsidiàries de Rafelbunyol',
                'tipo': 'modificacion puntual de planeamiento', 'numero_modificacion': number,
                'expediente_grupo': 'Modificació puntual ' + number + ' de les normes subsidiàries',
                'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_vigente',
                'url': SOURCE, 'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'documentos': [], 'geometry': None, 'lat': None, 'lon': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            })
            document = {'titulo': title, 'url': url, 'fecha_catalogo': date,
                        'etiqueta_fecha_fuente': date_label, 'source_url': SOURCE}
            if note:
                document['nota_catalogo'] = note
            if not any(d['url'] == url for d in row['documentos']):
                row['documentos'].append(document)
        if not rows:
            raise ValueError('Empty amendments inventory requires review')
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        capture = self.config.get('evidence_dir')
        capture = Path(capture) if capture else None
        if capture:
            capture.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-rafelbunyol/1.0'
            def fetch(url, limit):
                with session.get(url, timeout=40, stream=True) as response:
                    response.raise_for_status()
                    if urlparse(response.url).hostname != HOST:
                        raise ValueError('Unexpected document redirect')
                    parts, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > limit:
                            raise ValueError('Source exceeds reviewed size limit')
                        parts.append(chunk)
                    return b''.join(parts)
            html = fetch(SOURCE, 4_000_000)
            if capture:
                (capture / 'planeamiento.html').write_bytes(html)
            rows = self.parse_inventory(html.decode('utf-8'))
            seen = {}
            for row in rows:
                for doc in row['documentos']:
                    url = doc['url']
                    if url not in seen:
                        data = fetch(url, 30_000_000)
                        if not data.lstrip().startswith(b'%PDF-'):
                            raise ValueError('Official attachment is not a PDF: ' + url)
                        seen[url] = hashlib.sha256(data).hexdigest()
                        if capture:
                            (capture / (seen[url] + '.pdf')).write_bytes(data)
                    doc['sha256'] = seen[url]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'documents': len(seen),
                'source_urls': [SOURCE, *seen], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot, including all linked documents; no date watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
