"""Partial municipal planning inventory; no granted-licence claims."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.sanfulgencio.es/el-ayuntamiento/urbanismo-plan-general/'
LIMITATIONS = [
    'Partial inventory: only the municipal Plan General page, not all municipal works or planning.',
    'Link labelled Modificacion Puntual Nº 1 PGOU points to plan-general.zip containing '
    'general-plan drawings; excluded as an ambiguously identified instrument.',
    'No verified coordinates or geometry; no granted-licence inventory.',
    'Base-plan links are retained as listed; Plano-Orden.pdf returned HTTP 404 in a bounded verification probe.',
    'Linked base-plan PDFs are retained as documents, not OCR-parsed or converted to separate projects.',
]


def _norm(value: str) -> str:
    return ' '.join(value.lower().split())


def parse_inventory(html: str) -> tuple[list[dict[str, str]], dict[str, str], list[dict[str, str]]]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#main-content .et_pb_post_content')
    if content is None or 'urbanismo' not in soup.get_text(' ', strip=True).lower():
        raise ValueError('Missing municipal planning content')
    # A changed/paginated inventory must be reviewed, never silently cut off.
    if soup.select('a[rel~=next], .pagination, .page-numbers, .wp-pagenavi') or any(
        _norm(a.get_text(' ', strip=True)) in {'siguiente', 'next', '›', '»'}
        for a in content.select('a[href]')
    ):
        raise ValueError('Planning inventory pagination requires review')
    labels = {'memoria', 'normativa', 'ordenanza', 'planos', 'plano ordenación', 'impacto ambiental'}
    base_docs, modification, excluded = {}, {}, {}
    for a in content.select('a[href]'):
        title = a.get_text(' ', strip=True)
        label = _norm(title)
        url = urljoin(SOURCE, a['href'])
        parsed = urlparse(url)
        if parsed.hostname not in {'www.sanfulgencio.es', 'sanfulgencio.es'} or not parsed.path.startswith('/wp-content/uploads/'):
            raise ValueError('Unexpected link in planning inventory: ' + url)
        doc = {'titulo': title, 'url': url, 'source_url': SOURCE}
        if label in labels and parsed.path.lower().endswith('.pdf'):
            if label in base_docs and base_docs[label]['url'] != url:
                raise ValueError('Conflicting base-plan documents')
            base_docs[label] = doc
        elif re.fullmatch(r'modificacion puntual n[º°o]?\s*3 pgou', label) and parsed.path.lower().endswith('.pdf'):
            modification[url] = doc
        elif re.fullmatch(r'modificacion puntual n[º°o]?\s*1 pgou', label) and parsed.path.endswith('/plan-general.zip'):
            excluded[url] = doc
        else:
            raise ValueError('Unreviewed planning document: ' + title)
    if set(base_docs) != labels or len(modification) != 1:
        raise ValueError('Incomplete or ambiguous planning inventory')
    return list(base_docs.values()), next(iter(modification.values())), list(excluded.values())


def parse_notice(text: str) -> dict[str, str]:
    """Use labelled BOP publication and CTU agreement, not other historical dates."""
    flat = ' '.join(text.split())
    if not re.search(r'SAN FULGENCIO\. Modificación Puntual n\.[ºo] 3 del Plan General', flat):
        raise ValueError('PDF does not identify San Fulgencio modification 3')
    if not re.search(r'Aprobar definitivamente la Modificación Puntual', flat, re.I):
        raise ValueError('Missing definitive decision in planning notice')
    publication = re.search(r'Boletín Oficial de la Provincia de Alicante Nº \d+ de (\d{2})/(\d{2})/(\d{4})', flat)
    agreement = re.search(r'La Comisión Territorial de Urbanismo, en sesión celebrada el día (\d{1,2}) de febrero de (\d{4}), adoptó', flat)
    base = re.search(r'Plan General aprobado definitivamente por resolución del Conseller competente en urbanismo de fecha (\d{1,2}) de mayo de (\d{4})', flat)
    dossier = re.search(r'EXPTE\. ([\d/]+)\.- SAN FULGENCIO\..*?\((PL-\s*[\d/]+)\)', flat)
    if not all((publication, agreement, base, dossier)):
        raise ValueError('Notice date or dossier anchors changed; review required')
    return {
        'fecha_publicacion': date(int(publication[3]), int(publication[2]), int(publication[1])).isoformat(),
        'fecha_acuerdo': date(int(agreement[2]), 2, int(agreement[1])).isoformat(),
        'base_fecha_aprob': date(int(base[2]), 5, int(base[1])).isoformat(),
        'expediente': dossier[1], 'expediente_planeamiento': re.sub(r'\s+', '', dossier[2]),
    }


class SanFulgencioAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug: str, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.sanfulgencio.es')

    @staticmethod
    def _fetch(url: str, limit: int) -> bytes:
        # Public site rejects requests' default UA with HTTP 403.
        with requests.get(url, timeout=(15, 60), stream=True,
                          headers={'User-Agent': 'Mozilla/5.0 (municipio San Fulgencio public planning inventory)'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname not in {'www.sanfulgencio.es', 'sanfulgencio.es'}:
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Source exceeds reviewed response size')
                chunks.append(chunk)
            return b''.join(chunks)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        html = self._fetch(SOURCE, 2_000_000)
        docs, mod, excluded = parse_inventory(html.decode('utf-8'))
        pdf = self._fetch(mod['url'], 4_000_000)
        if not pdf.startswith(b'%PDF-'):
            raise ValueError('Planning notice is not a PDF')
        with tempfile.TemporaryDirectory(prefix='san-fulgencio-') as folder:
            source_pdf = Path(folder) / 'notice.pdf'
            source_pdf.write_bytes(pdf)
            proc = subprocess.run(['pdftotext', '-layout', str(source_pdf), '-'],
                                  capture_output=True, check=True, timeout=30)
        dates = parse_notice(proc.stdout.decode('utf-8'))
        rows = []
        for key, title, documents in [
            ('pgou', 'Plan General de San Fulgencio', docs),
            ('pgou-modificacion-3', mod['titulo'], [mod]),
        ]:
            row = {
                'id': 'san-fulgencio-proy-' + key,
                'municipio': 'San Fulgencio', 'provincia': 'Alicante', 'codigo_ine': '03118',
                'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
                'url': SOURCE, 'url_documento': documents[0]['url'], 'documentos': documents,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': dates['base_fecha_aprob'], 'fase': 'aprobación definitiva',
                'date_provenance': {'fecha_aprob': {'url': mod['url'], 'context': 'Antecedente del Plan General, página 2 del BOP'}},
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'coverage': 'partial', 'limitations': LIMITATIONS,
            }
            if key.endswith('-3'):
                row.update({k: dates[k] for k in ('fecha_publicacion', 'fecha_acuerdo', 'expediente', 'expediente_planeamiento')})
                row['fecha_aprob'] = dates['fecha_acuerdo']
                row['date_provenance'] = {k: {'url': mod['url'], 'context': 'BOP nº 50: cabecera y acuerdo CTU, página 1'} for k in ('fecha_publicacion', 'fecha_acuerdo', 'fecha_aprob')}
            rows.append(row)
        # Save only after all source parsing succeeds; a failure preserves prior output.
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(out_jsonl)
        # Optional local source captures, kept out of source control.
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'inventory.html').write_bytes(html)
            (capture / 'notice.pdf').write_bytes(pdf)
            (capture / 'notice.txt').write_bytes(proc.stdout)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, *[d['url'] for d in docs], mod['url']],
                'excluded_documents': excluded, 'limitations': LIMITATIONS, 'publication_ready': False,
                'source_sha256': {'inventory': hashlib.sha256(html).hexdigest(), 'notice': hashlib.sha256(pdf).hexdigest()}}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete snapshot of this single inventory page, no incremental date filter.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
