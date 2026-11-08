"""Moncofa's municipal technical-document inventory (partial project coverage)."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://moncofa.com/es/urbanismo/'


def _norm(text):
    return ' '.join(unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().upper().split())


class MoncofaAyuntamientoAdapter(AyuntamientoAdapter):
    """Refresh complete single-page public-information project sections, no licences."""

    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        # Fail closed if this static inventory ever gains pagination/load-more.
        for link in soup.select('a[href], button'):
            label = _norm(link.get_text(' ', strip=True))
            rel = link.get('rel', [])
            if ('next' in rel or label in {'SIGUIENTE', 'NEXT', 'CARGAR MAS', 'VER MAS'}
                    or re.search(r'/page/\d+|[?&](?:paged|page)=\d+', link.get('href', ''))):
                raise ValueError('Inventory pagination detected; crawler review required')
        rows = {}
        for item in soup.select('.elementor-toggle-item'):
            heading = item.select_one('.elementor-tab-title')
            if heading is None:
                continue
            title = heading.get_text(' ', strip=True)
            normal = _norm(title)
            if not normal.startswith('INFORMACION PUBLICA'):
                continue
            if 'PROYECTO FINALIZACION URBANIZACION BELCAIRE SUR' in normal:
                key, kind = 'finalizacion-urbanizacion-belcaire-sur', 'proyecto_urbanizacion'
            elif ('ACTUACION INTEGRADA' in normal and 'MANZANAS 1 Y 2' in normal
                  and 'CASABLANCA' in normal):
                key, kind = 'pai-manzanas-1-2-casablanca', 'programa_actuacion_integrada'
            else:
                raise ValueError(f'Unreviewed public-information section: {title}')
            if key in rows:
                raise ValueError(f'Duplicate instrument section: {key}')
            content = item.select_one('.elementor-tab-content')
            if content is None:
                raise ValueError(f'Missing technical inventory: {title}')
            docs = {}
            for a in content.select('a[href]'):
                label = a.get_text(' ', strip=True)
                # Empty PDF-icon anchors in this CMS point to unrelated dossiers.
                # Only explicitly labelled document links establish provenance.
                if not label:
                    continue
                url = urljoin(SOURCE, a['href'])
                parsed = urlparse(url)
                if (parsed.scheme != 'https' or parsed.hostname != 'moncofa.com'
                        or not parsed.path.startswith('/wp-content/uploads/')
                        or not parsed.path.lower().endswith('.pdf')):
                    raise ValueError(f'Unexpected labelled document URL: {url}')
                docs.setdefault(url, {'titulo': label, 'url': url, 'url_fuente': SOURCE})
            labels = _norm(' '.join(d['titulo'] for d in docs.values()))
            if not all(term in labels for term in ('MEMORIA', 'PLANOS', 'PRESUPUESTO')):
                raise ValueError(f'Incomplete technical-document section: {title}')
            rows[key] = {
                'id': 'moncofa-proy-' + key,
                'municipio': 'Moncofa', 'codigo_ine': '12077', 'provincia': 'Castellón',
                'titulo': title, 'tipo': kind, 'fase': 'información pública',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None,
                'date_status': 'La página inventario no explicita fechas; no se infieren de archivos ni del rastreo',
                'url': SOURCE, 'url_documento': next(iter(docs)),
                'documentos': list(docs.values()),
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_urbanismo',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'coverage': 'Parcial: secciones de información pública con documentos técnicos; no certifica vigencia del trámite ni ejecución',
            }
        if not rows:
            raise ValueError('No verified municipal public-information projects found')
        return list(rows.values())

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=(10, 45), stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-moncofa/1.0')
        }) as response:
            response.raise_for_status()
            if response.url.rstrip('/') != SOURCE.rstrip('/'):
                raise ValueError('Unexpected redirect from municipal source')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Inventory exceeds reviewed response size')
                chunks.append(chunk)
            raw = b''.join(chunks)
        rows = self.parse_projects(raw.decode('utf-8'))
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            Path(capture_dir).mkdir(parents=True, exist_ok=True)
            (Path(capture_dir) / 'urbanismo.html').write_bytes(raw)
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'partial', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        # Do not overwrite any existing licence output when disabled.
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
