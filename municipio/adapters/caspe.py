"""Municipal PGOU document tree; one instrument, never one project per map."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urldefrag, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.caspe.es/urbanismo-y-obras/'
ROOT = 'https://www.caspe.es/pgou/'
LIMITATIONS = [
    'Solo archivo PGOU enlazado por Urbanismo; no inventario completo de proyectos o modificaciones posteriores.',
    'Sin fechas verificadas de publicación o acuerdo; las marcas del servidor no son aprobaciones.',
    'Sin geometría ni verificación de vigencia jurídica; enlaces documentales, no licencias concedidas.',
]


def _pagination(soup):
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if ('next' in a.get('rel', []) or label in {'siguiente', 'next', 'más', '›', '»'}
                or 'page=' in a['href'] or '/page/' in a['href']):
            raise ValueError('Paginación inesperada: revisar cobertura antes de extraer')


def parse_portal(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.entry-content')
    if content is None:
        raise ValueError('Falta contenido de Urbanismo')
    _pagination(content)
    for section in content.select('.wpb_accordion_section'):
        heading = section.select_one('h3')
        if heading and heading.get_text(' ', strip=True).upper() == 'PGOU':
            for a in section.select('a[href]'):
                if urljoin(SOURCE, a['href']) == ROOT:
                    return ROOT
    raise ValueError('Falta enlace municipal explícito al archivo PGOU')


def parse_directory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    _pagination(soup)
    heading = soup.select_one('h1')
    if not heading or heading.get_text(strip=True) != 'Index of ' + unquote(urlsplit(url).path).rstrip('/'):
        raise ValueError('El archivo PGOU ya no es un índice reconocible: ' + url)
    if not soup.select_one('pre'):
        raise ValueError('Falta listado de documentos: ' + url)
    children, documents = set(), {}
    for a in soup.select('pre a[href]'):
        href = a['href']
        if href.startswith('?C='):  # Apache sorting links: same complete listing.
            continue
        target = urldefrag(urljoin(url, href))[0]
        parts = urlsplit(target)
        decoded = unquote(parts.path)
        if parts.hostname != 'www.caspe.es' or not decoded.startswith('/pgou/'):
            continue  # Parent Directory and unrelated links.
        if any(bit in {'.', '..'} for bit in decoded.split('/')):
            raise ValueError('Ruta ambigua en archivo PGOU')
        canonical = urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
        if canonical == url:
            continue
        if parts.query:
            raise ValueError('Enlace paginado o dinámico inesperado: ' + target)
        if parts.path.endswith('/'):
            children.add(canonical)
        elif decoded.lower().endswith('.pdf'):
            documents[canonical] = {
                'titulo': decoded.rsplit('/', 1)[-1][:-4],
                'url': canonical,
                'inventory_url': url,
            }
        else:
            raise ValueError('Formato nuevo en archivo PGOU: ' + target)
    return sorted(children), list(documents.values())


class CaspeAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={
            'User-Agent': 'MunicipalDocumentInventory/1.0 (Caspe research)'
        })
        response.raise_for_status()
        if response.url != url:
            raise ValueError('Redirección inesperada: ' + response.url)
        return response.content.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        root = parse_portal(self._fetch(SOURCE))
        pending, visited, documents = [root], set(), {}
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Archivo supera límite de seguridad; no se escribe salida parcial')
            visited.add(url)
            children, docs = parse_directory(self._fetch(url), url)
            pending.extend(child for child in children if child not in visited)
            for doc in docs:
                documents.setdefault(unquote(doc['url']), doc)
        if not documents or not any(d['titulo'].upper() == 'NORMAS URBANISTICAS' for d in documents.values()):
            raise ValueError('Archivo incompleto o sin normas urbanísticas del PGOU')
        row = {
            'id': 'caspe-pgou', 'municipio': 'Caspe', 'codigo_ine': '50074',
            'provincia': 'Zaragoza', 'titulo': 'Plan General de Ordenación Urbana de Caspe (PGOU)',
            'tipo': 'planeamiento_urbanistico', 'url': root, 'source': 'ayuntamiento',
            'origen': 'archivo_documental_pgou', 'inventory_url': SOURCE,
            'source_urls': [SOURCE] + sorted(visited),
            'documentos': sorted(documents.values(), key=lambda d: d['url']),
            'coverage': 'archivo_documental_pgou_parcial', 'limitations': LIMITATIONS,
            'publication_ready': False, 'geometry_status': 'unavailable',
        }
        self._write(out_jsonl, [row])
        return {'count': 1, 'written': 1, 'documents': len(documents),
                'source_urls': row['source_urls'], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
