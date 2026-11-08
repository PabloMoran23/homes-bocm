"""Verified current-POUM snapshot, not the complete urban-planning register."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://caldesdemalavella.cat/index.php/ca/viure-caldes-ca-es/viure-caldes-serveis-ca-es/serveis-de-poble/urbanisme'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def parse_inventory(html: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('[itemprop="articleBody"]')
    if body is None:
        raise ValueError('Municipal article body missing')
    heading = next((h for h in body.find_all('h3') if h.get_text(' ', strip=True) == 'Accés al planejament vigent'), None)
    listing = heading.find_next_sibling('ul') if heading else None
    if listing is None:
        raise ValueError('Current planning inventory missing')
    if body.select('a[rel~=next], .pagination, .pagenavcounter'):
        raise ValueError('Paginated inventory requires crawler review')
    links = [(a.get_text(' ', strip=True), urljoin(SOURCE, a['href'])) for a in listing.select('a[href]')]
    plans = [url for title, url in links if title == 'POUM']
    norms = [url for title, url in links if title == 'Normativa POUM']
    if len(plans) != 1 or len(norms) != 1:
        raise ValueError('Expected one POUM and its normative document')
    parsed = urlparse(plans[0])
    ids = parse_qs(parsed.query).get('codintExp', [])
    if parsed.hostname not in {'ptop.gencat.cat', 'dtes.gencat.cat'} or len(ids) != 1 or not ids[0].isdigit():
        raise ValueError('Unverified RPUC dossier link')
    if urlparse(norms[0]).hostname != 'caldesdemalavella.cat' or not urlparse(norms[0]).path.lower().endswith('.pdf'):
        raise ValueError('Unverified municipal normative document')
    documents = [{'titulo': title, 'url': url} for title, url in links
                 if title == 'Normativa POUM' or (urlparse(url).hostname in {'ptop.gencat.cat', 'dtes.gencat.cat'}
                 and parse_qs(urlparse(url).query).get('codintExp') == ids)]
    return {'rpuc_id': ids[0], 'pdf_url': norms[0], 'documentos': documents}


def parse_project(inventory: dict, text: str) -> dict:
    # Only the opening edict carries the plan's dates; later annex dates are not used.
    opening = text.split('\f', 1)[0]
    compact = ' '.join(opening.split())
    title = "Pla d'ordenació urbanística municipal, al terme municipal de Caldes de Malavella"
    if title not in compact or not re.search(r'Aprovar definitivament el Pla d[’\']ordenació urbanística municipal', compact):
        raise ValueError('PDF does not verify definitive approval of the municipal POUM')
    publication = re.search(r'Núm\.\s*\d+\s*-\s*(\d{1,2})\.(\d{1,2})\.(\d{4})', compact)
    agreement = re.search(r'en la sessió de (\d{1,2}) d[’\'](?:e\s+)?(\w+) de (\d{4})', compact)
    dossier = re.search(r'Exp\.:\s*(\d{4}\s*/\s*\d+\s*/\s*[A-Z])', compact)
    if not publication or not agreement or not dossier or agreement[2] not in MONTHS:
        raise ValueError('POUM edict date/dossier structure changed')
    published = date(int(publication[3]), int(publication[2]), int(publication[1])).isoformat()
    agreed = date(int(agreement[3]), MONTHS[agreement[2]], int(agreement[1])).isoformat()
    return {
        'id': 'caldes-de-malavella-proy-' + hashlib.sha256(('rpuc:' + inventory['rpuc_id']).encode()).hexdigest()[:14],
        'municipio': 'Caldes de Malavella', 'provincia': 'Girona', 'codigo_ine': '17033',
        'titulo': title, 'tipo': 'POUM', 'fase': 'aprobación definitiva',
        'fecha': None, 'fecha_publicacion': published, 'fecha_acuerdo': agreed, 'fecha_aprob': agreed,
        'expediente': ' / '.join(x.strip() for x in dossier[1].split('/')),
        'rpuc_id': inventory['rpuc_id'], 'url': SOURCE, 'url_documento': inventory['pdf_url'],
        'documentos': inventory['documentos'], 'source': 'ayuntamiento', 'origen': 'planejament_vigent',
        'descripcion': 'POUM enlazado en el inventario municipal de planeamiento vigente. El PDF municipal reproduce el edicto del DOGC y las normas urbanísticas; no es un texto consolidado de todas las modificaciones.',
        'date_provenance': {'fecha_publicacion': inventory['pdf_url'], 'fecha_acuerdo': inventory['pdf_url'], 'fecha_aprob': inventory['pdf_url']},
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified project geometry extracted',
        'coverage': 'Partial: original POUM only; amendments and other inventories excluded',
    }


class CaldesDeMalavellaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://caldesdemalavella.cat')

    def _fetch(self, session, url, limit):
        with session.get(url, timeout=(15, 45), stream=True) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source exceeds response size limit')
                chunks.append(chunk)
            return b''.join(chunks)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-caldes-de-malavella/1.0'
            html = self._fetch(session, SOURCE, 2_000_000)
            inventory = parse_inventory(html.decode('utf-8'))
            pdf = self._fetch(session, inventory['pdf_url'], 10_000_000)
        if not pdf.startswith(b'%PDF-'):
            raise ValueError('Normative document is not a PDF')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'norms.pdf'
            path.write_bytes(pdf)
            text = subprocess.run(['pdftotext', '-layout', str(path), '-'], check=True, capture_output=True, timeout=30).stdout.decode('utf-8')
        row = parse_project(inventory, text)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanisme.html').write_bytes(html)
            (capture / 'Normativa_POUM.pdf').write_bytes(pdf)
            (capture / 'Normativa_POUM.txt').write_text(text, encoding='utf-8')
        target = Path(out_jsonl)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + '.tmp')
        temp.write_text(json.dumps(row, ensure_ascii=False) + '\n', encoding='utf-8')
        temp.replace(target)
        return {'status': 'ok', 'rows': 1, 'source_urls': [SOURCE, inventory['pdf_url']], 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register in scope'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
