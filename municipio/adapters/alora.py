"""Current official Álora planning documents, grouped by instrument."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.alora.es/Inicio/'
LIMITATIONS = [
    'Cobertura parcial: instrumentos enlazados en el menú municipal actual; no registro histórico exhaustivo.',
    'No se extraen licencias, noticias, contratación ni modificaciones no enlazadas en este inventario.',
    'Documentos agrupados por instrumento; no se afirma vigencia ni aprobación definitiva.',
    'Sin geometría verificada; la fecha de publicación del PGOM corresponde al BOP, no a la web.',
    'El antiguo PGOU no se emite por separado: el PGOM reutiliza su borrador según el acuerdo municipal.',
]


def _official(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('alora.es', 'www.alora.es'):
        raise ValueError(f'Unexpected nonmunicipal URL: {url}')
    return url


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    if soup.select('a[rel~=next], link[rel~=next], .pagination, .paginacion'):
        raise ValueError('Pagination detected: refusing an incomplete snapshot')
    return soup


def _documents(container, url, directory):
    docs = {}
    for a in container.select('a[href]'):
        target = urljoin(url, a['href'])
        path = urlparse(target).path.lower()
        if path.startswith(directory) and path.endswith('.pdf'):
            _official(target)
            label = a.get_text(' ', strip=True)
            if not label:
                raise ValueError('Unlabelled planning document')
            docs[target] = {'titulo': label, 'url': target, 'source_url': url}
    if not docs:
        raise ValueError(f'No planning documents in {url}')
    return list(docs.values())


def _record(key, title, kind, url, docs):
    return {
        'id': 'alora-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
        'municipio': 'Álora', 'codigo_ine': '29012', 'provincia': 'Málaga',
        'titulo': title, 'tipo': kind, 'url': url, 'inventory_url': SOURCE,
        'documentos': docs, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
        'publication_ready': False, 'geometry_status': 'unavailable',
        'coverage': 'current_linked_planning_documents',
    }


def parse_menu(html, url=SOURCE):
    """Discover current plan pages and the named Mirasierra document group."""
    soup = _soup(html)
    pages = {}
    for a in soup.select('a[href]'):
        target = urljoin(url, a['href'])
        path = urlparse(target).path.lower().rstrip('/')
        if path in ('/ayuntamiento/pgom', '/ayuntamiento/nnss'):
            pages[path.rsplit('/', 1)[-1]] = _official(target.rstrip('/') + '/')
    if set(pages) != {'pgom', 'nnss'}:
        raise ValueError('Current municipal planning menu changed or missing')
    groups = []
    for li in soup.select('li'):
        anchor = li.find('a', recursive=False)
        if anchor and re.search(r'^Estudio detalle Calle Mirasierra\b', anchor.get_text(' ', strip=True), re.I):
            docs = _documents(li, url, '/ayuntamiento/informacion/mirasierra/')
            groups.append(_record('mirasierra', 'Estudio de detalle Calle Mirasierra',
                                  'estudio de detalle', url, docs))
    if len(groups) != 1:
        raise ValueError('Missing or ambiguous Mirasierra instrument group')
    return pages, groups


def _narrative_date(text, pattern):
    match = re.search(pattern, text, re.I)
    if not match:
        return None
    months = {'jul': 7, 'agos': 8}
    return date(2000 + int(match[3]), months[match[2].lower()], int(match[1])).isoformat()


def parse_plan(html, url, kind):
    soup = _soup(html)
    if kind == 'pgom':
        node = soup.find(string=lambda t: t and 'PUBLICACIÓN EN LA WEB DEL DOCUMENTO DE AVANCE DEL PGOM' in t)
        if not node:
            raise ValueError('Missing PGOM advance narrative')
        content = node.find_parent('td')
        if content is None:
            raise ValueError('Missing PGOM content block')
        text = content.get_text(' ', strip=True)
        docs = _documents(soup, url, '/ayuntamiento/pgom/')
        if not any('borrador' in d['titulo'].lower() for d in docs):
            raise ValueError('Missing PGOM draft document')
        row = _record('pgom', 'Avance del Plan General de Ordenación Municipal de Álora',
                      'PGOM', url, docs)
        row.update(descripcion=text, fase='avance')
        # The narrative attributes these dates to a plenary agreement and BOP.
        agreement = _narrative_date(text, r'Acuerdo de Sesión de pleno de (\d{1,2})/(Jul)/(\d{2})\b')
        publication = _narrative_date(text, r'Bop (\d{1,2})/(Agos)/(\d{2})\b')
        if agreement:
            row['fecha_acuerdo'] = agreement
            row['objeto_acuerdo'] = 'Consideración del borrador como avance del PGOM'
        if publication:
            row['fecha_publicacion'] = publication
            row['medio_publicacion'] = 'BOP (referenciado en la página municipal)'
    elif kind == 'nnss':
        node = soup.find(string=lambda t: t and 'NORMAS SUBSIDIARIAS DE PLANEAMIENTO DE ÁLORA' in t)
        if not node:
            raise ValueError('Missing NNSS instrument heading')
        docs = _documents(soup, url, '/ayuntamiento/nnss/')
        row = _record('nnss', node.strip(), 'normas subsidiarias de planeamiento', url, docs)
    else:
        raise ValueError(f'Unknown plan kind: {kind}')
    return row


class AloraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='alora', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def _fetch(self, url, name):
        _official(url)
        with requests.get(url, timeout=40, stream=True, headers={
            'User-Agent': 'municipio-alora/1.0 (public planning inventory)'
        }) as response:
            response.raise_for_status()
            _official(response.url)
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 2_000_000:
                    raise ValueError('Municipal HTML exceeds size limit')
            # Legacy ASP uses cp1252 with a few invalid bytes in shared menus.
            # Required instrument headings and document labels are checked below.
            html = bytes(content).decode('cp1252', errors='replace')
            if self.config.get('capture_dir'):
                folder = Path(self.config['capture_dir'])
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (name + '.html')).write_text(html, encoding='utf-8')
            return html, response.url

    def backfill_proyectos(self, out_jsonl):
        html, url = self._fetch(SOURCE, 'Inicio')
        pages, rows = parse_menu(html, url)
        sources = [url]
        for kind, target in sorted(pages.items()):
            html, final_url = self._fetch(target, kind)
            if urlparse(final_url).path.lower().rstrip('/') != urlparse(target).path.lower().rstrip('/'):
                raise ValueError('Unexpected planning page redirect')
            rows.append(parse_plan(html, final_url, kind))
            sources.append(final_url)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': sources,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full current snapshot; never claim an incremental history.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
