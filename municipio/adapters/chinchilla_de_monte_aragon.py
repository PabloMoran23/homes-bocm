"""Municipal POM document inventory; one instrument, all its published sections."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote_plus, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.webchinchilla.com/urbanismo/'
PLAN = 'PLAN DE ORDENACIÓN MUNICIPAL'


def _content(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content_area')
    if content is None:
        raise ValueError('Missing municipal content area')
    for a in content.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if ('next' in a.get('rel', []) or label in {'siguiente', 'next', '›', '»'}
                or re.search(r'[?&](?:page|pagina|offset)=', a['href'], re.I)):
            raise ValueError('Pagination detected: extend inventory traversal before extraction')
    return content


def parse_inventory(html):
    """Discover POM section buttons only, stopping at the next instrument heading."""
    content = _content(html)
    headings = content.select('h1')
    if not headings or headings[0].get_text(' ', strip=True) != PLAN:
        raise ValueError('Missing POM inventory heading')
    sections = {}
    for node in headings[0].find_all_next(['h1', 'a']):
        if node.name == 'h1':
            break
        if 'diyfeLinkAsButton' not in node.get('class', []):
            continue
        url = urljoin(SOURCE, node.get('href', ''))
        parts = urlsplit(url)
        if (parts.netloc != urlsplit(SOURCE).netloc or not parts.path.startswith('/urbanismo/')
                or parts.path == '/urbanismo/' or parts.query or parts.fragment):
            raise ValueError('Unexpected POM section URL')
        sections[url] = node.get_text(' ', strip=True)
    if not sections:
        raise ValueError('Empty POM section inventory')
    return sections


def parse_documents(html, section_url, section_title):
    content = _content(html)
    heading = content.select_one('h1')
    if not heading or heading.get_text(' ', strip=True).casefold() != section_title.casefold():
        raise ValueError('POM section heading mismatch')
    documents = {}
    for a in content.select('a[href]'):
        url = urljoin(section_url, a['href'])
        parts = urlsplit(url)
        match = re.fullmatch(r'/app/download/(\d+)/(.+\.pdf)', parts.path, re.I)
        if '/app/download/' not in parts.path:
            continue
        if not match or parts.netloc != urlsplit(SOURCE).netloc or parts.query or parts.fragment:
            raise ValueError('Unexpected POM document URL')
        key = match[1]
        documents.setdefault(key, {
            'id_origen': key, 'titulo': unquote_plus(match[2]), 'url': url,
            'procedencia': [{'url': section_url, 'seccion': section_title}],
        })
    if not documents:
        raise ValueError('POM section has no PDF documents')
    return list(documents.values())


class ChinchillaDeMonteAragonAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.webchinchilla.com')

    def _fetch(self, url):
        with requests.get(url, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-chinchilla/1.0')
        }) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 5_000_000:
                    raise ValueError('Source exceeds reviewed response size')
                chunks.append(chunk)
            body = b''.join(chunks)
            if self.config.get('evidence_dir'):
                folder = Path(self.config['evidence_dir'])
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(body)
            return body.decode('utf-8-sig')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        sections = parse_inventory(self._fetch(SOURCE))
        documents = {}
        for url, title in sections.items():
            for doc in parse_documents(self._fetch(url), url, title):
                key = doc['id_origen']
                if key in documents:
                    for provenance in doc['procedencia']:
                        if provenance not in documents[key]['procedencia']:
                            documents[key]['procedencia'].append(provenance)
                else:
                    documents[key] = doc
        row = {
            'id': '02029-pom', 'municipio': 'Chinchilla de Monte-Aragón',
            'codigo_ine': '02029', 'provincia': 'Albacete',
            'titulo': 'Plan de Ordenación Municipal de Chinchilla de Monte-Aragón',
            'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
            'origen': 'inventario_documental_pom', 'url': SOURCE,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fecha_aprob': None, 'fase': None,
            'descripcion': 'Instrumento publicado en la sección municipal de Urbanismo. '
                           'La página no acredita fechas de aprobación ni vigencia consolidada.',
            'documentos': list(documents.values()),
            'source_urls': [SOURCE, *sections],
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'cobertura': 'Parcial: documentación del POM; no incluye modificaciones, '
                         'otros instrumentos, tablón de anuncios ni licencias.',
        }
        self._write(out_jsonl, [row])
        return {'status': 'ok', 'rows': 1, 'documents': len(documents),
                'source_urls': row['source_urls'], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot of this POM inventory; state is intentionally untouched.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
