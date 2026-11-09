"""Berriz's municipal public-exhibition inventory (partial planning coverage)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.berriz.eus/es-ES/Servicios/Urbanismo/Paginas/expedientes-exposicion-publica.aspx'


class BerrizAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('#main-content')
        if not content or 'Expedientes en exposición pública' not in content.get_text(' ', strip=True):
            raise ValueError('Missing Berriz public-exhibition inventory')
        for control in content.select('a, button, input, select'):
            label = ' '.join([control.get_text(' ', strip=True), control.get('title', ''),
                              control.get('aria-label', ''), control.get('value', '')]).lower()
            href = control.get('href', '').lower()
            if (re.search(r'\b(siguiente|anterior|next|previous|página|pagina|hurrengoa)\b', label)
                    or control.get('rel') == ['next']
                    or re.search(r'(page=|paged=|startrow=|__dopostback)', href)):
                raise ValueError('Pagination detected; review traversal before accepting output')
        rows = {}
        for heading in content.select('#ProcedureZone h3.ms-WPTitle'):
            title = heading.get_text(' ', strip=True)
            if title.lower().startswith('ordenanza '):
                continue
            is_study = title.lower().startswith('estudio de detalle ')
            is_project = bool(re.search(r'información pública de proyecto', title, re.I))
            if not (is_study or is_project):
                continue
            block = heading.parent.parent
            docs = {}
            for a in block.select('.ms-WPBody a[href]'):
                url = urljoin(SOURCE, a['href'])
                parsed = urlparse(url)
                if (parsed.hostname != 'www.berriz.eus' or
                        not parsed.path.startswith('/es-ES/Servicios/Urbanismo/Documents/') or
                        not parsed.path.lower().endswith('.pdf')):
                    raise ValueError('Unexpected instrument document URL: ' + url)
                docs.setdefault(url, {'titulo': a.get_text(' ', strip=True), 'url': url,
                                      'source_url': SOURCE})
            primary = [d for d in docs.values() if re.search(
                r'Expediente Estudio de Detalle' if is_study else r'Proyecto básico', d['titulo'], re.I)]
            if len(primary) != 1 or len(docs) < 2:
                raise ValueError('Instrument lacks unique substantive project and supporting documents')
            record_title = title if is_study else re.sub(
                r'^\d+\.\s*|\s*\(PDF[^)]*\)\s*$', '', primary[0]['titulo'])
            key = hashlib.sha256(record_title.casefold().encode()).hexdigest()[:20]
            row = {
                'id': 'berriz-proy-' + key, 'municipio': 'Berriz', 'codigo_ine': '48019',
                'provincia': 'Bizkaia', 'titulo': record_title,
                'tipo': 'estudio_de_detalle' if is_study else 'proyecto_rehabilitacion',
                'fase': 'información pública', 'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': SOURCE, 'url_documento': primary[0]['url'],
                'source': 'ayuntamiento', 'origen': 'expedientes_exposicion_publica',
                'source_heading': title, 'documentos': list(docs.values()),
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            }
            if key in rows and rows[key] != row:
                raise ValueError('Conflicting duplicate instrument')
            rows[key] = row
        if not rows:
            raise ValueError('No usable instruments; review inventory rather than accept empty snapshot')
        return list(rows.values())

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        captures = self.config.get('capture_dir')
        captures = Path(captures) if captures else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
        urls = [SOURCE]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-berriz/1.0'
            response = session.get(SOURCE, timeout=40)
            response.raise_for_status()
            rows = self.parse_inventory(response.text)
            if captures:
                (captures / 'inventory.html').write_bytes(response.content)
            for row in rows:
                for doc in row['documentos']:
                    response = session.get(doc['url'], timeout=60)
                    response.raise_for_status()
                    if not response.content.startswith(b'%PDF-'):
                        raise ValueError('Source document is not a PDF: ' + doc['url'])
                    doc['sha256'] = hashlib.sha256(response.content).hexdigest()
                    if captures:
                        (captures / (doc['sha256'] + '.pdf')).write_bytes(response.content)
                    urls.append(doc['url'])
        return {**self._write(out_jsonl, rows), 'source_urls': urls,
                'coverage': 'municipal public-exhibition inventory; no historical completeness',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
