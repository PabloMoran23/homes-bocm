"""Urnieta's municipal development-plan document inventory (partial coverage)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, quote, unquote

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


SOURCE = 'https://www.urnieta.eus/es/hiri-antolamendurako-garapen-planak'


def _normal(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def _document_url(href):
    url = urlsplit(urljoin(SOURCE, href))
    if (url.scheme != 'https' or url.netloc != 'www.urnieta.eus'
            or not re.fullmatch(r'/documents/\d+/\d+/[^/]+/[0-9a-f-]{36}', unquote(url.path))):
        raise ValueError('Unexpected municipal document URL')
    return 'https://www.urnieta.eus' + quote(unquote(url.path), safe='/')


class UrnietaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def check_document(url):
        # Read only a signature: municipal archives can exceed 160 MB.
        with requests.get(url, timeout=40, stream=True) as response:
            if response.status_code in (403, 404, 410):
                return {'http_status': response.status_code, 'availability': 'unavailable'}
            response.raise_for_status()
            signature = next(response.iter_content(8), b'')
            if not signature.startswith((b'%PDF-', b'PK\x03\x04')):
                raise ValueError('Document link did not return a PDF or ZIP: ' + url)
            return {'http_status': response.status_code, 'availability': 'available',
                    'content_type': response.headers.get('Content-Type')}

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('#main-content')
        if main is None:
            raise ValueError('Missing municipal content region')
        # Fail explicitly if the inventory grows pagination. Never accept page one
        # as a complete snapshot; there are no pagination controls on the live source.
        for a in main.select('a[href]'):
            label = _normal(a.get_text(' ', strip=True) + ' ' + a.get('aria-label', ''))
            paginated = (a.find_parent(class_=re.compile(r'pagination|pager')) is not None
                         or 'next' in a.get('rel', [])
                         or re.search(r'\b(siguiente|next|hurrengoa|última|last)\b', label))
            if paginated and a['href'] not in ('', '#'):
                disabled = a.find_parent(class_=re.compile(r'disabled'))
                if not disabled and a.get('aria-disabled') != 'true':
                    raise ValueError('Inventory pagination requires traversal before extraction')
        rows = {}
        blocks = main.select('.documentos .documento')
        if not blocks:
            raise ValueError('No development-plan documents; review source layout')
        for block in blocks:
            title_link = block.select_one('.titulo a[href]')
            date_node = block.select_one('.fecha')
            if title_link is None or date_node is None:
                raise ValueError('Incomplete inventory entry')
            title = title_link.get_text(' ', strip=True)
            normalized = _normal(title)
            # This is a dedicated urban-planning inventory, but still fail on
            # unrelated new entries instead of promoting forms/news to projects.
            if not re.search(r'plan parcial|reparcelaci[oó]n|urbanizaci[oó]n|estudio de detalle|\bpau\b', normalized):
                raise ValueError('Unreviewed instrument type: ' + title)
            date_raw = date_node.get_text(' ', strip=True)
            catalog_date = datetime.strptime(date_raw, '%d·%m·%Y').date().isoformat()
            key = hashlib.sha256(normalized.encode()).hexdigest()[:20]
            if key not in rows:
                phase = ('segunda aprobación inicial' if 'segunda aprobación inicial' in normalized
                         else 'aprobación inicial' if 'aprobación inicial' in normalized else None)
                kind = ('reparcelacion' if 'reparcelaci' in normalized else
                        'urbanizacion' if 'urbanizaci' in normalized else 'planeamiento_urbanistico')
                rows[key] = {
                    'id': 'urnieta-proy-' + key, 'municipio': 'Urnieta',
                    'codigo_ine': '20072', 'provincia': 'Gipuzkoa',
                    'titulo': title, 'tipo': kind, 'fase': phase,
                    'fecha': None, 'fecha_publicacion': None,
                    'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': SOURCE, 'source': 'ayuntamiento',
                    'origen': 'inventario_municipal_planes_desarrollo',
                    'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                }
            # A file/icon link is not a separate project. Group all documents
            # bearing the same instrument title, preserving each catalogue date.
            docs = rows[key]['documentos']
            for a in block.select('a[href*="/documents/"]'):
                url = _document_url(a['href'])
                if not any(d['url'] == url for d in docs):
                    docs.append({'titulo': title, 'url': url,
                                 'fecha_catalogo': catalog_date,
                                 'fecha_fuente': date_raw, 'source_url': SOURCE})
            if not docs:
                raise ValueError('Instrument without municipal documents')
        return list(rows.values())

    @staticmethod
    def _write(path, rows, status='ok'):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'status': status, 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'municipio-urnieta/1.0 (public municipal planning inventory)'})
        response.raise_for_status()
        if urlsplit(response.url).netloc != 'www.urnieta.eus' or 'html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Unexpected inventory response')
        rows = self.parse_inventory(response.content)
        for row in rows:
            for document in row['documentos']:
                document.update(self.check_document(document['url']))
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'inventory-live.html').write_bytes(response.content)
        result = self._write(out_jsonl, rows)
        result['source_urls'] = [SOURCE]
        return result

    def update_proyectos(self, out_jsonl, state_path):
        """Refresh the full current inventory; no historical completeness claim."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return self._write(out_jsonl, [], status='disabled')

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
