"""Zuera's municipal planning inventory: complete document groups, partial coverage."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.ayunzuera.com/areas/urbanismo/planeamiento/'
LIMITATIONS = [
    'Partial municipal coverage: only the documents listed in the planning inventory; '
    'not a complete historical register, works inventory or licence register.',
    'Dates in link labels are retained verbatim, not promoted to agreement, approval '
    'or publication dates without parsing the underlying documents.',
    'No verified project geometry; coordinates are null and publication_ready is false.',
    'PDF links are inventoried, not automatically downloaded or interpreted; '
    'their current legal validity and embedded corrections are not consolidated.',
]


def _norm(text: str) -> str:
    return ' '.join(text.split()).casefold()


class ZueraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug: str, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.ayunzuera.com')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('main#page-content')
        if not main or not main.find('h1', string=re.compile(r'^\s*Planeamiento\s*$')):
            raise ValueError('Missing Zuera planning inventory')
        if main.select('[rel~=next], .pagination, .nav-links, [data-pagination]'):
            raise ValueError('Inventory pagination detected; refusing a truncated snapshot')
        for a in main.select('a[href]'):
            if _norm(a.get_text(' ', strip=True)) in {'siguiente', 'next', 'más resultados', 'cargar más'}:
                raise ValueError('Inventory pagination detected')

        rows: dict[str, dict] = {}
        current = None
        section = None
        started = ended = False

        def group(key, title, kind, parent=None):
            nonlocal current
            current = key
            if key in rows:
                raise ValueError('Repeated instrument heading: ' + key)
            rows[key] = {
                'id': 'zuera-proy-' + key, 'municipio': 'Zuera',
                'codigo_ine': '50298', 'provincia': 'Zaragoza',
                'titulo': title, 'tipo': kind, 'fase': None,
                'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': SOURCE, 'source': 'ayuntamiento',
                'origen': 'inventario_municipal_planeamiento',
                'instrumento_padre': parent, 'documentos': [],
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False,
                'limitaciones': LIMITATIONS,
            }

        subheads = {
            'textos', 'planos de ordenación', 'alineaciones', 'clasificación',
            'estructura urbana', 'no urbanizable', 'ordenación-usos',
            'sistemas generales', 'unidades ejecución', 'planos:', 'textos:',
        }
        for node in main.find_all(['h2', 'h3', 'h4', 'p', 'a']):
            text = node.get_text(' ', strip=True)
            norm = _norm(text)
            if node.name in {'h2', 'h3', 'h4'}:
                if norm.startswith('plan general de ordenacion urbana'):
                    if started:
                        raise ValueError('Repeated PGOU inventory')
                    started = True
                    group('pgou', text + ' — Zuera', 'plan_general')
                elif not started:
                    continue
                elif norm == 'noticias urbanismo':
                    ended = True
                    break
                elif norm == 'modificaciones aisladas':
                    section, current = 'pgou', None
                elif norm.startswith('modificaciones aisladas') and 'zuera sur' in norm:
                    section, current = 'pp-zuera-sur', None
                elif norm == 'zuera sur':
                    group('pp-zuera-sur', 'Plan Parcial Zuera Sur', 'plan_parcial')
                elif norm == 'plan de movilidad urbana sostenible':
                    group('pmus', text + ' de Zuera', 'plan_movilidad')
                elif norm not in subheads:
                    # Empty headings are harmless; documents below an unknown
                    # section must fail instead of being assigned to an old plan.
                    current = None
            elif not started:
                continue
            elif node.name == 'p' and not node.find('a'):
                match = re.match(r'MODIFICACI[OÓ]N AISLADA N[º°]\s*(\d+)\b', text, re.I)
                if match:
                    if section not in {'pgou', 'pp-zuera-sur'}:
                        raise ValueError('Modification outside a known parent plan')
                    group(f'{section}-mod-{match[1]}', text + ' — ' +
                          ('TRPGOU de Zuera' if section == 'pgou' else 'Plan Parcial Zuera Sur'),
                          'modificacion_planeamiento', 'zuera-proy-' + section)
            elif node.name == 'a' and node.get('href'):
                url = urljoin(SOURCE, node['href'])
                parsed = urlparse(url)
                if not parsed.path.lower().endswith('.pdf'):
                    continue
                if parsed.hostname != 'www.ayunzuera.com' or not parsed.path.startswith('/wp-content/uploads/'):
                    raise ValueError('Unreviewed document host or path: ' + url)
                if current is None:
                    raise ValueError('Document outside a recognized instrument: ' + text)
                docs = rows[current]['documentos']
                if not any(d['url'] == url for d in docs):
                    docs.append({'titulo': text, 'url': url, 'url_origen': SOURCE})
        if not started or not ended or not rows or any(not r['documentos'] for r in rows.values()):
            raise ValueError('Incomplete or empty planning inventory')
        for row in rows.values():
            row['url_documento'] = row['documentos'][0]['url']
        return list(rows.values())

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        session = requests.Session()
        session.mount('https://', HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1,
                      status_forcelist=[429, 500, 502, 503, 504])))
        with session:
            with session.get(SOURCE, timeout=(15, 45), stream=True,
                             headers={'User-Agent': 'Mozilla/5.0 (compatible; MunicipioZuera/1.0)'}) as response:
                response.raise_for_status()
                if urlparse(response.url).path.rstrip('/') != urlparse(SOURCE).path.rstrip('/'):
                    raise ValueError('Unexpected inventory redirect')
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 3_000_000:
                        raise ValueError('Inventory exceeds reviewed response limit')
                    chunks.append(chunk)
                content = b''.join(chunks)
                html = content.decode('utf-8')
        rows = self.parse_projects(html)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'planeamiento.html').write_bytes(content)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temporary = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'documents': sum(len(r['documentos']) for r in rows),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Refresh the entire single-page inventory; no date cursor or row cap.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        return {'status': 'disabled', 'rows': 0,
                'reason': 'No verified granted-licence inventory; forms are excluded'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
