"""One planning instrument, with all documents in the official PBOM inventory."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE_URL = 'https://www.casariche.es/?page_id=63413'
HOSTS = {'casariche.es', 'www.casariche.es'}


def parse_inventory(html: str, source_url: str = SOURCE_URL) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article#post-63413')
    title = article.select_one('h1.entry-title') if article else None
    if not title or 'Plan Básico de Ordenación Municipal' not in title.get_text(' ', strip=True):
        raise ValueError('Official PBOM instrument heading missing')
    # This source is a single instrument page, not a news search or archive.
    # A future split must be reviewed before producing incomplete output.
    for link in soup.select('a[href]'):
        rel = link.get('rel', [])
        label = link.get_text(' ', strip=True).casefold()
        if ('next' in rel or label in {'siguiente', 'siguiente página', 'next'}
                or link.find_parent(class_='page-links')):
            raise ValueError('Paginated inventory requires crawler review')
    if article.select_one('.page-links, .pagination, .nav-links'):
        raise ValueError('Paginated inventory requires crawler review')

    content = article.select_one('.entry-content')
    if content is None:
        raise ValueError('PBOM document inventory missing')
    in_documents = False
    phase = None
    heading = None
    documents = {}
    for node in content.find_all(['h1', 'h2', 'h3', 'h4', 'a']):
        text = node.get_text(' ', strip=True)
        if node.name != 'a':
            if text.upper() == 'DOCUMENTACIÓN':
                in_documents = True
            elif in_documents and re.fullmatch(r'Fase\s+(?:0|[IVX]+)', text, re.I):
                phase = text
                heading = None
            elif in_documents and not node.find('a') and text:
                heading = text
            continue
        if not in_documents or not node.get('href'):
            continue
        original = urljoin(source_url, node['href'])
        parsed = urlsplit(original)
        if parsed.hostname not in HOSTS or not parsed.path.startswith('/wp-content/uploads/'):
            # Participation forms and sharing links are not instruments/documents.
            continue
        if parsed.scheme not in {'http', 'https'} or not parsed.path.lower().endswith(('.pdf', '.zip')):
            raise ValueError('Unreviewed document format in PBOM inventory')
        if not phase or not heading:
            raise ValueError('PBOM document lacks phase or descriptive heading')
        # The page still publishes HTTP links; retain them and offer HTTPS transport.
        target = urlunsplit(('https', parsed.netloc, parsed.path, parsed.query, ''))
        doc = documents.setdefault(target, {
            'url': target, 'url_fuente': original, 'source_url': source_url,
            'referencias': [],
        })
        reference = {'fase_documental': phase, 'titulo': heading, 'enlace_texto': text}
        if reference not in doc['referencias']:
            doc['referencias'].append(reference)
    if not documents:
        raise ValueError('No PBOM source documents found')
    return [{
        'id': 'casariche-pbom-63413',
        'municipio': 'Casariche', 'codigo_ine': '41026', 'provincia': 'Sevilla',
        'titulo': title.get_text(' ', strip=True),
        'tipo': 'planeamiento_urbanistico',
        'url': source_url, 'inventory_url': source_url,
        'source': 'ayuntamiento', 'origen': 'inventario_documental_pbom',
        'documentos': list(documents.values()),
        'coverage': 'inventario_documental_pbom_parcial_municipio',
        'publication_ready': False, 'geometry_status': 'unavailable',
    }]


class CasaricheAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(output)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE_URL, timeout=45, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)',
        })
        response.raise_for_status()
        if urlsplit(response.url).hostname not in HOSTS:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, SOURCE_URL)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'pbom.html').write_text(response.text, encoding='utf-8')
        result = self._write(out_jsonl, rows)
        result.update(coverage=rows[0]['coverage'], publication_ready=False,
                      source_urls=[SOURCE_URL])
        return result

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Refresh the entire small inventory to retain added/replaced attachments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        result = self._write(out_jsonl, [])
        result.update(disabled=True, reason='No verified register of granted licences')
        return result

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
