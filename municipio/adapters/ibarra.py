"""Ibarra's municipal planning document inventory (not a licence register)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.ibarra.eus/es/urbanismo'


class IbarraAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        articles = [a for a in soup.select('.journal-content-article')
                    if a.select_one('.tabs-navegacion')]
        if len(articles) != 1:
            raise ValueError('Expected one municipal planning tab inventory')
        article = articles[0]
        for a in article.select('a[href]'):
            if (a.get('rel') and 'next' in a['rel']) or a.get_text(' ', strip=True).casefold() in {
                'siguiente', 'next', 'hurrengoa', 'ver más', 'mostrar más'}:
                raise ValueError('Pagination detected; traversal requires review')
        if article.select('.pagination, .lfr-pagination, [data-next-page]'):
            raise ValueError('Pagination detected; traversal requires review')
        rows = []
        visited = set()
        for tab in article.select('.tabs-navegacion a[href]'):
            ref = tab['href']
            if not ref.startswith('#') or ref in visited:
                raise ValueError('Invalid or duplicate planning tab')
            visited.add(ref)
            panel = article.find(id=ref[1:])
            if panel is None:
                raise ValueError('Missing tab content')
            if tab.get_text(' ', strip=True) == 'DATOS GENERALES':
                continue  # Forms and historical general regulations are outside scope.
            headings = panel.select('h2')
            if len(headings) != 1:
                raise ValueError('Expected one instrument heading per planning tab')
            title = headings[0].get_text(' ', strip=True)
            if not re.search(r'\bPLAN\b|ESTUDIO DE DETALLE', title, re.I):
                raise ValueError('Unreviewed instrument type: ' + title)
            documents = {}
            for a in panel.select('a[href]'):
                original = urljoin(SOURCE, a['href'])
                parsed = urlsplit(original)
                if parsed.hostname != 'www.ibarra.eus' or not parsed.path.startswith('/documents/'):
                    raise ValueError('Unreviewed link in planning instrument: ' + original)
                uuid = parsed.path.rstrip('/').rsplit('/', 1)[-1]
                if not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', uuid):
                    raise ValueError('Missing stable document UUID')
                url = urlunsplit(('https', parsed.netloc, parsed.path, '', ''))
                doc = documents.setdefault(uuid, {
                    'id_documento': uuid, 'titulo': '', 'url': url,
                    'enlaces_fuente': [], 'procedencia': SOURCE + ref,
                })
                label = a.get_text(' ', strip=True).replace('\u200b', '').strip()
                if label and label not in doc['titulo']:
                    doc['titulo'] = (doc['titulo'] + ' ' + label).strip()
                if original not in doc['enlaces_fuente']:
                    doc['enlaces_fuente'].append(original)
            if not documents or not any('memoria' in d['titulo'].lower() for d in documents.values()):
                raise ValueError('Instrument lacks its substantive planning documents')
            key = hashlib.sha256(title.casefold().encode()).hexdigest()[:16]
            rows.append({
                'id': 'ibarra-proy-' + key,
                'municipio': 'Ibarra', 'codigo_ine': '20042', 'provincia': 'Gipuzkoa',
                'titulo': title,
                'tipo': 'estudio_de_detalle' if 'ESTUDIO DE DETALLE' in title.upper() else 'planeamiento_urbanistico',
                'url': SOURCE + ref, 'source': 'ayuntamiento',
                'origen': 'inventario_municipal_planeamiento',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None,
                'documentos': list(documents.values()),
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
                'cobertura': 'Documentación publicada en las pestañas de planeamiento; sin verificación de vigencia ni fechas de aprobación.',
            })
        if not rows:
            raise ValueError('Empty planning inventory; review source before replacing output')
        # Newly added panels must not be silently omitted if navigation changes.
        panels = {p['id'] for p in article.select('.tabs > div[id]')}
        if panels != {ref[1:] for ref in visited}:
            raise ValueError('Planning panels and navigation disagree')
        return rows

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source': SOURCE}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=35, headers={'User-Agent': 'municipio-ibarra/1.0'})
        response.raise_for_status()
        if urlsplit(response.url).path.rstrip('/') != '/es/urbanismo':
            raise ValueError('Unexpected source redirect')
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_bytes(response.content)
        return self._write(out_jsonl, self.parse_inventory(response.text))

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
