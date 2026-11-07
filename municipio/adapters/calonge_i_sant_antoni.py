"""Municipal POUM JSON:API inventory; documents remain grouped by instrument."""
from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://api.calonge.cat'
PAGE = 'https://www.calonge.cat/ajuntament/poum'
SOURCE = BASE + '/jsonapi/node/poum?include=catalogs_files,gc_files,gq_files,regulations_files'
SECTIONS = ('catalogs_files', 'gc_files', 'gq_files', 'regulations_files')
LIMITATIONS = [
    'Partial coverage: municipal POUM section only; not all amendments, works or licences.',
    'Publication and agreement dates are not structured in this inventory and remain null.',
    'PDF map sheets are linked, not converted to verified vector geometry; no coordinates inferred.',
    'Related RPUC links are retained as references, not extracted as separate instruments.',
]


def _href(link):
    return link.get('href') if isinstance(link, dict) else link


def _api_url(url):
    parsed = urlparse(urljoin(BASE, url))
    if parsed.hostname != 'api.calonge.cat' or parsed.scheme not in {'http', 'https'} or not parsed.path.startswith('/jsonapi/node/poum'):
        raise ValueError('Unexpected POUM pagination URL')
    return parsed._replace(scheme='https').geturl()


class CalongeISantAntoniAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.calonge.cat')

    @staticmethod
    def parse_inventory(pages):
        """Resolve every attachment; incomplete includes are errors, not lost links."""
        nodes, files = {}, {}
        for page in pages:
            if page.get('errors') or not isinstance(page.get('data'), list):
                raise ValueError('Invalid POUM JSON:API inventory')
            for node in page['data']:
                key = (node['type'], node['id'])
                if key in nodes and nodes[key] != node:
                    raise ValueError('Conflicting POUM node across pages')
                nodes[key] = node
            for item in page.get('included', []):
                key = (item['type'], item['id'])
                if key in files and files[key] != item:
                    raise ValueError('Conflicting attachment across pages')
                files[key] = item
        rows = []
        for (kind, identifier), node in nodes.items():
            attrs = node['attributes']
            title = attrs.get('title', '')
            if kind != 'poum' or not re.search(r"pla d['’]ordenació urbanística municipal", title, re.I):
                raise ValueError('Unexpected instrument in dedicated POUM inventory')
            docs = {}
            for section in SECTIONS:
                relationship = node.get('relationships', {}).get(section, {})
                if _href(relationship.get('links', {}).get('next')):
                    raise ValueError('Paginated attachment relationship requires review')
                refs = relationship.get('data')
                if not isinstance(refs, list):
                    raise ValueError('Missing POUM attachment relationship')
                for ref in refs:
                    attachment = files.get((ref['type'], ref['id']))
                    if not attachment:
                        raise ValueError('Unresolved POUM attachment')
                    fa = attachment['attributes']
                    url = urljoin(BASE, fa.get('uri', {}).get('url', ''))
                    if urlparse(url).hostname != 'api.calonge.cat' or not urlparse(url).path.startswith('/sites/default/files/'):
                        raise ValueError('Invalid municipal document URL')
                    doc = docs.setdefault(url, {
                        'id_origen': ref['id'], 'url': url,
                        'titulo': ref.get('meta', {}).get('description') or fa['filename'],
                        'filename': fa['filename'], 'mime_type': fa.get('filemime'),
                        'source_url': SOURCE, 'secciones': [],
                    })
                    if section not in doc['secciones']:
                        doc['secciones'].append(section)
            if not docs or not any('regulations_files' in d['secciones'] for d in docs.values()):
                raise ValueError('POUM lacks regulatory documents')
            links = [{'titulo': x['title'], 'url': unescape(x['uri'])} for x in attrs.get('other_links', [])]
            # Only the actual plan's linked public dossier supplies expediente.
            codes = set()
            for link in links:
                if link['titulo'] == "Pla d'Ordenació Urbanística":
                    codes.update(parse_qs(urlparse(link['url']).query).get('codiPublic', []))
            if len(codes) > 1:
                raise ValueError('Ambiguous plan dossier')
            rows.append({
                'id': 'calonge-i-sant-antoni-proy-' + identifier,
                'id_origen': identifier, 'municipio': 'Calonge i Sant Antoni',
                'codigo_ine': '17034', 'provincia': 'Girona',
                'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'expediente': next(iter(codes), None), 'fase': None,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'url': PAGE, 'source_url': SOURCE,
                'source': 'ayuntamiento', 'origen': 'inventario_municipal_poum',
                'descripcion': BeautifulSoup((attrs.get('description') or {}).get('value', ''), 'html.parser').get_text(' ', strip=True),
                'documentos': list(docs.values()), 'enlaces_relacionados': links,
                'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False, 'coverage': 'partial',
                'limitations': LIMITATIONS,
            })
        if not rows:
            raise ValueError('Empty POUM inventory')
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pages, seen, urls = [], set(), []
        url = SOURCE
        while url:
            url = _api_url(url)
            if url in seen or len(seen) >= 100:
                raise ValueError('POUM pagination cycle or safety limit; no partial output written')
            seen.add(url)
            with requests.get(url, timeout=40, stream=True, headers={
                'User-Agent': 'municipio-calonge-i-sant-antoni/1.0',
                'Accept': 'application/vnd.api+json',
            }) as response:
                response.raise_for_status()
                _api_url(response.url)
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > 5_000_000:
                        raise ValueError('POUM response exceeds safety bound')
            page = json.loads(content)
            pages.append(page)
            urls.append(url)
            capture_dir = self.config.get('capture_dir')
            if capture_dir:
                capture = Path(capture_dir)
                capture.mkdir(parents=True, exist_ok=True)
                (capture / f'poum-page-{len(pages)}.json').write_bytes(content)
            next_url = _href(page.get('links', {}).get('next'))
            url = urljoin(url, next_url) if next_url else None
        rows = self.parse_inventory(pages)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': urls,
                'documents': sum(len(r['documentos']) for r in rows),
                'publication_ready': False, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot refresh, including all pages; no date-based cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
