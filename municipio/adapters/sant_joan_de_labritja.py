"""Municipal NNSS inventory and linked BOIB acts; no licence inference."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.santjoandelabritja.com/index.php/es/nnss'
HOSTS = {'www.santjoandelabritja.com', 'santjoandelabritja.com'}
MONTHS = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5,
          'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10,
          'noviembre': 11, 'diciembre': 12, 'gener': 1, 'febrer': 2, 'marc': 3,
          'maig': 5, 'juny': 6, 'juliol': 7, 'agost': 8, 'setembre': 9,
          'novembre': 11, 'desembre': 12}
LIMITATIONS = [
    'Partial coverage: only the municipal NNSS page and its linked BOIB acts, not all municipal planning or works.',
    'No verified public granted-licence register; forms and procurement excluded.',
    'Ancillary plans and annexes retained as links; only the BOIB acts are downloaded and verified.',
    'Historical acts do not prove the absence of later amendments or continued legal validity.',
    'No verified geometry or coordinates; publication_ready=false.',
]


def _norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def _date(day, month, year):
    return date(int(year), MONTHS[month], int(day)).isoformat()


def parse_inventory(html):
    """Read both anchors and Smart Slider data-href; group maps, not map rows."""
    soup = BeautifulSoup(html, 'html.parser')
    if 'NORMAS SUBSIDIARIAS' not in soup.get_text(' ', strip=True).upper():
        raise ValueError('Missing municipal NNSS inventory')
    for node in soup.select('a[href], [data-href]'):
        href = node.get('data-href') or node.get('href', '')
        label = _norm(node.get_text(' ', strip=True))
        rel = node.get('rel', [])
        if href not in {'', '#'} and (
            'next' in rel or label in {'siguiente', 'seguent', 'next', 'ver mas', 'cargar mas'}
            or re.search(r'[?&](?:start|page|limitstart)=', href)
        ):
            raise ValueError('Inventory pagination detected; extend crawler before extracting')
    if soup.select('.pagination a[href], a.pagenav[href]'):
        raise ValueError('Inventory pagination markup detected')
    groups = {}
    for node in soup.select('a[href], [data-href]'):
        href = node.get('data-href') or node.get('href', '')
        target = urljoin(SOURCE, href)
        parsed = urlparse(target)
        path = unquote(parsed.path)
        if not path.startswith(('/documentos/NNSS/', '/documentos/PTI/')):
            continue
        if parsed.scheme != 'https' or parsed.hostname not in HOSTS:
            raise ValueError('Unexpected planning document host')
        if not path.lower().endswith(('.pdf', '.tif', '.tiff')):
            raise ValueError('Unreviewed planning document format')
        filename = path.rsplit('/', 1)[-1]
        normalized = _norm(filename)
        # These are standalone general rules/instructions, not separate projects.
        if normalized.startswith(('ordenanza_', 'certificado de acuerdo de la cmpu')):
            continue
        mod = re.search(r'mod(?:ificacion)?\D*(\d+)', normalized)
        if mod:
            key = 'nnss-modificacion-' + str(int(mod[1]))
        elif '/documentos/NNSS/' in path and '/modificacion' not in path.lower():
            key = 'nnss'
        else:
            raise ValueError('Unclassified planning attachment: ' + filename)
        # Preserve actual linked host; normalize only encoding/fragments for deduplication.
        target = parsed._replace(path=quote(path, safe='/'), fragment='').geturl()
        group = groups.setdefault(key, {'documentos': {}, 'act_url': None})
        title = node.get_text(' ', strip=True) or filename
        prior = group['documentos'].get(target)
        if not prior or prior['titulo'] == filename:
            group['documentos'][target] = {'titulo': title, 'url': target,
                                           'inventory_url': SOURCE, 'verification': 'linked_not_fetched'}
        if normalized == 'nnss_boib.pdf' or (mod and filename.lower().endswith('.pdf')):
            if group['act_url'] and group['act_url'] != target:
                raise ValueError('Multiple possible BOIB acts for ' + key)
            group['act_url'] = target
    if 'nnss' not in groups or not groups:
        raise ValueError('No NNSS instrument found')
    if any(not group['act_url'] for group in groups.values()):
        raise ValueError('Instrument lacks identifiable BOIB act')
    return groups


def parse_boib(text, key):
    """Parse the act heading, not unrelated bulletin articles or historic dates."""
    flat = ' '.join(text.split())
    norm = _norm(flat)
    heading = re.search(
        r'ac(?:uerdo|ord) de la comis(?:sio|ion) insular.{0,180}?'
        r'de (\d{1,2}) de (\w+) de (\d{4}),? d[e’\' ]*aprobacio[n]? definitiva', norm)
    if not heading:
        # Catalan uses aprovació, Spanish aprobación.
        heading = re.search(
            r'acord de la comissio insular.{0,180}?de (\d{1,2}) de (\w+) de (\d{4}),? '
            r'd[’\']?aprovacio definitiva', norm)
    if not heading:
        raise ValueError('Missing BOIB definitive approval heading')
    tail = norm[heading.end():heading.end() + 1100]
    if 'sant joan de labritja' not in tail:
        raise ValueError('BOIB act is not for this municipality')
    modification = re.search(r'modificacio[n]? puntual (?:num(?:ero)?\.?\s*)(\d+)', tail)
    if key == 'nnss':
        if modification or not re.search(r'\(pl-?\s*01/2010\)', tail):
            raise ValueError('Unexpected base NNSS identity')
        reference = 'PL-01/2010'
        title = 'Revisión del planeamiento general de Sant Joan de Labritja mediante Normas Subsidiarias'
    else:
        number = key.rsplit('-', 1)[-1]
        if not modification or modification[1] != number:
            raise ValueError('BOIB modification does not match inventory')
        ref = re.search(r'exp(?:edient|\.)\s*(\d{4})\s*/\s*(\d+[a-z])', tail)
        if not ref:
            raise ValueError('Missing modification expediente')
        reference = ref[1] + '/' + ref[2].upper()
        title = 'Modificación puntual número ' + number + ' de las Normas Subsidiarias de Sant Joan de Labritja'
    # Publication comes from the bulletin header, not the approval heading.
    header = norm[:heading.start()]
    publication = re.search(r'\b(\d{1,2}) de (\w+) de (\d{4})\b', header)
    numeric = re.search(r'\b(\d{2})-(\d{2})-(\d{4})\b', header)
    if numeric:
        published = date(int(numeric[3]), int(numeric[2]), int(numeric[1])).isoformat()
    elif publication:
        published = _date(*publication.groups())
    else:
        raise ValueError('Missing BOIB publication date')
    return {'titulo': title, 'expediente': reference, 'fase': 'aprobación definitiva',
            'fecha': None, 'fecha_acuerdo': _date(*heading.groups()),
            'fecha_aprob': _date(*heading.groups()), 'fecha_publicacion': published,
            'approval_heading': heading.group()}


class SantJoanDeLabritjaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, limit):
        with requests.get(url, timeout=(15, 60), stream=True,
                          headers={'User-Agent': 'municipio-sant-joan-de-labritja/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname not in HOSTS:
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source exceeds reviewed response size')
                chunks.append(chunk)
            return b''.join(chunks)

    def backfill_proyectos(self, out_jsonl):
        capture_dir = self.config.get('capture_dir')
        capture = Path(capture_dir) if capture_dir else None
        if capture:
            capture.mkdir(parents=True, exist_ok=True)
        html = self._fetch(SOURCE, 5_000_000)
        if capture:
            (capture / 'nnss-inventory.html').write_bytes(html)
        groups = parse_inventory(html.decode('utf-8'))
        rows = []
        for key, group in sorted(groups.items()):
            pdf = self._fetch(group['act_url'], 10_000_000)
            if not pdf.startswith(b'%PDF-'):
                raise ValueError('BOIB link did not return a PDF')
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'act.pdf'
                path.write_bytes(pdf)
                result = subprocess.run(['pdftotext', str(path), '-'],
                                        capture_output=True, check=True, timeout=30)
                text = result.stdout.decode('utf-8')
            if capture:
                (capture / (key + '.pdf')).write_bytes(pdf)
                (capture / (key + '.txt')).write_text(text, encoding='utf-8')
            metadata = parse_boib(text, key)
            doc = group['documentos'][group['act_url']]
            doc.update(verification='downloaded_pdf_text', sha256=hashlib.sha256(pdf).hexdigest())
            rows.append({
                'id': 'sant-joan-de-labritja-' + key,
                'municipio': 'Sant Joan de Labritja', 'codigo_ine': '07050',
                'provincia': 'Illes Balears', 'tipo': 'planeamiento_urbanistico',
                **metadata, 'url': SOURCE, 'url_documento': group['act_url'],
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_nnss',
                'documentos': list(group['documentos'].values()),
                'date_provenance': {'url': group['act_url'],
                                    'fecha_publicacion': 'BOIB header',
                                    'fecha_acuerdo': 'CIOTUPHA act heading'},
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'geometry_status': 'unavailable',
                'coverage': 'partial_municipal_nnss_inventory',
            })
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] +
                [g['act_url'] for g in groups.values()], 'limitations': LIMITATIONS}

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
