"""San Adrián's published municipal planning inventory (not a licence register)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://transparencia.sanadrian.es/documentacion/relevancia-juridica/urbanismo-plan-general-municipal/'
HOST = urlparse(SOURCE).hostname
LIMITATIONS = [
    'Snapshot of the transparency planning inventory, not all municipal planning or public works.',
    'The inventory lists amendments through February 2016; later municipal notices are outside coverage.',
    'Amendment dates are source labels of unspecified semantics, not inferred approval/publication dates.',
    'Scanned amendment PDFs are retained but not OCRed; no inferred instrument number or approval stage.',
    'No verified project geometry or granted-licence register; publication_ready is false.',
]


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    # Refuse a changed/paginated inventory instead of silently taking page one.
    if soup.select('a[rel~=next], .pagination, .page-numbers, .nav-links') or any(
        a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', 'siguiente página'}
        for a in soup.select('a[href]')
    ):
        raise ValueError('Planning inventory is paginated; crawler needs review')
    content = soup.select_one('article .entry-content, #post-1334 .entry-content')
    if content is None or 'Publicación del Plan General Municipal de San Adrián' not in content.get_text(' ', strip=True):
        raise ValueError('Missing municipal planning inventory/narrative')
    rows = {}
    for item in content.select('ul.lista-items > li'):
        label = item.get_text(' ', strip=True)
        if not re.match(r'^(Plan General Municipal\.|Modificación\s)', label):
            raise ValueError(f'Unreviewed inventory entry: {label}')
        docs = {}
        for a in item.select('a[href]'):
            url = urljoin(SOURCE, a['href']).split('#')[0]
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname != HOST or not parsed.path.lower().endswith('.pdf'):
                raise ValueError('Unexpected planning document link')
            docs[url] = {'titulo': a.get_text(' ', strip=True), 'url': url,
                         'inventory_url': SOURCE, 'source_label': label}
        if not docs:
            raise ValueError('Planning entry has no source documents')
        primary = next(iter(docs))
        key = 'san-adrian-plan-' + hashlib.sha256(primary.encode()).hexdigest()[:16]
        is_plan = label.startswith('Plan General Municipal.')
        span = item.select_one('.txt-item')
        title = ('Plan General Municipal de San Adrián' if is_plan else
                 (span.get_text(' ', strip=True) if span else label.replace('Descargar (PDF)', '').strip()) +
                 ' — Plan General Municipal de San Adrián')
        row = {
            'id': key, 'municipio': 'San Adrián', 'codigo_ine': '31215', 'provincia': 'Navarra',
            'titulo': title, 'tipo': 'plan_general_municipal' if is_plan else 'modificacion_planeamiento',
            'url': primary, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_planeamiento_transparencia', 'source_label': label,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'fase': None, 'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'geometry_status': 'unavailable',
            'documentos': list(docs.values()),
        }
        if is_plan:
            narrative = content.select_one('#lipsum')
            row['descripcion'] = narrative.get_text(' ', strip=True) if narrative else None
            # The page refers to both the approval notice and publication of the
            # regulations. Preserve its wording; do not collapse those dates.
        if key in rows:
            existing = rows[key]
            known = {d['url'] for d in existing['documentos']}
            existing['documentos'].extend(d for d in row['documentos'] if d['url'] not in known)
        else:
            rows[key] = row
    if not rows or not any(r['tipo'] == 'plan_general_municipal' for r in rows.values()):
        raise ValueError('No verified general plan found')
    return list(rows.values())


class SanAdrianAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url: str, max_bytes: int) -> bytes:
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipal-planning-inventory/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != HOST:
                raise ValueError('Unexpected source redirect')
            chunks = []
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError('Source exceeds reviewed size limit')
                chunks.append(chunk)
            return b''.join(chunks)

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        html = self._fetch(SOURCE, 2_000_000)
        rows = parse_inventory(html.decode('utf-8'))
        captures = Path(self.config['evidence_dir']) if self.config.get('evidence_dir') else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'inventory.html').write_bytes(html)
        fetched = {}
        for row in rows:
            for doc in row['documentos']:
                url = doc['url']
                if url not in fetched:
                    body = self._fetch(url, 30_000_000)
                    if not body.startswith(b'%PDF-'):
                        raise ValueError(f'Planning document is not a PDF: {url}')
                    fetched[url] = hashlib.sha256(body).hexdigest()
                    if captures:
                        (captures / (fetched[url] + '.pdf')).write_bytes(body)
                doc['sha256'] = fetched[url]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'documents': len(fetched),
                'source_urls': [SOURCE, *fetched], 'limitations': LIMITATIONS,
                'coverage': 'complete_single_page_transparency_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
