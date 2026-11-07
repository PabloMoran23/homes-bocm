"""Municipal public-works sheets, a partial historical inventory (not licences)."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


SOURCE = ('https://www.llinarsdelvalles.cat/ajuntament/informacio-oficial/'
          'urbanisme-i-medi-ambient/urbanisme/projectes-dobra')
HOST = 'www.llinarsdelvalles.cat'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
LIMITATIONS = [
    'Partial historical coverage: only the municipal Projectes d’obra inventory; page last updated in 2016.',
    'Sheet work status is historical, with no verified status date; not a current execution claim.',
    'No granted licences, complete planning register, verified coordinates or geometry.',
    'Approval dates come from DATA D’APROVACIÓ on work sheets; publication/agreement dates are unknown.',
]


def _official_url(url: str) -> str:
    parts = urlsplit(urljoin(SOURCE, url))
    if parts.hostname != HOST or parts.scheme not in {'http', 'https'} or parts.username or parts.password:
        raise ValueError('Unexpected non-municipal source URL')
    return urlunsplit(('https', HOST, parts.path, parts.query, ''))


def parse_inventory(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#readspeakerPage')
    heading = content.select_one('h1') if content else None
    if not heading or heading.get_text(' ', strip=True) != "Projectes d'obra":
        raise ValueError('Missing municipal works inventory heading')
    # The reviewed inventory is a single page. Fail visibly if it becomes paginated.
    if soup.select('[rel~=next], .pagination, .paginacio, .paginador'):
        raise ValueError('Pagination detected; crawler must be extended')
    for a in soup.select('a[href]'):
        if re.search(r'[?&](?:pag|page|pagina)=', a['href']) or a.get_text(' ', strip=True).casefold() in {'següent', 'siguiente', 'next', 'més', 'carrega més'}:
            raise ValueError('Pagination detected; crawler must be extended')
    body = content.select_one('.ddbbtext')
    if not body:
        raise ValueError('Missing works inventory body')
    docs = {}
    for a in body.select('a[href]'):
        url = _official_url(a['href'])
        title = a.get_text(' ', strip=True)
        if (not urlsplit(url).path.startswith('/media/repository/documents/urbanisme/projectes-dobra/')
                or not urlsplit(url).path.lower().endswith('.pdf')
                or not re.match(r'^(Consolidació|Urbanització|Ampliació|Enderroc)\b', title, re.I)):
            raise ValueError('Unreviewed inventory entry; refusing partial extraction')
        docs.setdefault(url, {'titulo': title, 'url': url, 'url_original': a['href']})
    if not docs:
        raise ValueError('Empty municipal works inventory')
    return list(docs.values())


def parse_sheet(text: str) -> dict[str, Any]:
    def field(label):
        match = re.search(r'^\s*' + label + r'\s{2,}([^\n]+)', text, re.M)
        if not match:
            raise ValueError('Missing work-sheet field: ' + label)
        return match[1].strip()

    if not re.search(r'\bOBRA:', text):
        raise ValueError('Document is not a work sheet')
    expediente = field(r'EXP\. ADM\.')
    if not re.fullmatch(r'\d+/\d{4}', expediente):
        raise ValueError('Unrecognized municipal expediente')
    approval_text = field('DATA D[’\']APROVACIÓ')
    match = re.fullmatch(r'(\d{1,2})\s+(?:de\s+|d[’\'])(' + '|'.join(MONTHS) + r')\s+(?:de\s+)?(\d{4})', approval_text.casefold())
    if not match:
        raise ValueError('Unrecognized explicit approval date')
    approval = date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()
    return {'expediente': expediente, 'tipo_intervencion': field('TIPUS D[’\']INTERVENCIÓ'),
            'direccion': field('SITUACIÓ'), 'fecha_aprob': approval,
            'fecha_aprob_texto': approval_text, 'estado_obra_segun_ficha': field('ESTAT DE L[’\']OBRA')}


class LlinarsDelVallesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://' + HOST)

    def _fetch(self, url, limit):
        with requests.get(url, timeout=(10, 40), stream=True,
                          headers={'User-Agent': 'municipio-llinars-del-valles/1.0'}) as response:
            response.raise_for_status()
            _official_url(response.url)
            chunks, length = [], 0
            for chunk in response.iter_content(65536):
                length += len(chunk)
                if length > limit:
                    raise ValueError('Municipal source exceeds response size limit')
                chunks.append(chunk)
            data = b''.join(chunks)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            target = Path(capture_dir)
            target.mkdir(parents=True, exist_ok=True)
            (target / urlsplit(url).path.rsplit('/', 1)[-1]).write_bytes(data)
        return data

    @staticmethod
    def _pdf_text(data):
        if not data.startswith(b'%PDF-'):
            raise ValueError('Municipal attachment is not a PDF')
        # Existing system utility; no Python packages are installed by this adapter.
        result = subprocess.run(['pdftotext', '-layout', '-', '-'], input=data,
                                capture_output=True, check=True, timeout=30)
        return result.stdout.decode('utf-8')

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        docs = parse_inventory(self._fetch(SOURCE, 2_000_000).decode('utf-8'))
        grouped = {}
        for doc in docs:
            data = self._fetch(doc['url'], 10_000_000)
            text = self._pdf_text(data)
            fields = parse_sheet(text)
            key = fields['expediente']
            doc = {**doc, 'sha256': hashlib.sha256(data).hexdigest(),
                   'source_url': SOURCE, 'campos_ficha': fields, 'texto_ficha': text.strip()}
            if key in grouped:
                # Same dossier is one work, with every source document retained.
                if grouped[key]['fecha_aprob'] != fields['fecha_aprob']:
                    raise ValueError('Conflicting approval dates for the same work')
                grouped[key]['documentos'].append(doc)
                continue
            grouped[key] = {
                'id': 'llinars-del-valles-proy-' + key.replace('/', '-'),
                'municipio': 'Llinars del Vallès', 'provincia': 'Barcelona', 'codigo_ine': '08106',
                'titulo': doc['titulo'], 'tipo': 'obra_publica', 'fase': None,
                **fields, 'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'url': SOURCE, 'url_documento': doc['url'], 'documentos': [doc],
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_obras',
                'descripcion': doc['titulo'],
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'limitaciones': LIMITATIONS,
            }
        rows = list(grouped.values())
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + [d['url'] for d in docs],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh; no date cutoff or pagination truncation.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
