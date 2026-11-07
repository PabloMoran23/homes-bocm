"""Official Bargas PAU inventory: one record per documented urbanisation project."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.bargas.es/transparencia/urbanismo-y-obras/anuncios-expedientes-de-planeamiento-y-paus/'


class BargasAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.find('h1')
        if not heading or heading.get_text(' ', strip=True) != 'Anuncios expedientes de planeamiento y PAUs':
            raise ValueError('Bargas inventory heading missing')
        content = soup.select_one('section.main-container .col-md-8')
        if content is None:
            raise ValueError('Bargas inventory content missing')
        # This is a static document inventory, not the paginated news category.
        # If the source acquires pagination, fail rather than emit a partial snapshot.
        for a in soup.select('a[href]'):
            label = a.get_text(' ', strip=True).lower()
            if (set(a.get('rel', [])) & {'next', 'prev'} or
                    re.search(r'/page/|[?&](?:paged|page)=', a['href']) or
                    label in {'siguiente', 'anterior', 'next', 'previous'}):
                raise ValueError('Inventory pagination detected; traversal requires review')
        if soup.select('.pagination, .page-numbers, .nav-links'):
            raise ValueError('Inventory pagination detected; traversal requires review')
        rows = {}
        for section in content.find_all('h3'):
            label = section.get_text(' ', strip=True)
            match = re.fullmatch(r'UA\s*[–—-]\s*N[º°o]?\.?\s*(\d+)', label, re.I)
            if not match:
                raise ValueError(f'Unreviewed inventory section: {label}')
            unit = str(int(match[1]))
            listing = section.find_next_sibling('ul')
            if listing is None:
                raise ValueError(f'Missing document list for {label}')
            documents = {}
            technical = []
            for a in listing.select('a[href]'):
                title = a.get_text(' ', strip=True)
                url = urljoin(SOURCE, a['href'])
                parsed = urlparse(url)
                if (parsed.scheme != 'https' or parsed.hostname != 'www.bargas.es' or
                        not parsed.path.startswith('/wp-content/uploads/') or
                        not parsed.path.lower().endswith('.pdf')):
                    raise ValueError(f'Unreviewed document URL: {url}')
                project = re.match(r'^Proyecto de urbanización UA-(\d+)\s*[–—-]', title, re.I)
                if project and str(int(project[1])) != unit:
                    raise ValueError('Project document belongs to another unit')
                role = 'documento_tecnico' if project else 'documento_asociado'
                documents[url] = {'titulo': title, 'url': url, 'tipo': role, 'source_url': SOURCE}
                if project:
                    technical.append(re.split(r'\s+[–—-]\s+', title, maxsplit=1)[0])
            # A tender or contractor resolution alone never creates a project.
            if not technical:
                continue
            identifier = f'bargas-proy-urbanizacion-ua-{unit}'
            if identifier in rows:
                raise ValueError(f'Duplicate inventory section: {label}')
            rows[identifier] = {
                'id': identifier, 'municipio': 'Bargas', 'codigo_ine': '45019',
                'provincia': 'Toledo', 'titulo': technical[0],
                'tipo': 'proyecto_urbanizacion', 'ambito': label,
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_paus',
                'documentos': list(documents.values()),
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'coverage': 'Inventario municipal de PAUs; no registro completo de actuaciones ni licencias.',
            }
        if not rows:
            raise ValueError('No genuine project documents in Bargas inventory')
        return list(rows.values())

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        capture = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        if capture:
            capture.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-bargas/1.0'
            response = session.get(SOURCE, timeout=40)
            response.raise_for_status()
            if urlparse(response.url).hostname != 'www.bargas.es':
                raise ValueError('Inventory redirected away from municipality')
            response.encoding = 'utf-8'
            rows = self.parse_inventory(response.text)
            if capture:
                (capture / 'paus-live.html').write_bytes(response.content)
            checks = []
            for row in rows:
                for doc in row['documentos']:
                    # Inspect the actual PDF signature without downloading every large plan.
                    with session.get(doc['url'], timeout=40, stream=True) as pdf:
                        pdf.raise_for_status()
                        if urlparse(pdf.url).hostname != 'www.bargas.es':
                            raise ValueError('Document redirected away from municipality')
                        prefix = next(pdf.iter_content(chunk_size=1024), b'')
                        if not prefix.startswith(b'%PDF-'):
                            raise ValueError(f"Document is not a PDF: {doc['url']}")
                        checks.append({'url': doc['url'], 'status': pdf.status_code,
                                       'content_type': pdf.headers.get('Content-Type'),
                                       'pdf_signature': True})
            if capture:
                (capture / 'document-checks.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source': SOURCE, 'documents_checked': len(checks)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete inventory refresh, not an append-only stream or news backfill.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
