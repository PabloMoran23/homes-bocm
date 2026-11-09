"""Published municipal planning packages; no inferred approvals or licence grants."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
import zipfile

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'www.sanbartolomedelatorre.es'
ROOT = f'https://{HOST}/es/gobierno-abierto/portal-transparencia/resultados-de-transparencia/'
PGOU_URL = ROOT + 'Plan-General-de-Ordenacion-Urbana-PGOU./'
CONVENIOS_URL = ROOT + 'Convenios-y-actuaciones-urbanisticas-en-ejecucion./'
GALLERY = '/export/sites/sanbartolome/es/gobierno-abierto/portal-transparencia/.galleries/Transparencia/Transparencia-en-material-de-urbanismo/'


def _official(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname == HOST


def parse_inventory(html: str, url: str) -> list[dict]:
    """One PGOU package; one record per individually named urbanisation agreement."""
    if url not in (PGOU_URL, CONVENIOS_URL):
        raise ValueError('Unsupported inventory')
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.select_one('h1')
    expected = 'Plan General' if url == PGOU_URL else 'Convenios y actuaciones'
    if not title or expected not in title.get_text(' ', strip=True):
        raise ValueError('Inventory heading missing or changed')
    # These are unpaginated download galleries. Refuse new pagination, rather
    # than returning a silently incomplete inventory after a site redesign.
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if (a.get('rel') and 'next' in a['rel']) or label in {'siguiente', 'next', '»', '›'}:
            if a['href'] not in {'', '#'}:
                raise ValueError('Pagination detected; crawler requires review')
    if soup.select('.pagination, .paginator, .pager'):
        raise ValueError('Pagination container detected; crawler requires review')
    docs = {}
    folder = 'Planes-de-ordenacion-urbana/PGOU/' if url == PGOU_URL else 'Convenios-urbanisticos/'
    for a in soup.select('.sg-download-gallery table a[href]'):
        target = urljoin(url, a['href'])
        path = urlparse(target).path
        if not _official(target) or not path.startswith(GALLERY + folder):
            continue
        if not path.lower().endswith(('.pdf', '.docx')):
            continue
        name = a.get_text(' ', strip=True)
        if not name:
            raise ValueError('Unnamed source document')
        docs.setdefault(target, {'titulo': name, 'url': target})
    if not docs:
        raise ValueError('No planning documents in municipal gallery')
    if url == PGOU_URL:
        names = ' '.join(d['titulo'].casefold() for d in docs.values())
        if 'planeamiento vigente' not in names or 'normas urbanísticas' not in names:
            raise ValueError('PGOU package missing inventory or urban planning rules')
        groups = [(title.get_text(' ', strip=True), list(docs.values()), 'planeamiento_urbanistico', url)]
    else:
        groups = []
        for doc in docs.values():
            if doc['titulo'].casefold().startswith('convenio urbanístico para urbanizar '):
                groups.append((doc['titulo'], [doc], 'convenio_urbanistico', doc['url']))
        if not groups:
            raise ValueError('No named urbanisation agreements')
    return [{
        'id': 'san-bartolome-plan-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
        'municipio': 'San Bartolomé de la Torre', 'codigo_ine': '21063',
        'provincia': 'Huelva', 'titulo': name, 'tipo': kind,
        'url': identity, 'inventory_url': url, 'documentos': documents,
        'source': 'ayuntamiento', 'origen': 'inventario_documental_urbanismo',
        'publication_ready': False, 'geometry_status': 'unavailable',
    } for name, documents, kind, identity in groups]


class SanBartolomeDeLaTorreAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url: str) -> bytes:
        if not _official(url):
            raise ValueError('Non-municipal source URL')
        # Explicit manifest option for the incomplete TLS chain observed on this
        # public portal; never silently retry with verification disabled.
        response = requests.get(url, timeout=45, allow_redirects=False,
                                verify=self.config.get('tls_verify', True),
                                headers={'User-Agent': 'municipio-inventory/1.0'})
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError('Source redirected; review canonical URL')
        content = response.content
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            suffix = Path(urlparse(url).path).suffix or '.html'
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + suffix
            (directory / name).write_bytes(content)
        return content

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = []
        for url in (PGOU_URL, CONVENIOS_URL):
            rows.extend(parse_inventory(self._fetch(url).decode('utf-8'), url))
        # Verify the linked packages are real documents, not successful HTML
        # error/login responses. Complete all reads before replacing output.
        checked = set()
        for row in rows:
            for doc in row['documentos']:
                url = doc['url']
                if url in checked:
                    continue
                content = self._fetch(url)
                if urlparse(url).path.lower().endswith('.pdf'):
                    if not content.startswith(b'%PDF-'):
                        raise ValueError('Source attachment is not PDF')
                else:
                    with zipfile.ZipFile(io.BytesIO(content)) as archive:
                        if 'word/document.xml' not in archive.namelist():
                            raise ValueError('Source attachment is not DOCX')
                checked.add(url)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [PGOU_URL, CONVENIOS_URL],
                'coverage': 'two_current_municipal_document_galleries', 'publication_ready': False}

    @staticmethod
    def _write(path: Path, rows: list[dict]):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh of the bounded galleries; no invented incremental cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified licence-grant register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
