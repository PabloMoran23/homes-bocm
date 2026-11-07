"""Municipal PMUS document inventory; no inferred approval or implementation."""
from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://penarroyapueblonuevo.es/ayuntamiento/ayuntamiento-documentos/'
HOST = 'penarroyapueblonuevo.es'


def norm(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower().split())


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.entry-content')
    if content is None:
        raise ValueError('Missing municipal document inventory')
    # This inventory is a single page. Fail rather than silently accept a new
    # paginated layout (including WordPress multipage posts).
    if soup.select('link[rel~=next], a[rel~=next], .pagination a[href], .page-links a[href], .nav-links a[href]'):
        raise ValueError('Pagination detected; inventory coverage needs review')
    for a in content.select('a[href]'):
        if norm(a.get_text(' ', strip=True)) in {'siguiente', 'next', 'siguiente pagina', 'mas documentos'}:
            raise ValueError('Additional inventory page detected')
    groups = {}
    for block in content.select('.et_pb_text_inner'):
        heading = block.find('h2', recursive=False)
        if not heading or norm(heading.get_text(' ', strip=True)) != 'plan de movilidad urbana sostenible':
            continue
        title = heading.get_text(' ', strip=True)
        documents = groups.setdefault(title, {})
        for a in block.select('a[href]'):
            target = urljoin(url, a['href'])
            parsed = urlparse(target)
            if (parsed.scheme != 'https' or parsed.hostname != HOST
                    or not parsed.path.startswith('/wp-content/uploads/')
                    or not parsed.path.lower().endswith('.pdf')):
                raise ValueError('Unexpected PMUS document URL')
            label = a.get_text(' ', strip=True)
            if not label:
                raise ValueError('Unnamed PMUS document')
            documents.setdefault(target, {'titulo': label, 'url': target})
    if not groups or any(not docs for docs in groups.values()):
        raise ValueError('No documented municipal PMUS found')
    return [
        {'id': 'penarroya-pueblonuevo-plan-' + hashlib.sha256((url + norm(title)).encode()).hexdigest()[:16],
         'municipio': 'Peñarroya-Pueblonuevo', 'codigo_ine': '14052', 'provincia': 'Córdoba',
         'titulo': title, 'tipo': 'plan_movilidad_urbana_sostenible',
         'source': 'ayuntamiento', 'origen': 'inventario_documental_municipal',
         'url': url, 'inventory_url': url, 'documentos': list(docs.values()),
         'publication_ready': False, 'geometry_status': 'unavailable',
         'coverage': 'Inventario documental del PMUS; sin acreditar aprobación, vigencia ni ejecución.'}
        for title, docs in groups.items()
    ]


class PenarroyaPueblonuevoAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'
            response = session.get(SOURCE, timeout=40)
            response.raise_for_status()
            if response.url != SOURCE:
                raise ValueError('Unexpected inventory redirect')
            html = response.content.decode('utf-8')
            rows = parse_inventory(html, response.url)
            capture = self.config.get('evidence_dir')
            if capture:
                capture = Path(capture)
                capture.mkdir(parents=True, exist_ok=True)
                (capture / 'inventory.html').write_text(html, encoding='utf-8')
            # Verify every linked document, reading only its initial bytes.
            for row in rows:
                for i, doc in enumerate(row['documentos']):
                    with session.get(doc['url'], timeout=40, stream=True) as pdf:
                        pdf.raise_for_status()
                        prefix = next(pdf.iter_content(1024), b'')
                        if urlparse(pdf.url).hostname != HOST or not prefix.startswith(b'%PDF-'):
                            raise ValueError('Document is not an official PDF: ' + doc['url'])
                        doc['verified_url'] = pdf.url
                        doc['content_type'] = pdf.headers.get('Content-Type')
                        if capture:
                            (capture / f'pmus-{i + 1}.pdf.prefix').write_bytes(prefix)
        return self._write(out_jsonl, rows)

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows), 'coverage': 'current_pmus_document_inventory',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Refresh the complete scoped inventory; no date-based incremental cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**self._write(out_jsonl, []), 'disabled': True,
                'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
