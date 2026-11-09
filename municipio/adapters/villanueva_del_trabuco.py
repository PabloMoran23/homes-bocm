"""Anonymous municipal transparency inventory; documents grouped by instrument."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://villanuevadeltrabuco.sedelectronica.es'
SOURCE = BASE + '/transparency'
ROOT = BASE + '/transparency/6666264c-1b5f-4ab3-84ca-bd98d4719544/'


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def safe_url(url):
    if urlparse(url).netloc != urlparse(BASE).netloc or urlparse(url).scheme != 'https':
        raise ValueError('Unexpected nonmunicipal URL')
    return url


def parse_page(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.TransparencyListPanel')
    if table is None:
        raise ValueError('Transparency inventory missing')
    # The portal currently exposes complete folders. Fail closed if pagination
    # appears; parent recursive counts also detect missing document pages.
    if soup.select('.navigator, .pagination, .paging, .wicket-pagingnavigator'):
        raise ValueError('Pagination requires review; refusing partial inventory')
    folders, documents = [], []
    for a in table.select('a.gIconLink'):
        title = a.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            count = re.search(r'\(\s*(\d+)\s*\)\s*$', title)
            callback = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
            if not count or not callback:
                raise ValueError('Unrecognized folder/count')
            folders.append({'title': title[:count.start()].strip(), 'count': int(count[1]),
                            'url': safe_url(urljoin(url, callback[1]))})
        else:
            target = safe_url(urljoin(url, a.get('href', '')))
            if not urlparse(target).path.startswith('/preview-document/') or not title:
                raise ValueError('Unrecognized document link')
            documents.append({'titulo': title, 'descripcion': a.get('title'),
                              'url': target, 'inventory_url': url})
    return folders, documents


def instrument(path, doc):
    """Use source folder context; split mixed folders, never generic announcements."""
    context = norm(' / '.join(path))
    text = norm(doc['titulo'] + ' ' + (doc['descripcion'] or ''))
    if 'adaptacion' in context:
        return 'adaptacion-loua', 'Adaptación de las Normas Subsidiarias a la LOUA'
    if 'macro proyectos' in context:
        return 'nnss-renovables', path[-1]
    if path[-1] == 'MODIFICACIONES':
        if 'industrial' in text:
            return 'nnss-industrial', 'Modificación de las NNSS: usos industriales'
        if re.search(r'123[._ ]*2', text):
            return 'nnss-art123', 'Modificación de las NNSS: artículo 123.2.a)'
    if 'planes parciales' in context:
        if 'ur-3' in context + text:
            return 'plan-parcial-ur3', 'Plan Parcial del sector UR-3'
        if 'ur-7' in text and 'reparcelacion' in text:
            return 'reparcelacion-ur7', 'Proyecto de reparcelación del sector UR-7 La Yesera'
    if 'estudios detalles' in context:
        if 'ue-17' in context:
            return 'delimitacion-ue17', 'Nueva delimitación de la Unidad de Ejecución UE-17'
        if 'ur-4' in context:
            if 'modificacion' in text:
                return 'modificacion-ed-ur4', 'Modificación del Estudio de Detalle: vivienda sector UR-4'
            return 'ed-ur4', 'Estudio de Detalle: vivienda sector UR-4 (superior a 400 m2)'
        if 'calle canas' in context:
            return 'ed-canas', 'Estudio de Detalle: prolongación calle Las Cañas'
        if 'al-andalus' in context:
            return 'ed-alandalus', 'Estudio de Detalle: almacén calle Al-Andalus nº 10'
        if 'paseo virgen de los dolores' in text:
            return 'ed-paseo-dolores24', doc['descripcion']
    raise ValueError('Unclassified instrument; review new inventory document: ' + doc['titulo'])


def group_documents(pages):
    grouped = {}
    for page in pages:
        for doc in page['documents']:
            key, title = instrument(page['path'], doc)
            if key not in grouped:
                grouped[key] = {'id': 'villanueva-del-trabuco-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                    'municipio': 'Villanueva del Trabuco', 'codigo_ine': '29097', 'provincia': 'Málaga',
                    'titulo': title, 'tipo': 'instrumento o proyecto urbanístico',
                    'source': 'ayuntamiento', 'origen': 'portal_transparencia_municipal',
                    'url': page['url'], 'inventory_url': SOURCE, 'documentos': [],
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'fase': None, 'lat': None, 'lon': None, 'geometry': None,
                    'publication_ready': False, 'geometry_status': 'unavailable'}
            docs = grouped[key]['documentos']
            if doc['url'] not in {d['url'] for d in docs}:
                docs.append(doc)
    if not grouped:
        raise ValueError('No usable planning instruments')
    for row in grouped.values():
        row['url_documento'] = row['documentos'][0]['url']
        row['descripcion'] = '\n'.join(d['titulo'] + (': ' + d['descripcion'] if d['descripcion'] else '') for d in row['documentos'])
    return list(grouped.values())


class VillanuevaDelTrabucoAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('capture_dir')
        pages, visited = [], set()
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-villanueva-del-trabuco/1.0'

            def fetch(url):
                response = session.get(safe_url(url), timeout=40)
                response.raise_for_status()
                safe_url(response.url)
                if captures:
                    dest = Path(captures)
                    dest.mkdir(parents=True, exist_ok=True)
                    (dest / (hashlib.sha256(response.url.encode()).hexdigest()[:16] + '.html')).write_text(response.text, encoding='utf-8')
                return response.url, response.text

            def walk(url, path, expected):
                canonical, html = fetch(url)
                if canonical in visited:
                    raise ValueError('Repeated folder or pagination loop')
                visited.add(canonical)
                folders, documents = parse_page(html, canonical)
                pages.append({'url': canonical, 'path': path, 'documents': documents})
                total = len(documents)
                for folder in folders:
                    total += walk(folder['url'], path + [folder['title']], folder['count'])
                if total != expected:
                    raise ValueError(f'Incomplete inventory at {canonical}: expected {expected}, got {total}')
                return total

            root_url, root_html = fetch(ROOT)
            folders, _ = parse_page(root_html, root_url)
            selected = [f for f in folders if f['title'].startswith(('6.1.', '6.7 '))]
            if len(selected) != 2:
                raise ValueError('Expected municipal planning and LOUA inventories')
            for folder in selected:
                walk(folder['url'], [folder['title']], folder['count'])
        rows = group_documents(pages)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'documents': sum(len(p['documents']) for p in pages),
                'source_urls': [ROOT] + [p['url'] for p in pages],
                'coverage': 'complete recursive snapshot of sections 6.1 and 6.7 only', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
