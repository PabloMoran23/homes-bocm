"""Current Porqueres public-works inventory; CSVs are not direct download URLs."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://porqueres.cat/tramits-exposicio-publica/'
UUID = re.compile(r'\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b', re.I)
HEADING = re.compile(r'^(?:Expedient:\s*)?(X\d{10})\s*[–—-]?\s*(.+)$', re.I)
SUPPORTED = re.compile(
    r'^(?:PROJECTE\b|ACTUALITZACIÓ DE PREUS PROJECTE\b|'
    r'PLA DIRECTOR DEL SERVEI D’ABASTAMENT D’AIGUA\b|'
    r'MEMÒRIA (?:TÈCNICA\b|VALORADA PER L’ASFALTATGE\b))', re.I)
VALIDATOR_HOST = 'porqueres.emunicipis.ddgi.cat'
NOTICE_HOSTS = {'tauler.seu.cat', 'tauler.seu-e.cat'}


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('article .entry-content')
    title = soup.select_one('article h1')
    if content is None or title is None or 'exposició pública' not in _text(title).lower():
        raise ValueError('Porqueres inventory markup/title missing')
    # This inventory is currently one complete static page. Fail closed if the
    # publisher introduces pagination rather than silently returning page one.
    if soup.select('a[rel~=next], .pagination, .page-numbers, .wp-pagenavi, .post-page-numbers'):
        raise ValueError('Paginated inventory requires crawler review')
    for a in content.select('a[href]'):
        if _text(a).lower() in {'següent', 'següents', 'siguiente', 'next', 'més', 'carrega més'}:
            raise ValueError('Possible inventory continuation requires review')

    records = {}
    # HRs delimit actual entries, including those inside nested layout DIVs.
    for fragment in re.split(r'<hr\b[^>]*>', str(content), flags=re.I):
        block = BeautifulSoup(fragment, 'html.parser')
        headings = []
        for strong in block.select('strong'):
            match = HEADING.fullmatch(_text(strong))
            if match:
                headings.append(match)
        if len(headings) > 1:
            raise ValueError('Multiple expedientes in one inventory section')
        if not headings:
            # Do not silently lose a source entry if its title markup changes.
            if re.search(r'\bX\d{10}\b', _text(block)):
                raise ValueError('Expediente without a recognized title')
            continue
        expediente, name = headings[0].groups()
        if not SUPPORTED.match(name):
            continue  # Equality plan / environmental licence exposure, not works.

        text = _text(block)
        validators, notices = [], []
        for a in block.select('a[href]'):
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            link = {'titulo': _text(a), 'url': url}
            if parsed.scheme != 'https':
                continue
            if parsed.hostname == VALIDATOR_HOST and parsed.path == '/OAC/ValidarDoc.jsp':
                if url not in validators:
                    validators.append(url)
            elif parsed.hostname in NOTICE_HOSTS and link not in notices:
                notices.append(link)
        if len(validators) != 1:
            raise ValueError(f'{expediente}: missing or ambiguous document validator')
        documents = {}
        for string in block.stripped_strings:
            for match in UUID.finditer(string):
                csv = match[0].lower()
                documents[csv] = {
                    'titulo': ' '.join(string[:match.start()].strip(' :').split()),
                    'csv': csv, 'url': validators[0], 'source_url': SOURCE,
                    'access': 'manual_csv_validation',
                }
        if not documents:
            raise ValueError(f'{expediente}: no source document codes')
        phases = re.findall(r'aprovació\s+(inicial|definitiva)', text, re.I)
        if len(set(p.lower() for p in phases)) > 1:
            raise ValueError(f'{expediente}: conflicting approval phases')
        phase = ('aprobación ' + ('inicial' if phases[0].lower() == 'inicial' else 'definitiva')) if phases else None
        row = {
            'id': 'porqueres-proy-' + expediente.lower(),
            'expediente': expediente, 'municipio': 'Porqueres',
            'codigo_ine': '17137', 'provincia': 'Girona', 'titulo': name,
            'tipo': 'plan_director_abastecimiento' if name.startswith('PLA DIRECTOR') else 'proyecto_obra_publica',
            'fase': phase, 'estado_publicado': text[len(_text(block.select_one('strong'))):].strip(),
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_exposicion_publica',
            'documentos': list(documents.values()), 'enlaces_anuncio': notices,
            'descripcion': text, 'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }
        if expediente in records:
            previous = records[expediente]
            if previous['titulo'] != name or previous['fase'] != phase:
                raise ValueError(f'{expediente}: conflicting repeated entry')
            for doc in row['documentos']:
                if doc not in previous['documentos']:
                    previous['documentos'].append(doc)
            for link in notices:
                if link not in previous['enlaces_anuncio']:
                    previous['enlaces_anuncio'].append(link)
        else:
            records[expediente] = row
    if not records:
        raise ValueError('No supported Porqueres works with document provenance')
    return list(records.values())


class PorqueresAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='porqueres', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://porqueres.cat')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path):
        response = requests.get(SOURCE, timeout=40, headers={'User-Agent': 'municipio-porqueres/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != 'porqueres.cat' or urlparse(response.url).path != urlparse(SOURCE).path:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text)
        # Optional local capture uses exactly the response that produced rows.
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'works-live.html').write_text(response.text, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'current_public_works_inventory_only', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Complete current snapshot, not an incremental historical register.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
