"""Public Dalías territory inventory: grouped planning instruments and projects."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.dalias.es'
SOURCE = BASE + '/Servicios/cmsdipro/index.nsf/tablon_view_entidad_categoria1.xsp?p=Dalias&cat=Territorio'
LIMITATIONS = [
    'Only the current public Territorio inventory; not a complete historical register.',
    'Publication dates belong to individual source pages, not agreements or approvals.',
    'Document labels retained; legal validity, approval dates and geometry not inferred.',
    'Licence register disabled. No geocoding. PDFs linked, not exhaustively interpreted.',
    'Unexpected pagination fails explicitly rather than returning a truncated inventory.',
]


def official_url(href: str, page: str) -> str:
    url = urljoin(page, href)
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'www.dalias.es':
        raise ValueError('Unexpected source host or protocol')
    return url


def inventory_soup(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.select_one('table.xspDataTable') or not soup.select_one('form.xspForm'):
        raise ValueError('Territorio inventory missing (possibly login or changed layout)')
    # The reviewed inventory has no pager. Never accept a newly paginated subset.
    if soup.select('[id*="pager"] a, [id*="Pager"] a, .xspPagerContainer a, .xspPagerLeft a, .xspPagerRight a'):
        raise ValueError('Pagination detected; full traversal must be reviewed')
    for link in soup.select('a'):
        label = (link.get_text(' ', strip=True) + ' ' + link.get('title', '')).lower()
        if link.get('rel') == ['next'] or re.search(r'\b(siguiente|next|última página)\b', label):
            raise ValueError('Pagination detected; refusing partial coverage')
    return soup


def inventory_links(html: str) -> list[str]:
    soup = inventory_soup(html)
    if soup.select('table.xspDataTable button:has(img[src$="/expand.gif"]), table.xspDataTable button[title^="plegado"], table.xspDataTable button[title^="collapsed"]'):
        raise ValueError('Inventory still contains collapsed categories')
    links = {}
    for a in soup.select('table.xspDataTable a[href]'):
        url = official_url(a['href'], SOURCE)
        if urlparse(url).path.endswith('/tablon.xsp'):
            docid = parse_qs(urlparse(url).query).get('documentId', [''])[0]
            if not re.fullmatch('[A-Fa-f0-9]{32}', docid):
                raise ValueError('Invalid inventory document identifier')
            links[docid] = BASE + '/Servicios/cmsdipro/index.nsf/tablon.xsp?p=Dalias&documentId=' + docid
    if not links:
        raise ValueError('No public territory entries')
    return list(links.values())


def parse_detail(html: str, url: str) -> dict | None:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#doc-lectura-cultura')
    title = soup.select_one('h1')
    if content is None or title is None:
        raise ValueError('Missing municipal document content')
    heading = content.select_one('.left')
    if heading is None or 'Ayuntamiento de Dalías' not in heading.get_text(' ', strip=True):
        raise ValueError('Wrong municipality')
    category = next((p.get_text(' ', strip=True) for p in heading.select('p')
                     if p.get_text(strip=True).startswith('Territorio - ')), '')
    title = title.get_text(' ', strip=True)
    group = category.split(' - ')[-1]
    if category.startswith('Territorio - Planeamiento Urbanístico - '):
        if group in {'Normas Subsidiarias', 'Adaptacion Parcial NNSS'}:
            key = group
            record_title = group + ' de Dalías'
        elif group in {'CORRECCION DE ERRORES MATERIALES', 'Estudios de Detalle Ajuste de Alineaciones'}:
            key = url
            record_title = title
        else:
            raise ValueError('Unreviewed planning category: ' + category)
        kind = 'planeamiento_urbanistico'
    elif (category == 'Territorio - Urbanismo - Autorización para actuaciones extraordinarias de interés público en suelo rústico'
          and re.search(r'INSTALACION SOLAR FOTOVOLT', title, re.I)):
        key = url
        record_title = title
        kind = 'proyecto_actuacion'
    else:
        return None  # Forms, ordinances and unrelated entries are not projects.
    date_match = re.search(r'Publicado:\s*(\d{2}/\d{2}/\d{4})', content.get_text(' ', strip=True))
    if not date_match:
        raise ValueError('Missing explicit publication date')
    published = datetime.strptime(date_match[1], '%d/%m/%Y').date().isoformat()
    docs = {}
    for a in content.select('table a[href]'):
        if not re.search(r'/Servicios/Tablon/(?:anexos|archivadoanexos_\d+)\.nsf/', a['href']):
            continue
        target = official_url(a['href'], url)
        label = a.get_text(' ', strip=True)
        if label == '[descargar]':
            continue
        docs.setdefault(target, {'titulo': label, 'url': target, 'source_url': url,
                                 'fecha_publicacion_ficha': published,
                                 'archivado': '/archivadoanexos_' in target})
    if not docs:
        raise ValueError('Instrument or project lacks attached documents')
    if kind == 'proyecto_actuacion' and not any('Proyecto de Actuacion' in d['titulo'] for d in docs.values()):
        raise ValueError('Solar entry lacks the actual project document')
    return {'group_key': key, 'titulo': record_title, 'tipo': kind, 'url': url,
            'ficha': {'titulo': title, 'url': url, 'categoria': category, 'fecha_publicacion': published},
            'documentos': list(docs.values())}


def group_instruments(details: list[dict]) -> list[dict]:
    rows = {}
    for detail in details:
        key = detail['group_key']
        if key not in rows:
            rows[key] = {
                'id': 'dalias-' + hashlib.sha256(key.encode()).hexdigest()[:20],
                'municipio': 'Dalías', 'codigo_ine': '04038', 'provincia': 'Almería',
                'titulo': detail['titulo'], 'tipo': detail['tipo'], 'url': detail['url'],
                'source': 'ayuntamiento', 'source_entity_type': 'documento',
                'origen': 'inventario_territorio', 'inventory_url': SOURCE,
                'publication_ready': False, 'geometry_status': 'unavailable',
                'fichas': [], 'documentos': [],
            }
        row = rows[key]
        row['fichas'].append(detail['ficha'])
        row['documentos'].extend(detail['documentos'])
    if not rows:
        raise ValueError('No usable planning instruments or projects')
    return list(rows.values())


class DaliasAyuntamientoAdapter(AyuntamientoAdapter):
    def _capture(self, name, html):
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / name).write_text(html, encoding='utf-8')

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipal-public-inventory/1.0'

            def fetch(url, data=None):
                r = session.get(url, timeout=40) if data is None else session.post(url, data=data, timeout=40)
                r.raise_for_status()
                official_url(r.url, url)
                if '/names.nsf' in r.url:
                    raise ValueError('Public source redirected to login')
                return r.text

            html = fetch(SOURCE)
            self._capture('inventory-0.html', html)
            expanded = set()
            for index in range(200):
                soup = inventory_soup(html)
                button = soup.select_one('table.xspDataTable button:has(img[src$="/expand.gif"]), table.xspDataTable button[title^="plegado"], table.xspDataTable button[title^="collapsed"]')
                if button is None:
                    break
                event = button['id'].removesuffix('button')
                # Row indices change after expansion; the category position is stable.
                position = event.rsplit('__expand:', 1)[-1]
                if position in expanded:
                    raise ValueError('Category expansion made no progress')
                expanded.add(position)
                form = soup.select_one('form.xspForm')
                data = {x['name']: x.get('value', '') for x in form.select('input[name]')}
                data['$$xspsubmitid'] = event
                html = fetch(SOURCE, data)
                self._capture(f'inventory-{index + 1}.html', html)
            else:
                raise ValueError('Category traversal limit exceeded')
            links = inventory_links(html)
            details, excluded = [], []
            for url in links:
                html = fetch(url)
                docid = parse_qs(urlparse(url).query)['documentId'][0]
                self._capture(docid + '.html', html)
                detail = parse_detail(html, url)
                if detail is None:
                    excluded.append(url)
                else:
                    details.append(detail)
        rows = group_instruments(details)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(output)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [SOURCE, *links],
                'source_pages': len(links), 'excluded_urls': excluded, 'limitations': LIMITATIONS,
                'coverage': 'current_public_territorio_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # A complete snapshot also catches newly posted documents on old instruments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
