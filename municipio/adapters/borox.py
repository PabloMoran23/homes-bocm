"""Borox's current municipal NNSS document inventory (partial historical coverage)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.ayuntamientodeborox.com/index.php/ayun/urbanismo'
HOST = 'www.ayuntamientodeborox.com'


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    body = soup.select_one('[itemprop="articleBody"]')
    if body is None:
        raise ValueError('Municipal article body missing')
    # A newly paginated source must be reviewed rather than silently truncated.
    if soup.select('a[rel~="next"], .pagination a[href], .pagenav a[href]'):
        raise ValueError('Pagination detected; inventory coverage needs review')
    heading = next((h for h in body.select('strong, h2, h3')
                    if h.get_text(' ', strip=True).upper() == 'NORMAS SUBSIDIARIAS'), None)
    if heading is None:
        raise ValueError('NNSS inventory heading missing')
    section = heading.find_parent('table')
    if section is None:
        raise ValueError('NNSS inventory section missing')
    documents = {}
    for a in section.select('a[href]'):
        title = ' '.join(a.get_text(' ', strip=True).split())
        # Image thumbnails duplicate the labelled anchors; do not emit them twice.
        if not title:
            continue
        norm = title.casefold()
        if not (norm.startswith('ordenación ') or
                (norm.startswith('normas para ') and 'normas subsidiarias' in norm)):
            continue
        target = urljoin(source_url, a['href'])
        parsed = urlparse(target)
        if (parsed.scheme != 'https' or parsed.hostname != HOST or parsed.query
                or not parsed.path.startswith('/images/')
                or Path(parsed.path).suffix.lower() not in {'.pdf', '.jpg', '.jpeg', '.png'}):
            raise ValueError(f'Unexpected NNSS document URL: {target}')
        documents[target] = {'titulo': title, 'url': target, 'source_url': source_url}
    docs = list(documents.values())
    if not any('normas para ' in d['titulo'].casefold() for d in docs):
        raise ValueError('No NNSS normative documents found')
    if not any(d['titulo'].casefold().startswith('ordenación ') for d in docs):
        raise ValueError('No NNSS ordering plans found')
    return [{
        'id': 'borox-nnss', 'municipio': 'Borox', 'codigo_ine': '45021',
        'provincia': 'Toledo', 'titulo': heading.get_text(' ', strip=True) + ' de Borox',
        'tipo': 'normas_subsidiarias', 'url': source_url, 'inventory_url': source_url,
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
        'documentos': docs,
        'descripcion': 'Documentos de las Normas Subsidiarias agrupados por instrumento. '
                       'El inventario incluye planos rotulados 1984/1985 y normas de 1985; '
                       'no acredita fecha de acuerdo, aprobación ni vigencia actual.',
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'partial_current_document_inventory',
    }]


class BoroxAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(url, timeout=40)
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Unexpected redirect outside municipal source')
        return response

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        captures = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-borox-inventory/1.0'
            response = self._fetch(session, SOURCE)
            if captures:
                (captures / 'urbanismo.html').write_bytes(response.content)
            rows = parse_inventory(response.text, response.url)
            for row in rows:
                for doc in row['documentos']:
                    r = self._fetch(session, doc['url'])
                    suffix = Path(urlparse(doc['url']).path).suffix.lower()
                    valid = (r.content.startswith(b'%PDF-') if suffix == '.pdf' else
                             r.content.startswith(b'\xff\xd8\xff') if suffix in {'.jpg', '.jpeg'} else
                             r.content.startswith(b'\x89PNG\r\n\x1a\n'))
                    if not valid:
                        raise ValueError(f'Document signature invalid: {doc["url"]}')
                    doc.update(content_type=r.headers.get('Content-Type'),
                               sha256=hashlib.sha256(r.content).hexdigest(),
                               retrieved_url=r.url)
                    if captures:
                        (captures / Path(urlparse(doc['url']).path).name).write_bytes(r.content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'count': len(rows), 'written': len(rows),
                'source_urls': [SOURCE], 'coverage': 'partial_current_document_inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        # Full snapshot refresh; there is no incremental register on this page.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'Only application forms; no verified grant register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
