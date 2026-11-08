"""Municipal NNSS document inventory; a complete snapshot of indicator 50 galleries."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://transparencia.elcuervodesevilla.es/es/transparencia/'
          'indicadores-de-transparencia/indicador/'
          '50.-Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00004/')
DOCUMENT_ROOT = '/export/sites/elcuervo/es/transparencia/.galleries/IND-50-/normas-subsidiarias/'
IMAGE_ROOT = DOCUMENT_ROOT.replace('/IND-50-/', '/IMG-50-/')


def inventory_url(url: str) -> str:
    """Normalize only verified inventory pagination; reject unexpected destinations."""
    parsed, source = urlsplit(url), urlsplit(SOURCE)
    if (parsed.scheme != 'https' or parsed.netloc != source.netloc
            or parsed.path.rstrip('/') != source.path.rstrip('/')):
        raise ValueError('Unexpected inventory destination: ' + url)
    params = parse_qsl(parsed.query, keep_blank_values=True)
    if any(not re.fullmatch(r'pagegalleryfiles-\d+-\d+', k)
           or not v.isdigit() or int(v) < 1 for k, v in params):
        raise ValueError('Unrecognized inventory pagination: ' + url)
    return urlunsplit(('https', source.netloc, source.path, urlencode(sorted(params)), ''))


def parse_page(html: str, url: str) -> tuple[list[dict], list[str]]:
    soup = BeautifulSoup(html, 'html.parser')
    if not any('50.' in h.get_text() and 'PGOU' in h.get_text()
               for h in soup.select('h1,h2')):
        raise ValueError('Missing official indicator 50 heading')
    documents, pages = {}, set()
    for a in soup.select('a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlsplit(target)
        if 'pagegallery' in parsed.query:
            pages.add(inventory_url(target))
        root = next((root for root in (DOCUMENT_ROOT, IMAGE_ROOT) if parsed.path.startswith(root)), None)
        if (parsed.netloc == urlsplit(SOURCE).netloc and parsed.scheme == 'https'
                and root and parsed.path.lower().endswith(('.pdf', '.gif', '.jpg', '.png'))):
            title = a.get_text(' ', strip=True)
            if not title:
                raise ValueError('Unnamed NNSS document')
            documents[target] = {'titulo': title, 'url': target,
                                 'seccion': parsed.path[len(root):].split('/')[0],
                                 'source_pages': [inventory_url(url)]}
    if not documents:
        raise ValueError('No NNSS documents: source layout or content changed')
    return list(documents.values()), sorted(pages)


def build_record(documents: list[dict], pages: list[str]) -> dict:
    # Require the actual multi-document instrument, not a navigation link.
    sections = {d['seccion'] for d in documents}
    if not {'documentacion-escrita', 'estudio-impacto-ambiental',
            'planos-ordenacion', 'planos-informacion'}.issubset(sections):
        raise ValueError('Incomplete NNSS inventory: missing written/environmental/map sections')
    return {
        'id': 'el-cuervo-de-sevilla-nnss', 'municipio': 'El Cuervo de Sevilla',
        'codigo_ine': '41903', 'provincia': 'Sevilla',
        'titulo': 'Normas Subsidiarias de Planeamiento de El Cuervo de Sevilla',
        'tipo': 'normas subsidiarias de planeamiento', 'url': SOURCE,
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
        'descripcion': 'Documentación de las Normas Subsidiarias publicada en el indicador 50 del portal municipal de transparencia. No acredita por sí sola vigencia consolidada ni aprobación de modificaciones posteriores.',
        'documentos': sorted(documents, key=lambda d: d['url']), 'source_urls': sorted(pages),
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'coverage': 'Inventario documental NNSS del indicador 50; no incluye PBOM, otras modificaciones, obras ni licencias.',
    }


class ElCuervoDeSevillaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='el-cuervo-de-sevilla', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        pending, visited, documents = [SOURCE], set(), {}
        capture_dir = self.config.get('evidence_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-el-cuervo-de-sevilla/1.0'
            while pending:
                url = pending.pop(0)
                if url in visited:
                    continue
                if len(visited) >= 1000:
                    raise ValueError('Pagination safety limit reached; no partial output written')
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if inventory_url(response.url) != url:
                    raise ValueError('Inventory redirect lost pagination')
                rows, links = parse_page(response.text, url)
                visited.add(url)
                if capture_dir:
                    folder = Path(capture_dir)
                    folder.mkdir(parents=True, exist_ok=True)
                    name = 'inventory-' + hashlib.sha256(url.encode()).hexdigest()[:16]
                    (folder / (name + '.html')).write_text(response.text, encoding='utf-8')
                    (folder / (name + '.url')).write_text(url, encoding='utf-8')
                for row in rows:
                    previous = documents.get(row['url'])
                    if previous:
                        previous['source_pages'] = sorted(set(previous['source_pages'] + row['source_pages']))
                    else:
                        documents[row['url']] = row
                pending.extend(link for link in links if link not in visited and link not in pending)
        record = build_record(list(documents.values()), list(visited))
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(record, ensure_ascii=False) + '\n', encoding='utf-8')
        return {'count': 1, 'written': 1, 'documents': len(documents),
                'source_urls': sorted(visited), 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
