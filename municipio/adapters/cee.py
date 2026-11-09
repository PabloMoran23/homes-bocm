"""Cee's municipal planning page; one instrument, not one row per attachment."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://cee.gal/gl/servizos/urbanismo-obras-publicas/'
TITLE = 'Plan Xeral de Ordenación Municipal do concello de Cee'


class CeeAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('main .entry-content')
        if content is None:
            raise ValueError('Missing municipal urbanism content')
        # This thematic page has no pagination. Fail if it becomes a paged list,
        # rather than quietly extracting only the first page.
        if soup.select('a[rel~=next], .pagination, .page-links, .nav-links'):
            raise ValueError('Pagination requires review before extraction')
        for a in content.select('a[href]'):
            if a.get_text(' ', strip=True).casefold() in {'seguinte', 'siguiente', 'next', 'seguinte »'}:
                raise ValueError('Pagination requires review before extraction')
        headings = [h for h in content.find_all(re.compile(r'^h[1-6]$'))
                    if h.get_text(' ', strip=True) == TITLE]
        if len(headings) != 1:
            raise ValueError('Missing or ambiguous Cee PXOM heading')
        paragraphs, documents, ids = [], {}, set()
        for node in headings[0].next_elements:
            if getattr(node, 'name', None) in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
                break
            if getattr(node, 'name', None) == 'p':
                paragraphs.append(node.get_text(' ', strip=True))
            if getattr(node, 'name', None) != 'a' or not node.get('href'):
                continue
            url = urljoin(SOURCE, node['href'])
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname not in {'cmatv.xunta.gal', 'medioambiente.xunta.gal'}:
                raise ValueError('Unreviewed PXOM attachment provenance')
            query_id = parse_qs(parsed.query).get('_aaeRunning_WAR_aae_id', [])
            path_id = re.search(r'/documentos_AAE/(\d+)/', parsed.path)
            doc_ids = query_id or ([path_id[1]] if path_id else [])
            if len(doc_ids) != 1 or not doc_ids[0].isdigit():
                raise ValueError('Missing environmental instrument identifier')
            ids.add(doc_ids[0])
            label = node.get_text(' ', strip=True)
            match = re.search(r'(\d{2}/\d{2}/\d{4})$', label)
            doc_date = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None
            documents[url] = {
                'titulo': label, 'url': url, 'fecha_documento': doc_date,
                'fecha_documento_semantica': 'fecha rotulada por el inventario municipal',
                'procedencia': SOURCE,
                'contenido_verificado': False,
            }
        description = '\n'.join(paragraphs)
        required = ('Documento de consultas', 'Borrador do plan',
                    'Documento inicial estratéxico', 'Documento de alcance')
        if len(ids) != 1 or not all(any(d['titulo'].startswith(t) for d in documents.values()) for t in required):
            raise ValueError('Incomplete or mixed PXOM document inventory')
        if 'inmerso na elaboración do PXOM' not in description:
            raise ValueError('PXOM phase changed; review municipal narrative')
        instrument_id = next(iter(ids))
        return [{
            'id': f'cee-pxom-aae-{instrument_id}',
            'municipio': 'Cee', 'codigo_ine': '15023', 'provincia': 'A Coruña',
            'titulo': TITLE, 'tipo': 'planeamiento urbanístico',
            'fase': 'en elaboración', 'descripcion': description,
            'expediente': f'AAE {instrument_id}',
            'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'urbanismo_municipal',
            'documentos': list(documents.values()),
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'cobertura': 'parcial: ficha municipal del PXOM; sin histórico ni licencias',
        }]

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source': SOURCE}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=30, stream=True,
                          headers={'User-Agent': 'municipio-cee/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'cee.gal':
                raise ValueError('Unexpected municipal source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Municipal page exceeds reviewed size')
                chunks.append(chunk)
            raw = b''.join(chunks)
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_bytes(raw)
        rows = self.parse_projects(raw.decode('utf-8'))
        return self._write(out_jsonl, rows)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete refresh of this single thematic page; no date-based filtering.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
