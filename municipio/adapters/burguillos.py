"""Burguillos: grouped PGOU and PBOM document inventories, never licence grants."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qsl, urldefrag, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

PGOU = ('https://transparencia.burguillos.es/es/transparencia/'
        'indicadores-de-transparencia/indicador/'
        'Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00057')
PBOM = 'https://nuevoplandeburguillos.es/'
ENDORSEMENT = ('https://www.burguillos.es/es/actualidad/noticias/'
               'NUEVO-PLAN-BASICO-DE-ORDENACION-MUNICIPAL-DEL-BURGUILLOS/')
PGOU_DOC_PATH = '/export/sites/burguillos/es/transparencia/.galleries/IND-50-/'
LIMITATIONS = [
    'Inventarios documentales del PGOU y del nuevo PBOM; no censo completo de actuaciones municipales.',
    'Sin registro verificado de licencias concedidas ni inventario exhaustivo de obras físicas.',
    'Los documentos de cada plan se agrupan; su publicación no acredita vigencia ni aprobación del conjunto.',
    'Sin fechas normalizadas: el PGOU narra acuerdos, publicaciones y resoluciones judiciales distintos; '
    'las carpetas de subida y las fases genéricas del PBOM no prueban fechas ni estado actual.',
    'Sin coordenadas ni geometría verificada; enlaces documentales retenidos, sin analizar todos los PDF.',
]


def parse_pgou_page(html: str, page_url: str) -> tuple[list[dict], list[str], str]:
    soup = BeautifulSoup(html, 'html.parser')
    if not any('Plan General de Ordenación Urbana (PGOU)' in h.get_text(' ', strip=True)
               for h in soup.select('h1,h2')):
        raise ValueError('Missing PGOU inventory heading')
    documents = {}
    pages = set()
    for a in soup.select('a[href]'):
        target = urldefrag(urljoin(page_url, a['href']))[0]
        parts = urlsplit(target)
        title = a.get_text(' ', strip=True)
        if (parts.hostname == urlsplit(PGOU).hostname and parts.path.startswith(PGOU_DOC_PATH)
                and parts.path.lower().endswith('.pdf') and title and a.find_parent('table')):
            documents[target] = {'titulo': title, 'url': target, 'inventory_url': page_url}
        if (parts.hostname == urlsplit(PGOU).hostname and parts.path == urlsplit(PGOU).path
                and any(k.startswith('pagegalleryfiles-') for k, v in parse_qsl(parts.query))):
            pages.add(target)
    if not documents:
        raise ValueError('PGOU page has no supported documents')
    # Keep the complete municipal chronology, without collapsing several dates into one.
    paragraphs = [p.get_text(' ', strip=True) for p in soup.select('p')]
    chronology = '\n'.join(t for t in paragraphs if 'PGOU' in t or 'Plan General de Ordenación' in t)
    return list(documents.values()), sorted(pages), chronology


def parse_pbom(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    if 'Burguillos' not in text or 'Plan Básico de Ordenación Municipal' not in text:
        raise ValueError('Missing Burguillos PBOM identity')
    documents = {}
    for a in soup.select('a[href]'):
        target = urldefrag(urljoin(PBOM, a['href']))[0]
        parts = urlsplit(target)
        title = a.get_text(' ', strip=True)
        if (parts.hostname in {'nuevoplandeburguillos.es', 'www.nuevoplandeburguillos.es'}
                and parts.path.startswith('/wp-content/uploads/')
                and parts.path.lower().endswith('.pdf') and title):
            documents[target] = {'titulo': title, 'url': target, 'inventory_url': PBOM}
    # A participation form/manual alone is not an urban planning instrument.
    if not any('memoria' in d['titulo'].lower() or 'estratégico' in d['titulo'].lower()
               for d in documents.values()):
        raise ValueError('PBOM lacks technical planning documents')
    # No pagination on this static document section; fail if a new page control appears.
    if soup.select('a[rel~=next], .pagination a[href], .nav-links .next'):
        raise ValueError('PBOM pagination requires review')
    return list(documents.values())


def record(key: str, title: str, url: str, documents: list[dict], pages: list[str]) -> dict:
    return {
        'id': 'burguillos-plan-' + key, 'municipio': 'Burguillos', 'codigo_ine': '41019',
        'provincia': 'Sevilla', 'titulo': title, 'tipo': 'planeamiento_urbanistico',
        'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_documental_planeamiento',
        'inventory_urls': pages, 'documentos': documents, 'coverage': 'partial_document_inventory',
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class BurguillosAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session: requests.Session, url: str) -> str:
        response = session.get(url, timeout=45)
        response.raise_for_status()
        if urlsplit(response.url).hostname != urlsplit(url).hostname:
            raise ValueError('Unexpected source redirect: ' + response.url)
        response.encoding = 'utf-8'
        self.source_urls.append(url)
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f'source-{len(self.source_urls):02d}.html').write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        self.source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-burguillos/1.0 (public planning inventory)'
            pending, visited, docs, signatures = [PGOU], [], {}, set()
            chronology = ''
            while pending:
                url = pending.pop(0)
                if url in visited:
                    continue
                if len(visited) >= 100:
                    raise ValueError('PGOU pagination exceeded safety limit; no partial output written')
                page_docs, links, description = parse_pgou_page(self._fetch(session, url), url)
                signature = tuple(sorted(d['url'] for d in page_docs))
                # The base URL and explicit page=1 are aliases. Any other duplicate is an error.
                first_alias = (not urlsplit(url).query or
                               all(v == '1' for k, v in parse_qsl(urlsplit(url).query)
                                   if k.startswith('pagegalleryfiles-')))
                if signature in signatures and not first_alias:
                    raise ValueError('PGOU pagination repeats a document page')
                signatures.add(signature)
                visited.append(url)
                for document in page_docs:
                    docs.setdefault(document['url'], document)
                if not chronology:
                    chronology = description
                pending.extend(link for link in links if link not in visited and link not in pending)
            pgou = record('pgou', 'Plan General de Ordenación Urbanística de Burguillos', PGOU,
                          list(docs.values()), visited)
            if chronology:
                pgou['descripcion'] = chronology
            endorsement = BeautifulSoup(self._fetch(session, ENDORSEMENT), 'html.parser')
            if not any(urlsplit(urljoin(ENDORSEMENT, a['href'])).hostname in
                       {'nuevoplandeburguillos.es', 'www.nuevoplandeburguillos.es'}
                       for a in endorsement.select('a[href]')):
                raise ValueError('Municipal endorsement of PBOM website missing')
            pbom = record('pbom', 'Plan Básico de Ordenación Municipal de Burguillos', PBOM,
                          parse_pbom(self._fetch(session, PBOM)), [PBOM])
            pbom['provenance_url'] = ENDORSEMENT
        self._write(out_jsonl, [pgou, pbom])
        return {'count': 2, 'written': 2, 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'coverage': 'partial_document_inventory'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        """Re-read current inventories; state is deliberately not a publication-date cursor."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified licence-grant register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
