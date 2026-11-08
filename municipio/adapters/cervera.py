"""Cervera planning instruments evidenced by modern BOP Lleida notices.

CIDO is the discovery inventory; the municipal edicts, not its summaries, supply
approval stages and agreement dates. Legacy BOP and DOGC links are out of scope.
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
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://cido.diba.cat/normativa_local/8349590/planejament-urbanistic-ajuntament-de-cervera'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
PDF_PATH = re.compile(r'/aplicacions/bop/bopV1/fitxers/pdf/\d{4}/\d+/\d+\.pdf')


def _plain(text):
    return ' '.join(text.replace('’', "'").split())


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    if 'Ajuntament de Cervera' not in soup.get_text(' ', strip=True):
        raise ValueError('Wrong municipality or unavailable CIDO inventory')
    # This reviewed detail page exposes all its notices in one table. Refuse a
    # changed pagination contract instead of silently accepting only one page.
    if soup.select('.pagination, .paginacio, a[rel="next"], a[rel="prev"]'):
        raise ValueError('Paginated inventory requires crawler review')
    table = soup.select_one('table.adjunts')
    if not table or 'Data de publicació' not in table.get_text(' ', strip=True):
        raise ValueError('Missing publication inventory')
    notices = {}
    excluded = 0
    for tr in table.select('tbody tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) < 5:
            raise ValueError('Changed notice row layout')
        stamp = cells[0].select_one('time[datetime]')
        if stamp is None:
            raise ValueError('Missing notice publication date')
        publication = date.fromisoformat(stamp['datetime']).isoformat()
        links = [a['href'] for a in tr.select('a[href]')]
        modern = [u for u in links if urlparse(u).scheme == 'https'
                  and urlparse(u).netloc == 'ebop.diputaciolleida.cat'
                  and PDF_PATH.fullmatch(urlparse(u).path)]
        if not modern:
            excluded += 1
            continue
        if len(modern) != 1 or cells[1].get_text(strip=True) != 'BOPL':
            raise ValueError('Ambiguous original bulletin document')
        parts = list(cells[3].stripped_strings)
        if len(parts) != 2 or not parts[1].lower().startswith(('pla ', 'text refós', 'modificació')):
            raise ValueError('Unreviewed planning description')
        notice = {'url': modern[0], 'titulo': parts[1],
                  'fase_inventario': parts[0], 'fecha_publicacion': publication,
                  'inventory_url': SOURCE}
        if modern[0] in notices and notices[modern[0]] != notice:
            raise ValueError('Conflicting duplicate bulletin URL')
        notices[modern[0]] = notice
    if not notices:
        raise ValueError('No usable modern BOP planning documents')
    return list(notices.values()), excluded


def parse_notice(text, notice):
    text = _plain(text)
    if 'Cervera' not in text or 'EDICTE' not in text or 'cervera.sedelectronica.es/' not in text:
        raise ValueError('Not a verified Cervera municipal edict')
    publication = re.search(r'\bData (\d{2})-(\d{2})-(\d{4})', text)
    if not publication or date(int(publication[3]), int(publication[2]), int(publication[1])).isoformat() != notice['fecha_publicacion']:
        raise ValueError('Inventory / original publication date mismatch')
    # Only operative approval verbs count; references to future definitive
    # approval or licence suspension do not establish that approval.
    phases = re.findall(r'\b(?:Aprovat|aprovat|Aprovar|aprovar) (inicialment|provisionalment|definitivament)\b', text)
    if not phases or len(set(phases)) != 1:
        raise ValueError('Missing or ambiguous operative planning approval')
    phase = {'inicialment': 'aprobación inicial', 'provisionalment': 'aprobación provisional',
             'definitivament': 'aprobación definitiva'}[phases[0]]
    dates = []
    context = r'(?:acord de la Junta de Govern Local de |sessió celebrada el dia |sessió de data |sessió del dia |acord de la Junta de Govern Local del dia )'
    for m in re.finditer(context + r'(\d{1,2})(?: de (\w+) de (\d{4})|/(\d{2})/(\d{4}))', text):
        month = MONTHS[m[2]] if m[2] else int(m[4])
        dates.append(date(int(m[3] or m[5]), month, int(m[1])).isoformat())
    if len(set(dates)) > 1:
        raise ValueError('Ambiguous agreement dates')
    title = notice['titulo']
    # Both edicts name the same waste-deposit extension, while CIDO labels the
    # initial one only "Pla especial urbanístic". Group on original evidence.
    if "ampliació del dipòsit controlat de residus" in text:
        title = "Pla Especial Urbanístic i Estudi d'Impacte Paisatgístic de l'ampliació del dipòsit controlat de residus"
    key = unicodedata.normalize('NFKD', _plain(title).lower()).encode('ascii', 'ignore').decode()
    return {**notice, 'titulo': title, 'instrument_key': key, 'fase': phase,
            'fecha_acuerdo': dates[0] if dates else None,
            'descripcion': text, 'document_type': 'edicto municipal de planeamiento (BOPL)'}


def group_notices(notices):
    groups = {}
    for notice in notices:
        groups.setdefault(notice['instrument_key'], []).append(notice)
    rows = []
    for key, docs in sorted(groups.items()):
        docs.sort(key=lambda d: (d['fecha_publicacion'], d['url']))
        latest = docs[-1]
        rows.append({
            'id': 'cervera-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Cervera', 'provincia': 'Lleida', 'codigo_ine': '25072',
            'titulo': latest['titulo'], 'tipo': 'planeamiento_urbanistico',
            'fase': latest['fase'], 'fecha': None,
            'fecha_publicacion': latest['fecha_publicacion'],
            'fecha_acuerdo': latest['fecha_acuerdo'], 'fecha_aprob': latest['fecha_acuerdo'],
            'url': SOURCE, 'url_documento': latest['url'],
            'source': 'ayuntamiento', 'origen': 'edicto_municipal_bopl_via_cido',
            'descripcion': latest['descripcion'],
            'documentos': [{k: v for k, v in d.items() if k != 'instrument_key'} for d in docs],
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'coverage': 'Partial: modern direct BOPL PDFs indexed by CIDO; stage at latest covered notice, not necessarily current legal status',
        })
    return rows


class CerveraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://cervera.cat')

    def _fetch(self, url):
        with requests.get(url, timeout=(10, 40), stream=True,
                          headers={'User-Agent': self.config.get('user_agent', 'municipio-cervera/1.0')}) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 8_000_000:
                    raise ValueError('Source exceeds reviewed 8 MB response limit')
            return bytes(data)

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
            temp = Path(f.name)
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        captures = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
        inventory = self._fetch(SOURCE)
        if captures:
            (captures / 'inventory.html').write_bytes(inventory)
        notices, excluded = parse_inventory(inventory.decode('utf-8'))
        parsed = []
        for notice in notices:
            pdf = self._fetch(notice['url'])
            if not pdf.startswith(b'%PDF-'):
                raise ValueError('Original notice is not a PDF')
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'notice.pdf'
                path.write_bytes(pdf)
                text = subprocess.check_output(['pdftotext', '-layout', str(path), '-'], timeout=30).decode('utf-8')
            if captures:
                name = notice['url'].rsplit('/', 1)[-1]
                (captures / name).write_bytes(pdf)
                (captures / name.replace('.pdf', '.txt')).write_text(text, encoding='utf-8')
            parsed.append(parse_notice(text, notice))
        rows = group_notices(parsed)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'documents': len(parsed),
                'excluded_legacy_bop_or_dogc_notices': excluded,
                'source_urls': [SOURCE] + [n['url'] for n in notices], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
