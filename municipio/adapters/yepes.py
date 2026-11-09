"""Yepes municipal planning inventory; one instrument with its source documents."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.yepes.es/concejalia/urbanismo'
LIMITATIONS = [
    'Partial coverage: only the Plan de ordenación municipal inventory on the municipal Urbanismo page; not the complete historical planning or works register.',
    'Document dates are municipal upload/publication dates, not agreement or approval dates. Legal approval and current consolidated validity are not verified.',
    'No granted licences extracted; municipal application forms are excluded.',
    'No verified vector geometry or coordinates. PDF plans are retained as documents.',
]


class YepesAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        # This inventory is currently a complete, unpaginated document block.
        for a in soup.select('a[href]'):
            label = a.get_text(' ', strip=True).casefold()
            rel = a.get('rel', [])
            if ('next' in rel or label in {'siguiente', 'next', '›', '»'}
                    or a.find_parent(class_=lambda c: c and ('pagination' in c or 'paginator' in c))):
                raise ValueError('Pagination detected: review inventory before accepting a partial snapshot')
        headings = [h for h in soup.select('h2')
                    if h.get_text(' ', strip=True).casefold() == 'plan de ordenación municipal']
        if len(headings) != 1:
            raise ValueError('Expected one municipal planning inventory heading')
        block = headings[0].find_parent(class_=lambda c: c and 'col-6@sm' in c)
        if block is None:
            raise ValueError('Planning inventory structure changed')
        documents = {}
        for card in block.select('.card-file'):
            a = card.select_one('.card-file__title a[href]')
            if a is None:
                raise ValueError('Planning document lacks title/link')
            title = a.get_text(' ', strip=True)
            if title.casefold() not in {'planos', 'normas urbanísticas'}:
                raise ValueError('Unreviewed document/instrument in POM inventory: ' + title)
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            if (parsed.scheme != 'https' or parsed.netloc != 'www.yepes.es'
                    or not parsed.path.startswith('/fileadmin/') or not parsed.path.lower().endswith('.pdf')):
                raise ValueError('Unexpected planning document URL')
            time = card.select_one('time[datetime]')
            published = (datetime.strptime(time['datetime'], '%d-%m-%Y').date().isoformat()
                         if time else None)
            doc = {'titulo': title, 'url': url, 'url_procedencia': SOURCE,
                   'fecha_publicacion': published, 'fecha_publicacion_tipo': 'fecha de subida municipal del documento'}
            if url in documents and documents[url] != doc:
                raise ValueError('Conflicting document metadata')
            documents[url] = doc
        if {d['titulo'].casefold() for d in documents.values()} != {'planos', 'normas urbanísticas'}:
            raise ValueError('Incomplete POM source documents')
        return [{
            'id': 'yepes-proy-pom', 'municipio': 'Yepes', 'codigo_ine': '45202',
            'provincia': 'Toledo', 'titulo': 'Plan de ordenación municipal de Yepes',
            'tipo': 'planeamiento_urbanistico', 'url': SOURCE,
            'source': 'ayuntamiento', 'origen': 'inventario_municipal_urbanismo',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'fase': None,
            'documentos': list(documents.values()),
            'descripcion': 'Instrumento publicado por el Ayuntamiento con planos y normas urbanísticas. Sin fecha de aprobación acreditada por el inventario.',
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'cobertura': LIMITATIONS,
        }]

    def _fetch(self, url: str, limit: int) -> bytes:
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-yepes/1.0'}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source exceeds reviewed response size: ' + url)
                chunks.append(chunk)
            return b''.join(chunks)

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        html = self._fetch(SOURCE, 2_000_000)
        rows = self.parse_inventory(html.decode('utf-8'))
        captures = self.config.get('evidence_dir')
        if captures:
            Path(captures).mkdir(parents=True, exist_ok=True)
            (Path(captures) / 'urbanismo.html').write_bytes(html)
        source_urls = [SOURCE]
        for doc in rows[0]['documentos']:
            pdf = self._fetch(doc['url'], 20_000_000)
            if not pdf.startswith(b'%PDF-'):
                raise ValueError('Planning document is not a PDF: ' + doc['url'])
            doc['sha256'] = hashlib.sha256(pdf).hexdigest()
            doc['bytes'] = len(pdf)
            source_urls.append(doc['url'])
            if captures:
                (Path(captures) / Path(urlparse(doc['url']).path).name).write_bytes(pdf)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # The single planning inventory is refreshed as a complete snapshot.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
