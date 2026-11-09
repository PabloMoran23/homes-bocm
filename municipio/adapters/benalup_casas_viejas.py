"""Current municipal planning documents; no inferred grants, dates or geometry."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOME = 'https://www.benalupcasasviejas.es/es/'
LIMITATIONS = [
    'Current municipal PGOU-labelled document and PBOM advance only; not a historical register.',
    'Documents are grouped by instrument; no claim of a granted licence or current legal validity.',
    'CMS file dates are not agreement or approval dates; no dates inferred.',
    'No verified geometry; publication and automatic scheduling disabled.',
    'PDF signatures verified, not full document contents parsed by the adapter.',
]


def official_url(url):
    p = urlparse(url)
    return p.scheme == 'https' and p.hostname == 'www.benalupcasasviejas.es'


def discover_inventory(html, url=HOME):
    soup = BeautifulSoup(html, 'html.parser')
    found = {}
    for label in ('PGOU vigente', 'AVANCE PBOM'):
        links = {urljoin(url, a['href']) for a in soup.select('a[href]')
                 if a.get_text(' ', strip=True).casefold() == label.casefold()}
        if len(links) != 1 or not all(official_url(u) for u in links):
            raise ValueError(f'Missing or ambiguous municipal inventory link: {label}')
        found[label] = links.pop()
    if not urlparse(found['PGOU vigente']).path.lower().endswith('.pdf'):
        raise ValueError('PGOU link is no longer a PDF')
    return found


def parse_catalog(html, url):
    """Read one PBOM page and expose all pagination links for traversal."""
    soup = BeautifulSoup(html, 'html.parser')
    box = soup.select_one('#phoca-dl-category-box')
    heading = box.select_one('.pd-ctitle') if box else None
    if not heading or heading.get_text(' ', strip=True).upper() != 'PBOM':
        raise ValueError('Missing PBOM category')
    documents = {}
    for a in box.select('.pd-filename a[href]'):
        target = urljoin(url, a['href'])
        query = parse_qs(urlparse(target).query)
        title = a.get_text(' ', strip=True)
        if title.casefold() not in {'documento urbanístico', 'documento inicial estratégico'}:
            raise ValueError('Unrecognized PBOM attachment; review grouping before extraction')
        if not official_url(target) or not query.get('download') or not title:
            raise ValueError('Invalid PBOM document link')
        documents[target] = {'titulo': title, 'url': target, 'inventory_url': url}
    if not documents:
        raise ValueError('PBOM category has no documents')
    pages = set()
    for a in box.select('.pagination a[href], a[rel="next"]'):
        target = urljoin(url, a['href'])
        if (not official_url(target) or urlparse(target).path != urlparse(url).path
                or 'download' in parse_qs(urlparse(target).query)):
            raise ValueError('Unexpected pagination target')
        pages.add(target)
    # A full page without exposed links cannot establish completeness.
    limit = box.select_one('select[name="limit"] option[selected]')
    if limit and int(limit.get('value', '0')) > 0:
        if len(documents) >= int(limit['value']) and not pages:
            raise ValueError('Full PBOM page without navigable pagination')
    return list(documents.values()), sorted(pages)


def make_records(inventory, documents):
    if not documents:
        raise ValueError('No PBOM documents')
    common = dict(municipio='Benalup-Casas Viejas', codigo_ine='11901', provincia='Cádiz',
                  source='ayuntamiento', origen='inventario_planeamiento_municipal',
                  tipo='instrumento de planeamiento urbanístico',
                  fecha_publicacion=None, fecha_acuerdo=None, fecha_aprob=None,
                  lat=None, lon=None, geometry=None, geometry_status='unavailable',
                  publication_ready=False, coverage='current_document_inventory')
    return [
        dict(common, id='benalup-casas-viejas-planeamiento-pgou',
             titulo='PGOU vigente — Benalup-Casas Viejas (rótulo municipal)',
             url=inventory['PGOU vigente'], inventory_url=HOME,
             documentos=[{'titulo': 'PGOU vigente', 'url': inventory['PGOU vigente'], 'inventory_url': HOME}],
             descripcion='Documento de planeamiento enlazado por el ayuntamiento como PGOU vigente. El rótulo no acredita su vigencia jurídica.'),
        dict(common, id='benalup-casas-viejas-planeamiento-pbom',
             titulo='Avance del Plan Básico de Ordenación Municipal de Benalup-Casas Viejas (PBOM)',
             fase='avance', url=inventory['AVANCE PBOM'], inventory_url=inventory['AVANCE PBOM'],
             documentos=sorted(documents, key=lambda d: d['url']),
             descripcion='Avance PBOM: documentación urbanística y ambiental agrupada en un único instrumento. No equivale a aprobación definitiva.'),
    ]


class BenalupCasasViejasAyuntamientoAdapter(AyuntamientoAdapter):
    def _html(self, session, url):
        with session.get(url, timeout=45) as r:
            r.raise_for_status()
            if not official_url(r.url) or 'html' not in r.headers.get('Content-Type', '').lower():
                raise ValueError('Unexpected inventory response')
            return r.text

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        capture_dir = Path(captures) if captures else None
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-benalup-planning/1.0'
            home = self._html(session, HOME)
            if capture_dir:
                (capture_dir / 'live-home.html').write_text(home, encoding='utf-8')
            inventory = discover_inventory(home)
            pending, visited, documents = [inventory['AVANCE PBOM']], set(), {}
            while pending:
                url = pending.pop(0)
                if url in visited:
                    continue
                if len(visited) >= 100:
                    raise ValueError('PBOM pagination exceeds safety bound; extraction incomplete')
                html = self._html(session, url)
                visited.add(url)
                if capture_dir:
                    (capture_dir / f'live-pbom-{len(visited)}.html').write_text(html, encoding='utf-8')
                docs, pages = parse_catalog(html, url)
                for doc in docs:
                    documents.setdefault(doc['url'], doc)
                pending.extend(p for p in pages if p not in visited)
            rows = make_records(inventory, list(documents.values()))
            checks = []
            for index, url in enumerate(sorted({d['url'] for row in rows for d in row['documentos']})):
                with session.get(url, timeout=60, stream=True) as r:
                    r.raise_for_status()
                    prefix = next(r.iter_content(8192), b'')
                    if not official_url(r.url) or not prefix.startswith(b'%PDF-'):
                        raise ValueError(f'Expected official PDF: {url}')
                    checks.append(dict(url=url, final_url=r.url, status=r.status_code,
                                       content_type=r.headers.get('Content-Type'), signature='PDF',
                                       content_length=r.headers.get('Content-Length')))
                    if capture_dir:
                        (capture_dir / f'live-document-{index}-prefix.bin').write_bytes(prefix)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return dict(count=len(rows), written=len(rows), source_urls=[HOME, *sorted(visited), *[c['url'] for c in checks]],
                    catalog_pages=len(visited), document_checks=checks, limitations=LIMITATIONS,
                    coverage='current_document_inventory', publication_ready=False)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full current snapshot; no timestamp cursor can recover unpublished history.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
