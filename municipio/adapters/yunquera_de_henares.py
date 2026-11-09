"""Anonymous municipal transparency inventory; document groups, not granted licences."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'yunqueradehenares.sedelectronica.es'
SOURCE = f'https://{HOST}/transparency/175e1f74-8652-404b-9f6d-cb7ce3fa3ea6/'


def official_url(url):
    if urlparse(url).scheme != 'https' or urlparse(url).netloc != HOST:
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def parse_inventory(html, url):
    """Read every visible row; advertised recursive counts are checked by crawler."""
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('#content table.TransparencyListPanel')
    if table is None:
        raise ValueError('Missing public transparency inventory')
    # This inventory currently has no pager. Refuse changed pagination rather
    # than silently returning its first page. Counts also detect hidden pages.
    if soup.select('.navigator, .pagination, .paging, [rel="next"]'):
        raise ValueError('Pagination appeared: traversal must be reviewed')
    entries = []
    for cell in table.select('tbody td.class_name'):
        links = cell.select('a.gIconLink')
        if len(links) != 1:
            raise ValueError('Unrecognized inventory row')
        a = links[0]
        text = a.get_text(' ', strip=True)
        extra = a.select_one('.linkExtraInfo')
        title = ' '.join(text[:text.rfind(extra.get_text(' ', strip=True))].split()) if extra else text
        if 'exp' in a.get('class', []):
            count = re.fullmatch(r'\s*\(\s*(\d+)\s*\)\s*', extra.get_text() if extra else '')
            callback = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
            if not count or not callback:
                raise ValueError('Missing folder count or public navigation callback')
            entries.append({'kind': 'folder', 'titulo': title, 'count': int(count[1]),
                            'url': official_url(urljoin(url, callback[1]))})
        else:
            target = official_url(urljoin(url, a.get('href', '')))
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(target).path):
                raise ValueError('Unrecognized document link')
            entries.append({'kind': 'document', 'titulo': title, 'url': target,
                            'inventory_url': url})
    if not entries and 'emptyTable' not in table.get('class', []):
        raise ValueError('Inventory unexpectedly contains no rows')
    if len({e['url'] for e in entries}) != len(entries):
        raise ValueError('Duplicate inventory entries')
    return entries


def group_projects(nodes):
    """Group technical documents by folder, and loose documents by expediente."""
    rows = []
    for node in nodes:
        title, docs, url = node['titulo'], node['documents'], node['url']
        if not docs:
            continue
        if node['section'] == '7.1.':
            if not all(re.match(r'(MODIF[- ]PUNTUAL|Modificaci[oó]n|Plan\b|Estudio de detalle)', d['titulo'], re.I) for d in docs):
                raise ValueError('Unknown planning instrument; review grouping')
            # Each document here is a separate named instrument. Multi-document
            # packages must be explicitly grouped rather than guessed by filename.
            if len(docs) != 1:
                raise ValueError('Planning grouping changed; review instrument identity')
            title = docs[0]['titulo']
            kind = 'instrumento de planeamiento'
            identity = docs[0]['url']
        else:
            technical = ' '.join(d['titulo'] for d in docs)
            if not (re.search(r'proyecto|memoria|instalaci[oó]n solar', technical, re.I)
                    and re.search(r'expediente|explotaci[oó]n minera', title, re.I)):
                raise ValueError(f'Folder does not establish a physical project: {title}')
            kind = 'proyecto en información pública'
            identity = url
        dossier = re.search(r'(?:expediente\s*(?:n[ºo°.]*)?\s*)(\d+/\d{4})', title, re.I)
        rows.append({
            'id': 'yunquera-de-henares-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
            'municipio': 'Yunquera de Henares', 'provincia': 'Guadalajara', 'codigo_ine': '19331',
            'titulo': title, 'tipo': kind, 'fase': 'documentación de información pública',
            'expediente': dossier[1] if dossier else None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': url, 'url_documento': docs[0]['url'], 'inventory_url': SOURCE,
            'documentos': docs, 'source': 'ayuntamiento', 'origen': 'inventario_transparencia_urbanismo',
            'descripcion': title,
            'coverage': 'Inventario publicado; no acredita aprobación ni licencia concedida ni fase actual del expediente.',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'unavailable',
        })
    if not rows:
        raise ValueError('No genuine project or planning records found')
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Conflicting instrument identities')
    return rows


class YunqueraDeHenaresAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('evidence_dir')
        source_urls = []
        session = requests.Session()
        session.headers['User-Agent'] = 'municipio-yunquera-de-henares/1.0'

        def fetch(url):
            official_url(url)
            with session.get(url, timeout=40, stream=True) as response:
                response.raise_for_status()
                final = official_url(response.url)
                if not urlparse(final).path.startswith('/transparency/'):
                    raise ValueError('Unexpected inventory redirect')
                if 'text/html' not in response.headers.get('Content-Type', ''):
                    raise ValueError('Expected HTML inventory')
                body = bytearray()
                for chunk in response.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > 4_000_000:
                        raise ValueError('Inventory exceeds response limit')
                if final in source_urls:
                    raise ValueError('Folder cycle or repeated page')
                source_urls.append(final)
                if captures:
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / (urlparse(final).path.strip('/').replace('/', '-') + '.html')).write_bytes(body)
                return final, parse_inventory(body.decode('utf-8'), final)

        def walk(entry, section):
            url, entries = fetch(entry['url'])
            documents, nodes = [], []
            total = 0
            for child in entries:
                if child['kind'] == 'folder':
                    count, nested = walk(child, section)
                    total += count
                    nodes.extend(nested)
                else:
                    documents.append({k: v for k, v in child.items() if k != 'kind'})
                    total += 1
            if total != entry['count']:
                raise ValueError(f'Incomplete inventory: {entry["titulo"]}: expected {entry["count"]}, got {total}')
            if documents:
                if section == '7.6.' and entries != [e for e in entries if e['kind'] == 'document']:
                    # Loose documents are grouped by actual expediente number;
                    # an index is supporting material, not another project.
                    groups = {}
                    for doc in documents:
                        match = re.search(r'expediente\s*(?:n[ºo°.]*)?\s*(\d+/\d{4})', doc['titulo'], re.I)
                        if not match:
                            raise ValueError('Loose document has no instrument identity')
                        groups.setdefault(match[1], []).append(doc)
                    for number, group in groups.items():
                        detail = [d for d in group if not d['titulo'].upper().startswith('INDICE')]
                        if len(detail) != 1:
                            raise ValueError('Ambiguous loose expediente documents')
                        ordered = detail + [d for d in group if d not in detail]
                        nodes.append({'titulo': detail[0]['titulo'], 'documents': ordered,
                                      'url': detail[0]['url'], 'section': section})
                else:
                    nodes.append({'titulo': entry['titulo'], 'documents': documents,
                                  'url': url, 'section': section})
            return total, nodes

        try:
            _, sections = fetch(SOURCE)
            selected = [e for e in sections if e['titulo'].startswith(('7.1.', '7.6.'))]
            if len(selected) != 2:
                raise ValueError('Expected planning and public-information sections')
            nodes = []
            count = 0
            for section in selected:
                n, found = walk(section, section['titulo'][:4])
                count += n
                nodes.extend(found)
            rows = group_projects(nodes)
        finally:
            session.close()
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'documents': count,
                'source_urls': source_urls, 'coverage': 'sections 7.1 and 7.6; complete advertised document counts',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Refresh the entire bounded inventory. No date-based incremental cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
