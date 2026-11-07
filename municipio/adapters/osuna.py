"""Osuna: reviewed named instruments in the municipal transparency inventory."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://transparencia.osuna.es/es/transparencia/indicadores-de-transparencia/'
          'indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00027/')
PAGE_PARAM = 'pagegalleryfiles-1-1'
LIMITATIONS = [
    'Inventario documental parcial: solo instrumentos identificables por sus adjuntos; no registro exhaustivo municipal.',
    'No se extrae el contenido del registro de planeamiento enero 2016 ni documentos de identidad ambigua.',
    'Las denominaciones del inventario no acreditan por sí solas vigencia, ejecución ni concesión de licencia.',
    'Sin fechas de publicación/acuerdo extraídas, sin coordenadas y sin geocodificación.',
    'El estudio de ordenación Las Vegas y la modificación NNSS PI-7 se conservan como instrumentos distintos.',
]


def normalize(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def instrument(title):
    """Reviewed identities, never manufacture rows for absent documents."""
    t = normalize(title)
    if re.search(r'\b(modelo|solicitud|licitacion|contratacion|anuncio de licitacion)\b', t):
        return None
    # Exact ambiguous labels resolved by reading their official PDFs on 2026-11-07.
    if t == 'acuerdo pleno aprobacion inicial':
        return 'pms-ermita-santa-ana', 'Proyecto de delimitación PMS: ampliación Ermita Santa Ana'
    if t == '1104-2016 acuerdo pleno p1609261013.-modificacion puntual nnss-1':
        return 'nnss-art117', 'Modificación puntual NNSS artículo 117: usos en área de servicio'
    if 'alcazaba' in t:
        return 'alcazaba', 'Proyecto de delimitación PMS para ampliación del parque arqueológico Alcazaba'
    if 'las vegas' in t:
        return 'eo-pi7-las-vegas', 'Estudio de ordenación P.I.-7 Las Vegas'
    if 'recinto ferial' in t or 'casetas permanentes' in t:
        return 'nnss-recinto-ferial-quinta', 'Modificación NNSS: construcciones permanentes en Recinto Ferial y La Quinta'
    if 'avance pgom' in t:
        return 'avance-pgom', 'Avance del Plan General de Ordenación Municipal de Osuna'
    if re.search(r'\b(?:pi-?7|p17)(?![a-z0-9])', t):
        return 'nnss-ampliacion-pi7', 'Modificación NNSS: ampliación PI-7'
    if 'ermita santa ana' in t:
        if 'delimitacion pms' in t:
            return 'pms-ermita-santa-ana', 'Proyecto de delimitación PMS: ampliación Ermita Santa Ana'
        return 'nnss-ermita-santa-ana', 'Modificación NNSS: Ermita Santa Ana'
    if 'vivienda protegida' in t:
        return 'cambio-uso-vivienda-protegida', 'Actuación de mejora urbana: cambio de uso a vivienda protegida en varias parcelas'
    if 'edar' in t:
        return 'plan-especial-edar-puerto-encina', 'Plan especial EDAR Puerto de la Encina'
    if 'hospital' in t:
        return 'nnss-ampliacion-hospital', 'Modificación PGOU/NNSS: ampliación del Hospital Comarcal de Osuna'
    if re.search(r'art\.?\s*117', t):
        return 'nnss-art117', 'Modificación puntual NNSS artículo 117: usos en área de servicio'
    return None


def page_url(number):
    parts = urlsplit(SOURCE)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/'),
                       urlencode({PAGE_PARAM: number}), ''))


def parse_page(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article.sg-indicador-trans')
    gallery = article.select_one('#galleryfiles-1-1') if article else None
    if gallery is None:
        raise ValueError('Missing reviewed municipal document gallery')
    docs = {}
    for a in article.select('a[href]'):
        target = urljoin(url, a['href'])
        parts = urlsplit(target)
        if (parts.hostname == 'transparencia.osuna.es'
                and parts.path.startswith('/export/sites/osuna/es/transparencia/.galleries/IND-53-/')
                and parts.path.lower().endswith('.pdf')):
            title = a.get_text(' ', strip=True)
            if title:
                docs[target] = {'titulo': title, 'url': target, 'inventory_url': url}
    if not docs:
        raise ValueError('Empty document inventory')
    pages = set()
    for a in article.select('a[href]'):
        target = urljoin(url, a['href'])
        parts = urlsplit(target)
        query = parse_qs(parts.query)
        if not any(k.startswith('pagegalleryfiles') for k in query):
            continue
        if (parts.hostname != urlsplit(SOURCE).hostname
                or parts.path.rstrip('/') != urlsplit(SOURCE).path.rstrip('/')
                or set(query) != {PAGE_PARAM}):
            raise ValueError('Unexpected gallery pagination; review before continuing')
        values = query[PAGE_PARAM]
        if len(values) != 1 or not values[0].isdigit() or int(values[0]) < 1:
            raise ValueError('Invalid inventory page')
        pages.add(int(values[0]))
    return list(docs.values()), pages


def group_documents(documents):
    rows = {}
    skipped = []
    for doc in documents:
        identity = instrument(doc['titulo'])
        if identity is None:
            skipped.append(doc)
            continue
        key, title = identity
        row = rows.setdefault(key, {
            'id': 'osuna-plan-' + key, 'municipio': 'Osuna', 'codigo_ine': '41068',
            'provincia': 'Sevilla', 'titulo': title, 'tipo': 'instrumento_urbanistico',
            'url': doc['url'], 'inventory_url': SOURCE, 'source': 'ayuntamiento',
            'origen': 'inventario_documental_planeamiento', 'documentos': [],
            'publication_ready': False, 'geometry_status': 'unavailable',
        })
        if doc['url'] not in {d['url'] for d in row['documentos']}:
            row['documentos'].append(doc)
    if not rows:
        raise ValueError('No identifiable planning instruments')
    return list(rows.values()), skipped


class OsunaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        pending, visited, documents, signatures = {1}, set(), {}, set()
        captures = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-osuna-inventory/1.0'
            while pending:
                number = min(pending)
                pending.remove(number)
                url = page_url(number)
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if (urlsplit(response.url).hostname != urlsplit(SOURCE).hostname
                        or urlsplit(response.url).path.rstrip('/') != urlsplit(SOURCE).path.rstrip('/')):
                    raise ValueError('Unexpected municipal inventory redirect')
                docs, pages = parse_page(response.text, url)
                signature = tuple(sorted(d['url'] for d in docs))
                if signature in signatures:
                    raise ValueError('Repeated page: server may have ignored pagination')
                signatures.add(signature)
                visited.add(number)
                # Last-page links advertise the full range even when only a window is visible.
                if pages:
                    pending.update(set(range(1, max(pages) + 1)) - visited)
                if captures:
                    path = Path(captures)
                    path.mkdir(parents=True, exist_ok=True)
                    (path / f'inventory-{number}.html').write_text(response.text, encoding='utf-8')
                for doc in docs:
                    documents.setdefault(doc['url'], doc)
        rows, skipped = group_documents(documents.values())
        out = Path(out_jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        temp = out.with_suffix(out.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(out)
        return {'count': len(rows), 'written': len(rows), 'live_records': len(rows),
                'source_urls': [page_url(n) for n in sorted(visited)],
                'document_count': len(documents), 'unclassified_documents': skipped,
                'limitations': LIMITATIONS, 'coverage': 'reviewed_named_planning_instruments'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out = Path(out_jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
