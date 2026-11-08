"""Current municipal PGOU inventory, enriched by the municipal archival index."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://aytobaneza.sedelectronica.es/transparency/f5fc0e43-eda2-4d84-98c9-d5608595b9d3/'
ARCHIVE = 'https://www.aytobaneza.es/ayuntamiento/normativa-municipal/urbanismo/index.html'
LIMITATIONS = [
    'Partial coverage: current PGOU only; not a complete municipal project history.',
    'Public-exposure dossiers, general notice board, procurement and licence forms are excluded.',
    'Linked Drive folder is retained as a collection; its nested files are not inventoried.',
    'Approval date is not parsed from the linked PDF; document publication dates are separate.',
    'No verified geometry or coordinates; publication_ready is false.',
]


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # The reviewed inventories are unpaginated. Fail instead of silently taking
    # a first page if either site adds conventional or Wicket pagination.
    for a in soup.select('a, button'):
        label = _norm(a.get_text(' ', strip=True) + ' ' + a.get('aria-label', '')
                      + ' ' + a.get('title', ''))
        rel = a.get('rel', [])
        if (set(rel) & {'next', 'last'} or
                re.search(r'\b(siguiente|next|ultima pagina|pagina siguiente)\b', label)):
            if a.get('href') or a.get('onclick'):
                raise ValueError('Inventory pagination detected; crawler requires review')
    if soup.select('.pagination, .navigator, .paging, .paginator, .paging-navigator'):
        raise ValueError('Pagination controls require review')
    return soup


def parse_projects(current_html: str, archive_html: str) -> list[dict]:
    current, archive = _soup(current_html), _soup(archive_html)
    table = current.select_one('table.TransparencyListPanel')
    if table is None or 'normativa urbanistica' not in _norm(current.get_text(' ', strip=True)):
        raise ValueError('Missing current municipal planning inventory')
    documents = {}
    for a in table.select('a[href]'):
        title = a.get_text(' ', strip=True)
        target = urljoin(SOURCE, a['href'])
        if (_norm(title) != 'plan general de ordenacion urbana' or
                urlparse(target).hostname != 'aytobaneza.sedelectronica.es' or
                not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(target).path)):
            raise ValueError('Unreviewed document in current PGOU inventory')
        documents[target] = {'titulo': title, 'url': target, 'source_url': SOURCE,
                             'tipo': 'documento_sede', 'fecha_publicacion': None}
    if not documents:
        raise ValueError('No genuine PGOU document in current inventory')
    preview_urls = list(documents)
    content = archive.select_one('.paragraph_block')
    if content is None or 'plan general de ordenacion urbana de la baneza' not in _norm(content.get_text(' ', strip=True)):
        raise ValueError('Missing municipal PGOU archival narrative')
    for a in content.select('a[href]'):
        target = urljoin(ARCHIVE, a['href'])
        title = a.get_text(' ', strip=True)
        host = urlparse(target).hostname
        doc = {'titulo': title, 'url': target, 'source_url': ARCHIVE,
               'fecha_publicacion': None}
        if host == 'bocyl.jcyl.es' and urlparse(target).path.endswith('.pdf'):
            # Upgrade the municipal HTTP link to the verified official HTTPS URL.
            target = target.replace('http://', 'https://', 1)
            doc['url'] = target
            match = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', title)
            if not match:
                raise ValueError('BOCYL document lacks explicit publication date')
            doc['fecha_publicacion'] = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
            doc['tipo'] = 'anuncio_bocyl'
        elif host == 'drive.google.com' and 'p.g.o.u.' in title.lower():
            doc['tipo'] = 'coleccion_planos_textos_memoria'
        else:
            raise ValueError('Unreviewed link in municipal PGOU archive')
        documents[target] = doc
    if not any(d['tipo'] == 'anuncio_bocyl' for d in documents.values()):
        raise ValueError('No official planning announcements')
    return [{
        'id': 'la-baneza-pgou', 'municipio': 'La Bañeza', 'provincia': 'León',
        'codigo_ine': '24010', 'titulo': 'Plan General de Ordenación Urbana de La Bañeza',
        'tipo': 'planeamiento_urbanistico',
        'fase': 'aprobación definitiva' if 'anuncio aprobacion definitiva' in _norm(content.get_text(' ', strip=True)) else None,
        'fase_source_url': ARCHIVE,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': SOURCE, 'url_documento': preview_urls[0],
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_pgou',
        'source_urls': [SOURCE, ARCHIVE],
        'documentos': list(documents.values()),
        'descripcion': content.get_text(' ', strip=True),
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'unavailable', 'limitaciones': LIMITATIONS,
    }]


class LaBanezaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def _fetch(self, url, capture_name):
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-la-baneza/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != urlparse(url).hostname:
                raise ValueError('Unexpected source redirect')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected an HTML inventory')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 3_000_000:
                    raise ValueError('Inventory response exceeds 3 MB')
            if self.config.get('capture_dir'):
                path = Path(self.config['capture_dir'])
                path.mkdir(parents=True, exist_ok=True)
                (path / capture_name).write_bytes(body)
            return bytes(body).decode(response.encoding or 'utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        current = self._fetch(SOURCE, 'live_inventory.html')
        archive = self._fetch(ARCHIVE, 'live_archive.html')
        rows = parse_projects(current, archive)
        # Check the actual public document detail, not just a navigation label.
        preview = self._fetch(rows[0]['url_documento'], 'live_pgou_detail.html')
        text = _norm(BeautifulSoup(preview, 'html.parser').get_text(' ', strip=True))
        if not all(term in text for term in ('plan general de ordenacion urbana', 'informacion del documento', 'pdf')):
            raise ValueError('PGOU document detail unavailable')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE, ARCHIVE, rows[0]['url_documento']],
                'coverage': 'current_pgou_snapshot', 'publication_ready': False, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of this unpaginated current-plan inventory.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
