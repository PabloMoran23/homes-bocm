"""Olite's official PGM dossier; one instrument, multiple source documents."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.olite.es/plan-general-municipal/'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def canonical(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, '', ''))


def parse_page(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    # Navigation outside the dossier (including latest-news widgets) is excluded.
    content = soup.select_one('.contenido.content > .mt-3, .noticia_text')
    title = soup.select_one('.titulo-single, .noticia_titulo')
    if content is None or title is None:
        raise ValueError(f'Missing dossier content: {url}')
    if soup.select_one('a[rel~=next], .pagination, .page-links, .nav-links'):
        raise ValueError(f'Pagination requires review: {url}')
    for a in content.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', 'más', 'cargar más'}:
            raise ValueError(f'Uncovered continuation: {url}')
    text = content.get_text(' ', strip=True)
    page = {'url': url, 'titulo': title.get_text(' ', strip=True), 'texto_fuente': text}
    published = soup.select_one('.cabecera-single .noticia_fecha')
    if published:
        m = re.fullmatch(r'(\d{1,2}) de (\w+) de (\d{4})', published.get_text(strip=True))
        if not m or m[2] not in MONTHS:
            raise ValueError(f'Unknown publication date: {url}')
        page['fecha_publicacion'] = date(int(m[3]), MONTHS.index(m[2]) + 1, int(m[1])).isoformat()
    documents, sections = {}, {}
    for a in content.select('a[href]'):
        target = canonical(urljoin(url, a['href']))
        p = urlsplit(target)
        label = a.get_text(' ', strip=True)
        if not label or p.scheme != 'https':
            continue
        is_document = (p.hostname == 'drive.google.com' and p.path.startswith('/file/d/')) or (
            p.hostname == 'www.olite.es' and p.path.lower().endswith(('.pdf', '.zip', '.doc', '.docx')))
        if is_document:
            documents[target] = {'titulo': label, 'url': target, 'pagina_fuente': url,
                                 'verificacion': 'enlace_publicado_por_el_ayuntamiento'}
        elif p.hostname == 'www.olite.es' and not p.path.startswith('/wp-content/'):
            sections[target] = label
    return page, list(documents.values()), list(sections)


def parse_dossier(html, fetch):
    root, docs, sections = parse_page(html, SOURCE)
    if root['titulo'].casefold() != 'plan general municipal' or 'EMOT' not in root['texto_fuente']:
        raise ValueError('PGM inventory changed or is missing')
    pages = [root]
    for url in sections:
        if url == SOURCE:
            continue
        page, attachments, _ = parse_page(fetch(url), url)
        pages.append(page)
        docs.extend(attachments)
    if not docs:
        raise ValueError('No planning documents in the PGM dossier')
    # Deduplicate files without losing the municipal pages that link them.
    grouped = {}
    for doc in docs:
        provenance = {'url': doc['pagina_fuente'], 'titulo_enlace': doc['titulo']}
        entry = grouped.setdefault(doc['url'], {k: v for k, v in doc.items() if k != 'pagina_fuente'})
        if provenance not in entry.setdefault('procedencia', []):
            entry['procedencia'].append(provenance)
    row = {
        'id': 'olite-plan-' + hashlib.sha256(SOURCE.encode()).hexdigest()[:16],
        'municipio': 'Olite / Erriberri', 'codigo_ine': '31191', 'provincia': 'Navarra',
        'titulo': root['titulo'], 'tipo': 'planeamiento_urbanistico',
        'url': SOURCE, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
        'origen': 'dossier_plan_general_municipal', 'documentos': list(grouped.values()),
        'paginas_fuente': pages, 'geometry_status': 'unavailable', 'publication_ready': False,
        'cobertura': 'Dossier PGM y secciones directamente enlazadas; no inventario municipal completo.',
    }
    # No generic, agreement or approval dates: dossier pages do not establish them.
    return [row]


class OliteAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipal-inventory-olite/1.0'

            def fetch(url):
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if urlsplit(response.url).hostname != 'www.olite.es':
                    raise ValueError(f'Unexpected source redirect: {response.url}')
                if captures:
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    name = urlsplit(url).path.strip('/').replace('/', '_') or 'index'
                    (directory / (name + '.html')).write_text(response.text, encoding='utf-8')
                return response.text

            rows = parse_dossier(fetch(SOURCE), fetch)
        return {**self._write(out_jsonl, rows), 'coverage': 'PGM dossier only'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
