"""Municipal public-exposure planning inventory; no licence inference."""
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

SOURCE = 'https://www.poblamafumet.cat/documents-subjectes-a-exposicio-publica'
BOPT = 'https://aplicacions.dipta.cat/bopt/web/anunci/351869/modificacio-puntual-num-6-del-pla-d-ordenacio-urbanistica-municipal-poum-aprovacio-inicial-ajuntament-pobla-de-mafumet-la'
PDF = 'https://aplicacions.dipta.cat/bopt/web/anunci/descarrega-pdf/351869'
LIMITATIONS = [
    'Partial snapshot of the municipal public-exposure inventory; not the full RPUC or historical planning register.',
    'Municipal PAU-I plan link on Google Drive returned HTTP 404 during research; retained as published. BOPT notice PDF is accessible, not the complete technical plan.',
    'Agreement/approval dates are not parsed from PDFs; publication date comes only from the BOPT labelled field.',
    'No verified project geometry or granted-licence register; environmental authorisations are excluded.',
]


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.select_one('title')
    content = soup.select_one('.page-content')
    if not title or 'Documents subjectes a exposició pública' not in title.get_text() or not content:
        raise ValueError('Municipal inventory missing or unexpected markup')
    for a in soup.select('a[href]'):
        if ('next' in a.get('rel', []) or
            re.fullmatch(r'(següent|siguiente|next|[»›])', a.get_text(' ', strip=True), re.I) or
            re.search(r'/(?:page|pagina)/\d+|[?&](?:paged|page)=\d+', a['href'])):
            raise ValueError('Pagination detected; extend inventory traversal before extraction')
    records = {}
    for heading in content.select('h2'):
        text = heading.get_text(' ', strip=True)
        match = re.fullmatch(r'Aprovació (inicial|provisional|definitiva) de la modificació puntual núm\.?\s*(\d+) del POUM', text, re.I)
        if not match:
            continue
        number = str(int(match[2]))
        docs = {}
        for sibling in heading.next_siblings:
            if getattr(sibling, 'name', None) == 'h2':
                break
            if not hasattr(sibling, 'select'):
                continue
            for a in sibling.select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                if urlparse(url).scheme != 'https':
                    raise ValueError('Unexpected planning document URL')
                docs[url] = {'titulo': a.get_text(' ', strip=True), 'url': url,
                             'procedencia': SOURCE, 'rol': 'documentacion_enlazada_por_el_ayuntamiento'}
        if not docs:
            raise ValueError(f'POUM modification {number} has no linked documentation')
        if number in records:
            if records[number]['fase'] != 'aprobación ' + match[1].lower():
                raise ValueError('Conflicting phases for one planning instrument')
            prior = {d['url']: d for d in records[number]['documentos']}
            prior.update(docs)
            records[number]['documentos'] = list(prior.values())
            continue
        identity = f'{SOURCE}#modificacion-poum-{number}'
        records[number] = {
            'id': 'la-pobla-de-mafumet-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
            'municipio': 'La Pobla de Mafumet', 'codigo_ine': '43109', 'provincia': 'Tarragona',
            'titulo': text, 'tipo': 'modificacion_planeamiento_urbanistico',
            'numero_modificacion': number, 'fase': 'aprobación ' + match[1].lower(),
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'source': 'ayuntamiento', 'origen': 'inventario_exposicion_publica', 'url': SOURCE,
            'documentos': list(docs.values()), 'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False,
        }
    if not records:
        raise ValueError('No supported planning instruments in municipal inventory')
    return list(records.values())


def parse_bopt(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    h1 = soup.select_one('h1')
    if not h1 or not re.search(r'Modificació puntual núm\. 6 .*POUM\. Aprovació inicial', h1.get_text(' ', strip=True)):
        raise ValueError('BOPT notice does not match modification 6')
    if 'AJUNTAMENT POBLA DE MAFUMET, LA' not in text or '2025-09478' not in text:
        raise ValueError('BOPT municipality or notice identity mismatch')
    dates = re.findall(r'Data de publicació:\s*(\d{2}/\d{2}/\d{4})', text)
    if len(set(dates)) != 1:
        raise ValueError('BOPT publication date missing or ambiguous')
    if not any(urljoin(BOPT, a['href']) == PDF for a in soup.select('a[href]')):
        raise ValueError('BOPT notice PDF link missing')
    return datetime.strptime(dates[0], '%d/%m/%Y').date().isoformat()


class LaPoblaDeMafumetAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.poblamafumet.cat')

    def _fetch(self, url, capture_name):
        with requests.get(url, timeout=35, stream=True,
                          headers={'User-Agent': 'municipio-la-pobla-de-mafumet/1.0'}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 5_000_000:
                    raise ValueError('Source response exceeds 5 MB; refusing partial extraction')
                chunks.append(chunk)
            data = b''.join(chunks)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture_name).write_bytes(data)
        return data

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = parse_inventory(self._fetch(SOURCE, 'live-inventory.html').decode('utf-8'))
        urls = [SOURCE]
        for row in rows:
            if row['numero_modificacion'] != '6':
                continue
            if row['fase'] != 'aprobación inicial':
                raise ValueError('Municipal phase changed; review supplemental BOPT notice')
            row['fecha_publicacion'] = parse_bopt(self._fetch(BOPT, 'live-bopt.html').decode('utf-8'))
            pdf = self._fetch(PDF, 'live-bopt-351869.pdf')
            if not pdf.startswith(b'%PDF-'):
                raise ValueError('BOPT download is not a PDF')
            row['documentos'].append({'titulo': 'Anunci BOPT 2025-09478', 'url': PDF,
                                      'procedencia': BOPT, 'rol': 'anuncio_aprobacion_inicial'})
            row['referencias_publicacion'] = [{'url': BOPT, 'registro': '2025-09478',
                                               'fecha_publicacion': row['fecha_publicacion']}]
            urls.extend([BOPT, PDF])
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Entire current exposure inventory refreshed; no historical completeness claim.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
