"""Municipal land-use inventory; documents are grouped by planning instrument.

The WordPress document viewer stores its complete inventory in JSON attributes.
Only the three short municipal notices are text-extracted (preinstalled pdftotext);
scanned plans remain linked, without OCR, guessed status or geometry.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://transparencia.lafontdencarros.es/urbanisme/'
HOST = 'transparencia.lafontdencarros.es'
GROUPS = {
    'general': 'Pla general de la Font d’en Carròs',
    'normes': 'Normes subsidiàries de la Font d’en Carròs',
    'altures': 'Ordenació d’altures de l’edificació',
    'tossal': 'Pla parcial Tossal Gros — ordenances',
    'rafali': 'Pla especial de protecció del recinte emmurallat «El Rafalí»',
}
MONTHS = {'gener': 1, 'febrer': 2, 'marc': 3, 'abril': 4, 'maig': 5,
          'juny': 6, 'juliol': 7, 'agost': 8, 'setembre': 9, 'octubre': 10,
          'novembre': 11, 'desembre': 12}


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


def group_for(title):
    t = norm(title)
    if re.search(r'\bpla general\b', t) or t == 'planol classificacio concert previ':
        return 'general'
    if t == 'normes subsidiaries':
        return 'normes'
    if re.fullmatch(r'ordenacio altures edificacio part [12]', t):
        return 'altures'
    if t == 'ordenances pla parcial tossal gros':
        return 'tossal'
    if t == 'pla especial de proteccio del recinte emmurallat':
        return 'rafali'
    return None


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    # The verified source is a single complete viewer, not a paged search.
    if soup.select('[rel~=next], .pagination, .nav-links, .page-numbers, [data-next-page]'):
        raise ValueError('Inventory pagination appeared; traversal requires review')
    buttons = soup.select('button.doc-viewer__btn')
    if not buttons:
        raise ValueError('Municipal document inventory missing')
    groups, excluded, seen = {}, [], {}
    for button in buttons:
        item = json.loads(button['data-wp-context'])
        title = item['title'].strip()
        url = urljoin(SOURCE, item['pdfUrl'])
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or parsed.hostname != HOST
                or not parsed.path.startswith('/wp-content/uploads/')
                or not parsed.path.lower().endswith('.pdf')):
            raise ValueError('Unexpected municipal document URL')
        if url in seen:
            if seen[url] != title:
                raise ValueError('Conflicting titles for the same document')
            continue
        seen[url] = title
        group = group_for(title)
        if group is None:
            excluded.append({'titulo': title, 'url': url,
                             'reason': 'Outside selected land-use instrument coverage'})
            continue
        groups.setdefault(group, []).append({'titulo': title, 'url': url,
                                              'source_url': SOURCE})
    if not groups:
        raise ValueError('No named land-use planning instruments found')
    rows = []
    for key, docs in groups.items():
        rows.append({
            'id': 'la-font-d-en-carros-plan-' + key,
            'municipio': "la Font d'en Carròs", 'codigo_ine': '46127',
            'provincia': 'Valencia', 'titulo': GROUPS[key],
            'tipo': 'instrumento de planeamiento urbanístico',
            'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
            'url': SOURCE, 'documentos': docs,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'fase': None,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'coverage': 'partial_land_use_document_inventory',
        })
    return rows, excluded


def date_from(pattern, text):
    match = re.search(pattern, norm(text))
    if not match:
        return None
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


DATE = r'(\d{1,2})\s+d[’\x27e ]*(\w+)\s+de\s+(\d{4})'


def enrich_notice(row, doc, text):
    """Dates come from the notice narrative, never paths or PDF signatures."""
    compact = ' '.join(text.split())
    t = norm(compact)
    title = norm(doc['titulo'])
    required = None
    if title.startswith('1. informacio publica pla general'):
        required = 'informacio publica del pla general'
        agreement = date_from(r'sessio de\s+' + DATE, compact)
        published = date_from(r'docv de\s+' + DATE, compact)
        if agreement:
            doc['fecha_acuerdo'] = agreement
        if published:
            doc['fecha_publicacion'] = published
        doc['fase'] = 'información pública'
    elif title.startswith('2. aprovacio provisional pla general'):
        required = 'aprovacio provisional del pla general'
        agreement = date_from(r'sessio d[’\x27e ]*' + DATE, compact)
        if agreement:
            doc['fecha_acuerdo'] = doc['fecha_aprob'] = agreement
            row['fecha_acuerdo'] = row['fecha_aprob'] = agreement
        row['fase'] = 'aprobación provisional (documento de 2019; vigencia no verificada)'
        doc['fase'] = 'aprobación provisional'
    elif title == 'pla especial de proteccio del recinte emmurallat':
        required = 'pla especial de proteccio del recinte emmurallat'
        agreement = date_from(r'sessio de\s+' + DATE, compact)
        if agreement:
            doc['fecha_acuerdo'] = doc['fecha_aprob'] = agreement
            row['fecha_acuerdo'] = row['fecha_aprob'] = agreement
            row['fase'] = 'aprobado por el pleno (sin atribuir aprobación definitiva)'
    else:
        return
    if required not in t or 'font' not in t or 'carros' not in t:
        raise ValueError('Unexpected planning notice content')
    # Links transcribed from the notice retain explicit provenance. They are
    # documentary references, not fetched/claimed as an enumerated Drive folder.
    links = re.findall(r'https?://[^\s<>]+', compact)
    doc['enlaces_documentacion'] = list(dict.fromkeys(links))
    doc['text_sha256'] = hashlib.sha256(text.encode()).hexdigest()
    doc['date_provenance'] = 'municipal PDF notice narrative; not upload path'


def pdf_text(content):
    with tempfile.TemporaryDirectory(prefix='font-plan-') as tmp:
        source = Path(tmp) / 'notice.pdf'
        source.write_bytes(content)
        result = subprocess.run(['pdftotext', '-layout', str(source), '-'],
                                check=True, capture_output=True, timeout=30)
        return result.stdout.decode('utf-8')


class LaFontDEnCarrosAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, url, limit):
        with requests.get(url, timeout=(15, 60), stream=True,
                          headers={'User-Agent': 'municipal-planning-inventory/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != HOST:
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source exceeds response limit')
                chunks.append(chunk)
            content = b''.join(chunks)
        capture = self.config.get('capture_dir')
        if capture:
            folder = Path(capture)
            folder.mkdir(parents=True, exist_ok=True)
            name = 'live-inventory.html' if url == SOURCE else urlparse(url).path.rsplit('/', 1)[-1]
            (folder / name).write_bytes(content)
        return content

    def backfill_proyectos(self, out_jsonl: Path):
        rows, excluded = parse_inventory(self._get(SOURCE, 3_000_000).decode('utf-8'))
        fetched = [SOURCE]
        for row in rows:
            for doc in row['documentos']:
                title = norm(doc['titulo'])
                if title.startswith(('1. informacio publica pla general',
                                     '2. aprovacio provisional pla general',
                                     'pla especial de proteccio del recinte emmurallat')):
                    content = self._get(doc['url'], 5_000_000)
                    if not content.startswith(b'%PDF-'):
                        raise ValueError('Notice is not a PDF')
                    enrich_notice(row, doc, pdf_text(content))
                    fetched.append(doc['url'])
        out = Path(out_jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        # A failed fetch/parse leaves the previous snapshot intact.
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=out.parent,
                                         delete=False) as temp:
            temp.write(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
            temporary = Path(temp.name)
        temporary.replace(out)
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'source_urls': fetched, 'excluded_documents': excluded,
                'coverage': 'partial_land_use_document_inventory',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full current inventory snapshot; no incremental date filter or page cap.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out = Path(out_jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
