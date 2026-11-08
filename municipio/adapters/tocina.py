"""Tocina's published PGOU and LOUA adaptation document inventories."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urldefrag, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

PGOU = 'https://www.tocina.es/es/ayuntamiento/pgou/'
ADAPTACION = ('https://transparencia.tocinalosrosales.es/es/transparencia/'
              'indicadores-de-transparencia/indicador/'
              'Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00002/')
DOC_ROOT = '/export/sites/tocina/es/transparencia/.galleries/IND-50-/ADAPTACION-PARCIAL-LOUA/'


def parse_inventory(html: str, url: str, kind: str):
    """Return grouped documents plus every advertised gallery page."""
    soup = BeautifulSoup(html, 'html.parser')
    container = soup.select_one('#cuerpo' if kind == 'pgou' else 'article.documentacion')
    if container is None:
        raise ValueError(f'Missing {kind} inventory container: {url}')
    groups = {}
    for a in container.select('a[href]'):
        target = urljoin(url, a['href'])
        parts = urlsplit(target)
        if not parts.path.lower().endswith('.pdf'):
            continue
        if kind == 'pgou':
            if parts.hostname != 'multimedia.dipusevilla.es' or not parts.path.startswith('/tocina/pgou/'):
                raise ValueError(f'Unreviewed PGOU document: {target}')
            key = 'pgou'
        else:
            if parts.hostname != urlsplit(ADAPTACION).hostname or not parts.path.startswith(DOC_ROOT):
                raise ValueError(f'Unreviewed adaptation document: {target}')
            key = 'correccion-adaptacion' if 'CORRECCION' in parts.path.upper() else 'adaptacion-loua'
        title = a.get('title') or a.get_text(' ', strip=True)
        if title.startswith('(Descargar') or not title:
            title = a.parent.get_text(' ', strip=True)
        groups.setdefault(key, {})[target] = {
            'titulo': title, 'url': target, 'inventory_url': url,
        }
    if not groups:
        raise ValueError(f'No planning documents in {url}')
    pages = set()
    for a in soup.select('a[href]'):
        target = urldefrag(urljoin(url, a['href']))[0]
        parts = urlsplit(target)
        query = parse_qs(parts.query)
        is_page = any(k.startswith('pagegalleryfiles-') for k in query)
        label = a.get_text(' ', strip=True).lower()
        if is_page:
            base = urlsplit(url)
            if (parts.netloc, parts.path.rstrip('/')) != (base.netloc, base.path.rstrip('/')):
                raise ValueError(f'Unexpected gallery page: {target}')
            pages.add(target)
        elif label in {'siguiente', 'next', '›', '»'} or 'next' in a.get('rel', []):
            if a.get('href') not in {'', '#'}:
                raise ValueError(f'Unrecognized pagination: {target}')
    return groups, sorted(pages)


def make_records(groups):
    titles = {
        'pgou': 'PGOU de Tocina — inventario documental municipal',
        'adaptacion-loua': 'Adaptación parcial del PGOU de Tocina a la LOUA',
        'correccion-adaptacion': 'Corrección de error material de la adaptación del PGOU de Tocina',
    }
    return [{
        'id': f'tocina-planeamiento-{key}', 'titulo': titles[key],
        'municipio': 'Tocina', 'provincia': 'Sevilla', 'codigo_ine': '41092',
        'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
        'origen': 'inventario_documental_planeamiento',
        'url': PGOU if key == 'pgou' else ADAPTACION,
        'documentos': sorted(docs.values(), key=lambda d: d['url']),
        'publication_ready': False, 'geometry_status': 'unavailable',
        'coverage': 'Inventarios PGOU y adaptación LOUA; sin garantía de vigencia ni histórico completo',
    } for key, docs in sorted(groups.items())]


class TocinaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        groups, visited = {}, []
        capture = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-tocina-inventory/1.0'
            for kind, start in [('pgou', PGOU), ('adaptacion', ADAPTACION)]:
                pending, seen = [start], set()
                while pending:
                    url = pending.pop(0)
                    if url in seen:
                        continue
                    if len(seen) >= 100:
                        raise ValueError('Pagination exceeds safety limit; no partial output written')
                    seen.add(url)
                    response = session.get(url, timeout=45)
                    response.raise_for_status()
                    if urlsplit(response.url).hostname != urlsplit(start).hostname:
                        raise ValueError('Unexpected inventory redirect')
                    if capture:
                        folder = Path(capture)
                        folder.mkdir(parents=True, exist_ok=True)
                        (folder / f'{kind}-{len(seen)}.html').write_text(response.text, encoding='utf-8')
                    parsed, pages = parse_inventory(response.text, response.url, kind)
                    visited.append(response.url)
                    for key, docs in parsed.items():
                        groups.setdefault(key, {}).update(docs)
                    pending.extend(p for p in pages if p not in seen and p not in pending)
        # A disappeared inventory/group is an error, rather than a successful empty update.
        if not {'pgou', 'adaptacion-loua', 'correccion-adaptacion'} <= groups.keys():
            raise ValueError('Expected planning document groups missing')
        rows = make_records(groups)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': visited,
                'documents': sum(len(r['documentos']) for r in rows),
                'coverage': 'partial_current_document_inventories', 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
