"""Caudete's published base NNSS inventory, grouped as one planning instrument."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.caudete.org/ayuntamiento/obras-y-urbanismo-legislacion/'
LIMITATION = ('Inventario municipal del texto base de las Normas Subsidiarias. '
              'La fuente excluye modificaciones puntuales y estudios de detalle. '
              'No constituye un inventario completo del planeamiento ni de obras o licencias.')


def _norm(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                   if not unicodedata.combining(c))


def _document_url(href: str) -> str:
    parts = urlsplit(urljoin(SOURCE, href))
    if parts.hostname not in {'www.caudete.org', 'caudete.org', 'docm.jccm.es'}:
        raise ValueError('Unreviewed document host in Caudete planning inventory')
    if parts.scheme not in {'http', 'https'} or parts.username or parts.password:
        raise ValueError('Invalid planning document URL')
    # Municipal legacy HTTP links also serve the same paths over HTTPS.
    return urlunsplit(('https', parts.netloc, quote(parts.path, safe='/%'), parts.query, ''))


class CaudeteAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.caudete.org')

    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        entries = soup.select('div.entry')
        if len(entries) != 1:
            raise ValueError('Expected one municipal legislation inventory')
        entry = entries[0]
        heading = entry.find('h1')
        if not heading or 'obras y urbanismo' not in _norm(heading.get_text(' ', strip=True)):
            raise ValueError('Missing Caudete urbanism inventory heading')
        # The reviewed source is a complete, unpaginated static document index.
        # Fail visibly if it becomes paginated; never silently take page one.
        if soup.select('[rel~=next], .pagination, .wp-pagenavi, a.next, .page-links'):
            raise ValueError('Inventory pagination detected; crawler must be reviewed')
        for a in entry.select('a[href]'):
            if re.fullmatch(r'(siguiente|next|[»›])', a.get_text(' ', strip=True), re.I):
                raise ValueError('Inventory pagination detected')

        documents = {}
        roles = set()
        descriptions = []
        for li in entry.find_all('li'):
            # Nested wrapper lists contain unrelated state/local legislation.
            if li.find('li'):
                continue
            text = li.get_text(' ', strip=True)
            normalized = _norm(text)
            if 'normas subsidiarias' in normalized:
                if normalized.startswith('texto de '):
                    role = 'normativa'
                    if 'caudete' not in normalized:
                        raise ValueError('Normative text does not identify Caudete')
                elif normalized.startswith('planos de '):
                    role = 'cartografia'
                elif normalized.startswith('acuerdo de '):
                    role = 'acuerdo_aprobacion'
                elif normalized.startswith('aprobacion definitiva texto refundido'):
                    role = 'publicacion_texto_refundido'
                else:
                    raise ValueError('New NNSS document category requires review')
            elif normalized.startswith('planos agrupados'):
                role = 'cartografia'
            else:
                continue
            anchors = li.select('a[href]')
            if not anchors or any(a['href'].strip() in {'', '#'} for a in anchors):
                raise ValueError('Planning document category lacks usable links')
            descriptions.append(text)
            roles.add(role)
            for a in anchors:
                url = _document_url(a['href'])
                documents.setdefault(url, {
                    'titulo': text, 'tipo': role,
                    'enlace_texto': a.get_text(' ', strip=True),
                    'url': url, 'url_original': urljoin(SOURCE, a['href']),
                    'source_url': SOURCE,
                })
        required = {'normativa', 'cartografia', 'acuerdo_aprobacion', 'publicacion_texto_refundido'}
        if not required.issubset(roles):
            raise ValueError('Incomplete NNSS inventory: missing required document categories')
        return [{
            'id': 'caudete-proy-nnss-texto-refundido',
            'municipio': 'Caudete', 'provincia': 'Albacete', 'codigo_ine': '02025',
            'titulo': 'Normas Subsidiarias de Planeamiento de Caudete — texto refundido y planos',
            'tipo': 'planeamiento_urbanistico',
            'fase': 'aprobación definitiva',
            'fase_fuente': 'Título del enlace municipal de aprobación definitiva del texto refundido',
            # The index supplies no explicit dates. Filenames and crawl dates are not events.
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_nnss',
            'descripcion': '\n'.join(descriptions),
            'documentos': list(documents.values()), 'cobertura': LIMITATION,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'Sin geometría verificada; planos documentales no georreferenciados por este adaptador',
        }]

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=(10, 45), stream=True,
                          headers={'User-Agent': 'municipio-caudete/1.0'}) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname != 'www.caudete.org':
                raise ValueError('Unexpected inventory redirect')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected HTML inventory')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Inventory exceeds reviewed size; no partial extraction')
                chunks.append(chunk)
            content = b''.join(chunks)
        rows = self.parse_projects(content.decode('utf-8'))
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory.html').write_bytes(content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': [LIMITATION, 'Fechas no extraídas del contenido de los PDFs',
                                'Sin geometría verificada; publication_ready=false'],
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete refresh of this one-page inventory; no incremental cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0,
                'reason': 'No se ha verificado un registro público de licencias concedidas'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
