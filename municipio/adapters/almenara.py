"""Almenara's informative planning consolidation, hosted by Generalitat Valenciana."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://mediambient.gva.es/auto/urbanismo/Textos_consolidados/'
          '2.%20Textos%20consolidados%2C%20Orden%2010-2022/12011%20Almenara/')
INDEX = '00_TC_Indice_de_documentos.pdf'
LIMITATIONS = [
    'Partial coverage: only the GVA-hosted informative planning consolidation; not a full municipal project inventory.',
    'Consolidation is informative and has no legal value; no new plan approval is inferred.',
    'Publication/agreement/approval dates and project geometry are not verified.',
    'No granted-licence inventory; application forms and procurement notices are excluded.',
    'Attachment URLs retained from the complete directory; only the general index PDF is downloaded and text-validated.',
]


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1#indextitle')
    if not heading or not heading.get_text().endswith('/12011 Almenara'):
        raise ValueError('Wrong municipality or changed GVA inventory')
    for a in soup.select('a[href], link[href]'):
        if (a.get('rel') and 'next' in a.get('rel')) or re.fullmatch(
                r'(next|siguiente|següent|[»›])', a.get_text(' ', strip=True), re.I):
            raise ValueError('Pagination detected; refusing partial snapshot')
    docs = {}
    for a in soup.select('#indexlist td.indexcolname a[href]'):
        url = urljoin(SOURCE, a['href'])
        parts = urlsplit(url)
        if (not url.startswith(SOURCE) or parts.query or parts.fragment or
                '/' in unquote(url[len(SOURCE):]) or not parts.path.lower().endswith('.pdf')):
            raise ValueError('Unexpected directory entry; coverage requires review')
        docs[url] = {'titulo': a.get_text(' ', strip=True), 'url': url,
                     'origen': 'Generalitat Valenciana; documentación municipal consolidada'}
    names = {unquote(url.rsplit('/', 1)[-1]) for url in docs}
    if not {INDEX, '01_TC_Documento_de_sintesis.pdf', '03_TC_Ordenanzas_de_las_NNSS.pdf',
            '04_Ordenanzas_del_Planeamiento_de_Desarrollo.pdf'} <= names:
        raise ValueError('Incomplete consolidation inventory')
    return [docs[url] for url in sorted(docs)]


def parse_project(documents: list[dict], index_text: str) -> dict:
    text = ' '.join(index_text.split())
    title = re.search(r'Texto Consolidado de planeamiento urbanístico\s+de Almenara', text)
    if not title or not all(phrase in text for phrase in (
            'carácter informativo', 'no tiene valor jurídico',
            'ÍNDICE DE DOCUMENTOS QUE COMPONEN EL TEXTO CONSOLIDADO')):
        raise ValueError('Index PDF does not verify the Almenara consolidation')
    return {
        'id': 'almenara-planeamiento-texto-consolidado-orden-10-2022',
        'municipio': 'Almenara', 'provincia': 'Castellón', 'codigo_ine': '12011',
        'titulo': title[0], 'tipo': 'texto_consolidado_planeamiento',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': SOURCE, 'url_documento': urljoin(SOURCE, INDEX),
        'source': 'generalitat_valenciana', 'origen': 'textos_consolidados_planeamiento_municipal',
        'descripcion': 'Conjunto documental de planeamiento municipal consolidado: síntesis, planos y ordenanzas. '
                       'Documento informativo sin valor jurídico; consultar los instrumentos originales para información con plena validez jurídica.',
        'documentos': documents, 'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'limitaciones': LIMITATIONS,
        'documento_indice_sha256_texto': hashlib.sha256(index_text.encode()).hexdigest(),
    }


class AlmenaraAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url: str, capture_name: str, max_bytes: int) -> bytes:
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-almenara/1.0'}) as response:
            response.raise_for_status()
            if response.url != url:
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError('Source exceeds response limit; refusing truncation')
                chunks.append(chunk)
            content = b''.join(chunks)
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir'])
            path.mkdir(parents=True, exist_ok=True)
            (path / capture_name).write_bytes(content)
        return content

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        docs = parse_inventory(self._fetch(SOURCE, 'inventory.html', 2_000_000).decode('utf-8'))
        pdf = self._fetch(urljoin(SOURCE, INDEX), 'index.pdf', 10_000_000)
        if not pdf.startswith(b'%PDF-'):
            raise ValueError('Expected an index PDF')
        # Poppler is preinstalled; no Python dependency or software installation.
        with tempfile.TemporaryDirectory(prefix='almenara-') as directory:
            path = Path(directory) / 'index.pdf'
            path.write_bytes(pdf)
            result = subprocess.run(['pdftotext', '-layout', str(path), '-'],
                                    capture_output=True, check=True, timeout=30)
        row = parse_project(docs, result.stdout.decode('utf-8'))
        self._write(out_jsonl, [row])
        return {'status': 'ok', 'rows': 1, 'documents': len(docs),
                'source_urls': [SOURCE, urljoin(SOURCE, INDEX)], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        """Refresh the entire single-directory snapshot; no date-based cutoff."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
