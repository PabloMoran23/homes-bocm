"""Snapshot of Tobarra's municipal POM document inventory, not a licence register."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://tobarra.es/areas-municipales-urbanismo/'


def official_url(href, base=SOURCE):
    url = urlsplit(urljoin(base, href))
    if url.hostname != 'tobarra.es' or url.scheme not in {'http', 'https'} or url.port:
        raise ValueError(f'Unexpected document host: {href}')
    return urlunsplit(('https', 'tobarra.es', url.path, url.query, ''))


def parse_inventory(html, source_url=SOURCE):
    """Return all document links and nested inventory pages; reject pagination."""
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    heading = main.select_one('h1') if main else None
    if not heading or 'urbanismo' not in heading.get_text(' ', strip=True).lower():
        raise ValueError('Missing municipal urbanismo content')
    if soup.select('[rel~=next], .pagination, .nav-links, .page-links, .elementor-pagination'):
        raise ValueError('Pagination detected; extend crawler before accepting snapshot')
    for a in main.select('a[href]'):
        if a.get_text(' ', strip=True).lower() in {'siguiente', 'next', '»', '›'}:
            raise ValueError('Pagination detected')
    if source_url == SOURCE:
        groups = [a.get_text(' ', strip=True) for a in main.select('.elementor-accordion-title')]
        if groups != ['D1 M1', 'D2 PI', 'D3 MJ', 'D4 PO', 'D5 NNUU', 'D6 CAT']:
            raise ValueError('POM inventory structure changed')
    docs, children = {}, {}
    for a in main.select('a[href]'):
        raw = urljoin(source_url, a['href'])
        path = urlsplit(raw).path
        if not (path.lower().endswith('.pdf') or path.startswith('/urbanismo-')):
            continue
        url = official_url(raw, source_url)
        label = a.get_text(' ', strip=True)
        block = a.find_parent(class_='elementor-accordion-item')
        group = block.select_one('.elementor-accordion-title') if block else None
        section = group.get_text(' ', strip=True) if group else heading.get_text(' ', strip=True)
        if path.lower().endswith('.pdf'):
            docs.setdefault(url, {'titulo': unquote(path.rsplit('/', 1)[-1]),
                                  'texto_enlace': label, 'seccion': section,
                                  'url': url, 'url_enlace_original': raw,
                                  'source_url': source_url})
        else:
            children.setdefault(url, {'url': url, 'titulo': label,
                                      'url_enlace_original': raw, 'source_url': source_url})
    if not docs or 'Plan de Ordenación Municipal' not in main.get_text(' ', strip=True):
        raise ValueError('No verified POM document inventory')
    if source_url == SOURCE and not any(d['titulo'] == 'Doc3-Memoria-Justificativa.pdf' for d in docs.values()):
        raise ValueError('Missing POM memoria justificativa')
    return list(docs.values()), list(children.values())


class TobarraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='tobarra', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://tobarra.es')

    def _fetch(self, session, url):
        response = session.get(url, timeout=40)
        official_url(response.url)
        capture = self.config.get('evidence_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            name = urlsplit(url).path.strip('/').replace('/', '_') or 'index'
            (directory / (name + '.html')).write_bytes(response.content)
        return response

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-tobarra/1.0'
            root = self._fetch(session, SOURCE)
            root.raise_for_status()
            documents, pending = parse_inventory(root.content)
            pages, seen = [], {SOURCE}
            while pending:
                child = pending.pop(0)
                url = child['url']
                if url in seen:
                    continue
                if len(seen) >= 30:
                    raise ValueError('Inventory expanded beyond reviewed scope; no partial output written')
                seen.add(url)
                response = self._fetch(session, url)
                page = {**child, 'http_status': response.status_code}
                pages.append(page)
                # Preserve a municipally linked but removed volume as a coverage gap.
                if response.status_code in {404, 410}:
                    page['limitacion'] = 'Subinventario municipal no disponible; documentos no extraídos'
                    continue
                response.raise_for_status()
                docs, nested = parse_inventory(response.content, url)
                documents.extend(docs)
                pending.extend(nested)
        unique = {doc['url']: doc for doc in documents}
        row = {
            'id': 'tobarra-pom', 'municipio': 'Tobarra', 'codigo_ine': '02074',
            'provincia': 'Albacete', 'titulo': 'Plan de Ordenación Municipal de Tobarra',
            'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_documental_pom',
            'descripcion': 'Instrumento de planeamiento publicado por el Ayuntamiento; documentos agrupados. '
                           'La página HTML no acredita vigencia ni fechas de acuerdos o publicación.',
            'documentos': list(unique.values()), 'inventarios_relacionados': pages,
            'cobertura': 'Parcial: inventario municipal del POM; no registro general de proyectos ni licencias.',
            'limitaciones': [p['limitacion'] + ': ' + p['url'] for p in pages if 'limitacion' in p],
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        }
        return {**self._write(out_jsonl, [row]), 'source_urls': sorted(seen),
                'documents': len(unique), 'limitations': row['limitaciones']}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
