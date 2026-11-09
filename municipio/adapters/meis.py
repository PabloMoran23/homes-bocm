"""Meis municipal planning-document inventory (not a licence register)."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.meis.gal/urbanismo/'


def _norm(text):
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().upper().split())


def _pdf_url(href):
    url = urljoin(SOURCE, href)
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname != 'www.meis.gal' or not parts.path.lower().endswith('.pdf'):
        raise ValueError(f'Unexpected municipal document URL: {url}')
    return url


def parse_inventory(html):
    """One record per named instrument; the PXOM owns its inventory maps."""
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#page-content .page-content-inner')
    if content is None:
        raise ValueError('Meis planning content missing')
    for a in content.select('a[href]'):
        if ('next' in a.get('rel', []) or _norm(a.get_text(' ', strip=True)) in
                {'NEXT', 'SEGUINTE', 'SIGUIENTE', 'SEGUINTE PAGINA'} or
                re.search(r'/page/\d|[?&](?:paged|page)=', a['href'])):
            raise ValueError('Paginated planning inventory requires crawler review')
    heading = next((p for p in content.select('p') if _norm(p.get_text(' ', strip=True)) ==
                    'PLAN XERAL DE ORDENACION MUNICIPAL'), None)
    block = heading.find_parent('div', class_='wpb_wrapper') if heading else None
    if block is None:
        raise ValueError('Meis PXOM inventory missing')
    records = {}

    def add(key, title, kind, anchor):
        url = _pdf_url(anchor['href'])
        if key not in records:
            records[key] = {
                'id': 'meis-' + key, 'municipio': 'Meis', 'codigo_ine': '36028',
                'provincia': 'Pontevedra', 'titulo': title, 'tipo': kind,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None, 'url': SOURCE,
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_urbanismo',
                'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'limitaciones': 'Inventario documental parcial; fechas y vigencia no extraídas de los PDF. '
                                'La ruta de subida no acredita publicación ni aprobación.',
            }
        docs = records[key]['documentos']
        if not any(d['url'] == url for d in docs):
            docs.append({'titulo': anchor.get_text(' ', strip=True), 'url': url,
                         'source_url': SOURCE})

    maps = []
    for a in block.select('a[href]'):
        title = a.get_text(' ', strip=True)
        label = _norm(title)
        if label == 'PLAN XERAL DE ORDENACION MUNICIPAL DE MEIS':
            add('pxom', title, 'planeamiento_urbanistico', a)
        elif (match := re.fullmatch(r'MODIFICACION PUNTUAL N\s*[.º°O]*\s*(\d+) PXOM', label)):
            add('pxom-mp-' + str(int(match[1])), title, 'modificacion_planeamiento', a)
        elif re.fullmatch(r'(?:SUELO URBANO-?|PLANO )\s*\d+', label):
            maps.append(a)
        elif urlsplit(a['href']).path.lower().endswith('.pdf'):
            raise ValueError(f'Unclassified PXOM document: {title}')
    if 'pxom' not in records or not maps:
        raise ValueError('PXOM document or associated maps missing')
    for a in maps:
        add('pxom', records['pxom']['titulo'], 'planeamiento_urbanistico', a)
    for a in content.select('a[href]'):
        if _norm(a.get_text(' ', strip=True)) == 'PLAN DE MOBILIDADE SOSTIBLE DE MEIS':
            add('pmus', a.get_text(' ', strip=True), 'plan_movilidad_sostenible', a)
    for row in records.values():
        row['url_documento'] = row['documentos'][0]['url']
    return list(records.values())


class MeisAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        captures = Path(self.config['evidence_dir']) if self.config.get('evidence_dir') else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.trust_env = False  # Public anonymous access; no netrc credentials.
            session.headers['User-Agent'] = 'municipio-meis/1.0'
            with session.get(SOURCE, timeout=45, stream=True) as response:
                response.raise_for_status()
                if response.url != SOURCE:
                    raise ValueError('Unexpected inventory redirect')
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 3_000_000:
                        raise ValueError('Oversized planning inventory')
                    chunks.append(chunk)
                html = b''.join(chunks).decode('utf-8')
            rows = parse_inventory(html)
            checks = []
            # Check file signatures without downloading the 218 MB mobility plan
            # on each refresh. Document contents/dates are not parsed here.
            for url in dict.fromkeys(d['url'] for r in rows for d in r['documentos']):
                with session.get(url, timeout=45, stream=True) as response:
                    response.raise_for_status()
                    _pdf_url(response.url)
                    if response.raw.read(5) != b'%PDF-':
                        raise ValueError(f'Not a PDF: {url}')
                    checks.append({'url': url, 'resolved_url': response.url,
                                   'status': response.status_code, 'pdf_signature': True})
        if captures:
            (captures / 'inventory.html').write_text(html, encoding='utf-8')
            (captures / 'document_checks.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'documents': len(checks),
                'source_urls': [SOURCE], 'coverage': 'partial municipal planning inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete replacement of this unpaginated inventory; no false watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
