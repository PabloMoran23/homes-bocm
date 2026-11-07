"""Santoña: current municipal PGOU index, one instrument with its documents."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://santona.es/guia-ciudadana/urbanismo'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _date(text, pattern):
    match = re.search(pattern + r'\s+(\d{1,2}) de (\w+) de (\d{4})', text, re.I)
    if not match:
        return None
    return date(int(match[3]), MONTHS.index(match[2].lower()) + 1, int(match[1])).isoformat()


class SantonaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://santona.es')

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        if soup.select('a[rel~=next], .pagination a[href], .dropfiles-pagination'):
            raise ValueError('Inventory pagination detected; review before extracting a partial page')
        groups = []
        for container in soup.select('.dropfiles-container'):
            if any('/PGOU/' in a['href'] for a in container.select('a.dropfiles_downloadlink[href]')):
                groups.append(container)
        if len(groups) != 1:
            raise ValueError('Expected one municipal PGOU document inventory')
        docs = {}
        for a in groups[0].select('a.dropfiles_downloadlink[href]'):
            url = urljoin(SOURCE, a['href'])
            if urlparse(url).hostname != 'santona.es' or '/PGOU/' not in url:
                raise ValueError('Unexpected PGOU inventory document')
            docs[url] = {'titulo': _text(a), 'url': url, 'relacion': 'indice_municipal'}
        # Additional documents require explicit grouping/semantics review, never discard them.
        if len(docs) != 1:
            raise ValueError('PGOU inventory changed; review grouping of all documents')
        return list(docs.values())

    @staticmethod
    def parse_index(html, document):
        soup = BeautifulSoup(html, 'html.parser')
        body = soup.body or soup
        text = _text(body)
        if not re.search(r'PLAN GENERAL de ORDENACIÓN URBANA de SANTOÑA', text, re.I):
            raise ValueError('Downloaded document is not the Santoña PGOU index')
        approval = _date(text, r'en su sesión de fecha')
        publication = _date(text, r'publicado en el Boletín Oficial de Cantabria BOC de')
        if 'aprobado definitivamente' not in text.lower() or not approval or not publication:
            raise ValueError('PGOU index approval/publication provenance missing')
        docs = {document['url']: document}
        references = {}
        for a in body.select('a[href]'):
            url = a['href']
            if urlparse(url).scheme not in {'http', 'https'}:
                continue
            item = {'titulo': _text(a), 'url': url, 'provenance_url': document['url']}
            if urlparse(url).hostname in {'santona.es', 'www.santona.es'} and '/Datos/Urbanismo/PG.SANTOÑA_' in unquote(url):
                item['relacion'] = 'parte_del_pgou'
                docs.setdefault(url, item)
            else:
                # Ordinances/PORN references are not separate municipal projects.
                item['relacion'] = 'referencia_del_indice'
                references.setdefault(url, item)
        if len(docs) < 2:
            raise ValueError('PGOU index no longer links its constituent documents')
        return [{
            'id': 'santona-proy-pgou', 'municipio': 'Santoña', 'provincia': 'Cantabria',
            'codigo_ine': '39079', 'titulo': 'Plan General de Ordenación Urbana de Santoña',
            'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación definitiva',
            'fecha': None, 'fecha_aprob': approval, 'fecha_acuerdo': approval,
            'fecha_publicacion': publication, 'url': SOURCE, 'url_documento': document['url'],
            'source': 'ayuntamiento', 'origen': 'indice_municipal_pgou',
            'descripcion': text[:text.index('0 ÍNDICE GENERAL')] if '0 ÍNDICE GENERAL' in text else text,
            'documentos': list(docs.values()), 'referencias': list(references.values()),
            'date_provenance_url': document['url'],
            'coverage': 'PGOU municipal index only; later amendments and full legal consolidation not verified',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'No verified instrument geometry extracted',
        }]

    def _fetch(self, url, limit):
        with requests.get(url, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-santona/1.0')
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname not in {'santona.es', 'www.santona.es'}:
                raise ValueError('Municipal source redirected outside the official host')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source exceeds bounded response size; no truncation permitted')
                chunks.append(chunk)
            return b''.join(chunks)

    def backfill_proyectos(self, out_jsonl):
        html = self._fetch(SOURCE, 4_000_000)
        docs = self.parse_inventory(html)
        pdf = self._fetch(docs[0]['url'], 20_000_000)
        if not pdf.startswith(b'%PDF-'):
            raise ValueError('Municipal PGOU download is not a PDF')
        with tempfile.TemporaryDirectory(prefix='santona-') as tmp:
            path = Path(tmp) / 'pgou.pdf'
            path.write_bytes(pdf)
            # Poppler is preinstalled; preserve PDF hyperlinks as well as text.
            converted = subprocess.run(['pdftohtml', '-i', '-s', '-stdout', str(path)],
                                       capture_output=True, check=True, timeout=30).stdout
        rows = self.parse_index(converted, docs[0])
        rows[0]['document_sha256'] = hashlib.sha256(pdf).hexdigest()
        if self.config.get('evidence_dir'):
            evidence = Path(self.config['evidence_dir'])
            evidence.mkdir(parents=True, exist_ok=True)
            for name, content in [('urbanismo.html', html), ('pgou.pdf', pdf), ('pgou-links.html', converted)]:
                (evidence / name).write_bytes(content)
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [SOURCE, docs[0]['url']], 'coverage': 'partial_pgou_index'}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'Application forms are not granted licences'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
