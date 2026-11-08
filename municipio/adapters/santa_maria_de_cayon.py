"""Municipal planning inventory; one record per instrument, with source documents."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


BASE = 'https://www.santamariadecayon.es'
SOURCE = BASE + '/index.php/servicios-municipales/sm-urbanismo-obras/sm-urbanismo-pgou'
MONTHS = dict(zip(('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split(), range(1, 13)))


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def date_value(match):
    if not match:
        return None
    from datetime import date
    return date(int(match[3]), MONTHS[match[2].lower()], int(match[1])).isoformat()


def pdf_dates(text):
    """Only explicit BOC publication headers and agreement clauses, never signatures."""
    first = norm(text.split('\f')[0])
    publication = re.search(r'(\d{1,2}) de (\w+) de (\d{4})\s*-\s*boc num', first)
    agreement = re.search(r'(?:celebrada el dia|celebrada el)\s*(\d{1,2}) de (\w+) de\s*(\d{4})', first)
    return {k: v for k, v in [('fecha_publicacion', date_value(publication)),
                             ('fecha_acuerdo', date_value(agreement))] if v}


class SantaMariaDeCayonAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE = SOURCE

    @classmethod
    def parse_inventory(cls, html):
        soup = BeautifulSoup(html, 'html.parser')
        body = soup.select_one('.item-page [itemprop="articleBody"]')
        if body is None or 'normas' not in norm(body.get_text()):
            raise ValueError('Municipal planning inventory missing')
        if soup.select('.pagination a[href], a[rel="next"]'):
            raise ValueError('Unimplemented pagination on planning inventory')
        for a in soup.select('a[href]'):
            if norm(a.get_text(' ', strip=True)) in {'siguiente', 'next', '›', '»'} and a['href'] not in ('', '#'):
                raise ValueError('Unimplemented next page')
        rows = {}
        current = None
        for block in body.find_all(['p', 'li']):
            text = block.get_text(' ', strip=True)
            folded = norm(text)
            exp = re.search(r'expediente\s+(\d+/\d+)', text, re.I)
            if exp:
                current = exp[1]
            elif re.search(r'normas subsi\w* de 1987', folded):
                current = 'nnss-1987'
            elif 'modificacion puntual' in folded and not block.find('a'):
                # Heading for the next instrument; do not attach it to its predecessor.
                current = None
            links = block.select('a[href]')
            if current is None:
                if links:
                    raise ValueError('Unclassified linked planning document: ' + text)
                continue
            correction = 'correccion de errores' in folded
            if current not in rows:
                if correction:
                    raise ValueError('Correction without original instrument')
                rows[current] = {
                    'id': 'santa-maria-de-cayon-planeamiento-' + current.replace('/', '-'),
                    'municipio': 'Santa María de Cayón', 'codigo_ine': '39074',
                    'provincia': 'Cantabria', 'titulo': text.rstrip('. '),
                    'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
                    'origen': 'inventario_municipal_planeamiento', 'url': cls.SOURCE,
                    'documentos': [],
                }
                if exp:
                    rows[current]['expediente'] = current
            for a in links:
                url = urljoin(cls.SOURCE, a['href'])
                if url.startswith('http://boc.cantabria.es/'):
                    url = 'https://' + url[len('http://'):]
                parsed = urlparse(url)
                if parsed.hostname not in {'www.santamariadecayon.es', 'boc.cantabria.es'}:
                    raise ValueError('Unexpected document host: ' + url)
                kind = 'referencia_boletin' if 'verBoletin.do' in url else ('correccion' if correction else 'instrumento')
                doc = {'titulo': a.get_text(' ', strip=True), 'url': url, 'tipo': kind}
                if not any(d['url'] == url for d in rows[current]['documentos']):
                    rows[current]['documentos'].append(doc)
        if not rows or any(not any(d['tipo'] == 'instrumento' for d in r['documentos']) for r in rows.values()):
            raise ValueError('Empty or incomplete planning inventory')
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('capture_dir')
        capture_dir = Path(captures) if captures else None
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'MunicipalPlanningResearch/1.0'

            def fetch(url, suffix):
                response = session.get(url, timeout=60)
                response.raise_for_status()
                source_urls.append(url)
                if capture_dir:
                    name = hashlib.sha256(url.encode()).hexdigest()[:16] + suffix
                    (capture_dir / name).write_bytes(response.content)
                return response

            rows = self.parse_inventory(fetch(self.SOURCE, '.html').text)
            for row in rows:
                for doc in row['documentos']:
                    if doc['tipo'] == 'referencia_boletin':
                        continue
                    response = fetch(doc['url'], '.pdf')
                    if not response.content.startswith(b'%PDF-'):
                        raise ValueError('Document no longer a PDF: ' + doc['url'])
                    doc['sha256'] = hashlib.sha256(response.content).hexdigest()
                    with tempfile.TemporaryDirectory() as tmp:
                        pdf = Path(tmp) / 'source.pdf'
                        pdf.write_bytes(response.content)
                        text = subprocess.run(['pdftotext', '-layout', str(pdf), '-'],
                                              check=True, capture_output=True, timeout=60).stdout.decode('utf-8')
                    dates = pdf_dates(text)
                    doc.update(dates)
                    if doc['tipo'] == 'instrumento':
                        row.update(dates)
                        if dates:
                            row['fechas_fuente_url'] = doc['url']
                row['cobertura'] = 'Inventario municipal de planeamiento; no histórico exhaustivo ni licencias'
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': source_urls}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refreshed inventory: no date watermark can lose a newly linked old document.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return self._write(out_jsonl, [])

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
