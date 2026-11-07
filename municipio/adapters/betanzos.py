"""Municipal PXOM document inventory; no assertion of present legal validity."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://concello.betanzos.es/urbanismo/'
HOST = 'concello.betanzos.es'
MONTHS = dict(zip(('xaneiro febreiro marzo abril maio xuño xullo agosto setembro outubro novembro decembro').split(), range(1, 13)))
LIMITATIONS = [
    'Cobertura parcial: só a ficha documental PXOM enlazada desde Urbanismo; non é un censo de obras nin licenzas.',
    'Versión de aprobación inicial publicada en 2021; non acredita a fase actual nin a vixencia do PXOM.',
    'Carpetas de Google Drive conservadas como ligazóns oficiais; non se enumeran os seus ficheiros internos.',
    'Sen xeometría verificada. NNSS, PEPOCH, noticias, axudas e contratación fóra desta extracción.',
]


def checked_soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select_one('a[rel~=next], .pagination, .page-numbers, .nav-links, .fusion-load-more-button'):
        raise ValueError('Pagination detected: inventory coverage must be reviewed')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).lower() in {'seguinte', 'siguiente', 'next', 'cargar máis', 'cargar más'}:
            raise ValueError('Pagination detected: refusing partial inventory')
    return soup


def discover_pxom(html, url=SOURCE):
    soup = checked_soup(html)
    urls = []
    for a in soup.select('.tab-pane a[href]'):
        target = urljoin(url, a['href'])
        if (urlparse(target).hostname == HOST and
                urlparse(target).path.startswith('/portfolio-items/plan-xeral-de-ordenacion-')):
            if target not in urls:
                urls.append(target)
    if not urls:
        raise ValueError('Municipal PXOM inventory link missing')
    return urls


def contextual_date(text, pattern):
    match = re.search(pattern + r'(\d{1,2}) de (\w+) de (\d{4})', text, re.I)
    if not match:
        return None
    day, month, year = match.groups()
    if month.lower() not in MONTHS:
        raise ValueError('Unrecognized source month')
    return date(int(year), MONTHS[month.lower()], int(day)).isoformat()


def parse_pxom(html, url):
    soup = checked_soup(html)
    body = soup.select_one('.project-description')
    if body is None:
        raise ValueError('PXOM document body missing')
    text = body.get_text(' ', strip=True)
    heading = next((p for p in body.select('p') if re.search(
        r'Revisión do Plan xeral de ordenación municipal de Betanzos', p.get_text(' ', strip=True), re.I)), None)
    if heading is None:
        raise ValueError('Named Betanzos instrument missing')
    strong = heading.find('strong')
    title = (strong or heading).get_text(' ', strip=True).strip('“” ,')
    documents = {}
    for a in body.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        p = a.find_parent('p')
        label = (p or a).get_text(' ', strip=True)
        if re.search(r'Formulario|Alegaci[oó]ns', label, re.I):
            continue
        if parsed.scheme != 'https':
            continue
        if parsed.hostname == HOST and parsed.path.lower().endswith('.pdf'):
            kind = 'pdf'
        elif parsed.hostname == 'drive.google.com' and parsed.path.startswith(('/file/d/', '/drive/folders/')):
            kind = 'carpeta' if '/folders/' in parsed.path else 'documento'
        else:
            continue
        if a.get_text(' ', strip=True).upper() != 'VER':
            label = a.get_text(' ', strip=True)
        documents[target] = {'titulo': label, 'url': target, 'tipo_enlace': kind,
                             'provenance_url': url}
    if not any(d['tipo_enlace'] == 'pdf' for d in documents.values()):
        raise ValueError('PXOM has no municipal source PDF')
    row = {
        'id': 'betanzos-pxom-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Betanzos', 'codigo_ine': '15009', 'provincia': 'A Coruña',
        'titulo': title, 'tipo': 'planeamiento_urbanistico', 'url': url,
        'inventory_url': SOURCE, 'source': 'ayuntamiento',
        'origen': 'inventario_documental_pxom', 'descripcion': heading.get_text(' ', strip=True),
        'documentos': list(documents.values()), 'publication_ready': False,
        'geometry_status': 'unavailable', 'limitaciones': LIMITATIONS,
    }
    agreement = contextual_date(text, r'Este documento foi aprobado polo Pleno do Concello o\s+')
    publication = contextual_date(text, r'Diario Oficial de Galicia\s+de data\s+')
    if agreement:
        row['fecha_acuerdo'] = agreement
        row['fecha_acuerdo_fuente'] = url
    if publication:
        row['fecha_publicacion'] = publication
        row['fecha_publicacion_tipo'] = 'anuncio de aprobación inicial no DOG; non data da ficha web'
    return row


class BetanzosAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=45, headers={'User-Agent': 'municipio-betanzos/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Unexpected municipal source redirect')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            import gzip
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html.gz'
            (path / name).write_bytes(gzip.compress(response.content))
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.jsonl.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        urls = discover_pxom(self._fetch(SOURCE))
        rows = [parse_pxom(self._fetch(url), url) for url in urls]
        return {**self._write(out_jsonl, rows), 'source_urls': [SOURCE, *urls],
                'coverage': 'partial_pxom_document_inventory', 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
