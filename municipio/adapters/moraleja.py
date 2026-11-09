"""Municipal planning notices: complete board traversal, one row per instrument."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.moraleja.es'
SOURCE = BASE + '/ayuntamiento/tablon-de-anuncios/obras-y-urbanismo'
LIMITATIONS = [
    'Partial thematic coverage: Plan General Municipal, its numbered modifications and SAU reparcelaciones in the municipal board only.',
    'Municipal notices are historical publications, not a complete current planning register; later regional proceedings are outside extraction scope.',
    'Municipal publication metadata can predate the agreement described in edited pages; retain dates per notice, never infer an approval from metadata.',
    'Documents are discovered links, not parsed legal decisions; legacy SITEX and Dropbox links may be obsolete.',
    'No verified granted licences, project geometry or coordinates; no geocoding.',
]


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def municipal_url(href, parent):
    url = urljoin(parent, href)
    p = urlsplit(url)
    if p.hostname != 'www.moraleja.es' or p.scheme not in {'http', 'https'}:
        raise ValueError('Unexpected municipal URL: ' + url)
    return p._replace(scheme='https', fragment='').geturl()


def instrument(title):
    text = norm(title)
    if any(word in text for word in ('licitacion', 'ordenanza', 'solicitud')):
        return None
    if 'plan general municipal' in text:
        if 'modificacion' in text:
            match = re.search(r'modificacion\s+puntual\s+(?:(?:num\.?|n[.º°]*)\s*)?(\d+)\b', text)
            if not match:
                raise ValueError('Unidentified PGM modification: ' + title)
            number = match[1]
            return 'pgm-mod-' + number, 'Modificación puntual ' + number + ' del Plan General Municipal de Moraleja', 'modificacion_planeamiento'
        return 'pgm', 'Plan General Municipal de Moraleja', 'planeamiento_urbanistico'
    if 'reparcelacion' in text:
        match = re.search(r'\bsau\s*-?\s*(\d+)\b', text)
        if not match:
            raise ValueError('Unidentified reparcelación: ' + title)
        return 'reparcelacion-sau-' + match[1], 'Proyecto de reparcelación SAU-' + match[1] + ' de Moraleja', 'reparcelacion'
    return None


def parse_inventory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    view = soup.select_one('.view-id-tablon_de_anuncios.view-display-id-listado')
    if not view:
        raise ValueError('Municipal board markup missing')
    items = view.select('.view-content li.item')
    if not items:
        raise ValueError('Empty municipal board; requires review')
    notices = []
    for item in items:
        a = item.select_one('p.semibold a[href]')
        if not a:
            raise ValueError('Notice title missing')
        title = a.get_text(' ', strip=True)
        target = municipal_url(a['href'], url)
        if not urlsplit(target).path.startswith(urlsplit(SOURCE).path + '/'):
            raise ValueError('Notice outside municipal board')
        if instrument(title):
            notices.append({'titulo': title, 'url': target})
    pages = set()
    for a in view.select('.pager a[href]'):
        target = municipal_url(a['href'], url)
        parts = urlsplit(target)
        query = parse_qs(parts.query)
        if parts.path != urlsplit(SOURCE).path or (query and (set(query) != {'page'} or len(query['page']) != 1 or not query['page'][0].isdigit())):
            raise ValueError('Unrecognized board pagination')
        page = int(query.get('page', ['0'])[0])
        pages.add(SOURCE + ('?page=' + str(page) if page else ''))
    # Fingerprint all entries, including excluded notices, to catch ignored page queries.
    signature = tuple(a['href'] for a in view.select('.view-content p.semibold a[href]'))
    return notices, sorted(pages), signature, len(items)


def parse_notice(html, notice):
    soup = BeautifulSoup(html, 'html.parser')
    node = soup.select_one('.node-anuncios-generales')
    if node is None or not re.fullmatch(r'node-\d+', node.get('id', '')):
        raise ValueError('Expected municipal notice node')
    body = node.select_one('.main-node-content')
    stamp = node.select_one('.fecha-publicacion')
    if body is None or stamp is None:
        raise ValueError('Missing notice body/date')
    match = re.search(r'\b\d{2}/\d{2}/\d{4}\b', stamp.get_text(' ', strip=True))
    if not match:
        raise ValueError('Unrecognized municipal publication date')
    publication = datetime.strptime(match[0], '%d/%m/%Y').date().isoformat()
    description = '\n'.join(p.get_text(' ', strip=True) for p in body.select('p') if p.get_text(strip=True))
    if not description:
        raise ValueError('Notice has no narrative')
    docs = {}
    for a in node.select('#archivos a[href], .main-node-content a[href]'):
        target = urljoin(notice['url'], a['href'])
        parts = urlsplit(target)
        if parts.scheme not in {'http', 'https'}:
            continue
        if '/sites/default/files/' in parts.path or '/SITEX/ptofiguras/' in parts.path:
            docs.setdefault(target, {'titulo': a.get_text(' ', strip=True), 'url': target,
                                     'procedencia_url': notice['url'], 'verificacion': 'enlace_en_fuente_no_contenido'})
    # Narrow explicit narrative patterns; never read an approval from a page timestamp.
    agreement = None
    m = re.search(r'aprobada\s+definitivamente\s+por\s+acuerdo\s+de\s+la\s+comision.*?de\s+(\d{2}/\d{2}/\d{4})', norm(description))
    if m:
        agreement = datetime.strptime(m[1], '%d/%m/%Y').date().isoformat()
    m = re.search(r'por acuerdo del pleno.*?con fecha (\d{1,2}) de abril de (\d{4})', norm(description))
    if m:
        agreement = datetime(int(m[2]), 4, int(m[1])).date().isoformat()
    m = re.search(r'aprobado provisionalmente por el pleno de la corporacion con fecha (\d{1,2}) de mayo de (\d{4})', norm(description))
    if m:
        agreement = datetime(int(m[2]), 5, int(m[1])).date().isoformat()
    result = {**notice, 'source_node_id': node['id'], 'fecha_publicacion': publication,
              'fecha_publicacion_procedencia': 'metadato municipal; puede pertenecer a una versión anterior de la página',
              'descripcion': description, 'documentos': list(docs.values())}
    if agreement:
        result['fecha_acuerdo'] = agreement
        if publication < agreement:
            result['advertencia_fechas'] = 'El metadato de publicación precede al acuerdo narrado; página aparentemente actualizada sin cambiar la fecha.'
    return result


def group_notices(notices):
    groups = {}
    for notice in notices:
        key, title, kind = instrument(notice['titulo'])
        row = groups.setdefault(key, {
            'id': 'moraleja-' + key, 'municipio': 'Moraleja', 'codigo_ine': '10128',
            'provincia': 'Cáceres', 'titulo': title, 'tipo': kind,
            'source': 'ayuntamiento', 'origen': 'tablon_urbanismo', 'inventory_url': SOURCE,
            'url': notice['url'], 'anuncios': [], 'documentos': [],
            'geometry_status': 'unavailable', 'publication_ready': False,
            'cobertura': 'histórico del tablón municipal; estado vigente no determinado',
        })
        if any(n['source_node_id'] == notice['source_node_id'] for n in row['anuncios']):
            continue
        row['anuncios'].append(notice)
        for doc in notice['documentos']:
            if not any(d['url'] == doc['url'] and d['procedencia_url'] == doc['procedencia_url'] for d in row['documentos']):
                row['documentos'].append(doc)
    for row in groups.values():
        if not row['documentos']:
            raise ValueError('Instrument has no source documents: ' + row['id'])
    if not groups:
        raise ValueError('No supported planning instruments in municipal inventory')
    return [groups[k] for k in sorted(groups)]


class MoralejaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=35, headers={'User-Agent': 'municipio-moraleja/1.0 (public planning inventory)'})
        response.raise_for_status()
        if municipal_url(response.url, url) != url:
            raise ValueError('Unexpected source redirect')
        if 'text/html' not in response.headers.get('Content-Type', ''):
            raise ValueError('Expected HTML source')
        if self.config.get('evidence_dir'):
            folder = Path(self.config['evidence_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pending, seen, signatures, notices, source_urls = [SOURCE], set(), set(), {}, []
        inventory_items = 0
        while pending:
            url = pending.pop(0)
            if url in seen:
                continue
            if len(seen) >= 100:
                raise ValueError('Pagination exceeds safety limit; no partial output written')
            entries, pages, signature, count = parse_inventory(self._fetch(url), url)
            if signature in signatures:
                raise ValueError('Repeated inventory page; possible ignored pagination')
            signatures.add(signature)
            seen.add(url)
            source_urls.append(url)
            inventory_items += count
            for entry in entries:
                notices.setdefault(entry['url'], entry)
            pending.extend(p for p in pages if p not in seen and p not in pending)
        parsed = []
        for url, notice in notices.items():
            parsed.append(parse_notice(self._fetch(url), notice))
            source_urls.append(url)
        rows = group_notices(parsed)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'live_records': len(rows),
                'inventory_pages': len(seen), 'inventory_items': inventory_items,
                'supported_notices': len(parsed), 'source_urls': source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
