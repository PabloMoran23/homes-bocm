"""Laviana's current RPGUR planning inventory, linked by the municipality."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://www54.asturias.es/rpgur/'
MUNICIPAL_SOURCE = 'https://www.ayto-laviana.es/normativa-urbanistica'
INVENTORY = ROOT + 'action/publico/busquedaConsulta?method=listPublico&primeraVez=false&ambito=MUN&idConcejo=32&estado=V'
DETAIL = ROOT + 'action/publico/gestionConsulta?method=retrieve&idInstrumento='
DOCS = ROOT + 'action/publico/gestionConsulta?method=docs&idInstrumento='
SUPPORTED = re.compile(r'^(Plan General|Modificaci[oó]n|Cat[aá]logo Urban[ií]stico|Plan Especial|Estudio (?:de )?Detalle|Proyecto (?:de |Expropiaci[oó]n))', re.I)


def text(node):
    return node.get_text(' ', strip=True) if node else ''


def resolve(soup, href, url):
    # RPGUR links are relative to the declared JSP base, not the action URL.
    base = soup.select_one('base[href]')
    target = urljoin(urljoin(url, base['href']) if base else url, href)
    parts = urlsplit(target)
    return urlunsplit((parts.scheme, parts.netloc, re.sub(r';jsessionid=[^/?;]+', '', parts.path), parts.query, ''))


def registry_url(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname != 'www54.asturias.es' or not parts.path.startswith('/rpgur/action/publico/'):
        raise ValueError('Unexpected RPGUR navigation URL')
    return url


def parse_inventory(html, url=INVENTORY):
    soup = BeautifulSoup(html, 'html.parser')
    summary = re.search(r'(\d+) registros encontrados\.\s*Mostrando del (\d+) al (\d+)', text(soup))
    table = soup.select_one('table#instrumento')
    if not summary or table is None:
        raise ValueError('Missing RPGUR inventory/count (blocked or changed source)')
    total, start, end = map(int, summary.groups())
    records = []
    for tr in table.select('tbody > tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 7:
            raise ValueError('Changed inventory columns')
        _, scope, town, category, title, dossier, status = map(text, cells)
        if (scope, town, status) != ('Municipal', 'LAVIANA', 'Vigente'):
            raise ValueError('Inventory escaped Laviana/current filter')
        a = cells[0].select_one('a[href]')
        if not a or not title:
            raise ValueError('Inventory row lacks identity/title')
        link = registry_url(resolve(soup, a['href'], url))
        ident = parse_qs(urlsplit(link).query).get('idInstrumento', [''])[0]
        if not ident.isdigit() or urlsplit(link).path != '/rpgur/action/publico/gestionConsulta':
            raise ValueError('Invalid instrument identity')
        records.append({'rpgur_id': ident, 'titulo': title, 'expediente': dossier or None,
                        'clasificacion': category, 'estado': status, 'url': DETAIL + ident})
    if len(records) != end - start + 1 or not 1 <= start <= end <= total:
        raise ValueError('Inventory range/count mismatch')
    next_links = {registry_url(resolve(soup, a['href'], url)) for a in soup.select('a[href]') if text(a) == 'Siguiente'}
    if len(next_links) > 1 or bool(next_links) != (end < total):
        raise ValueError('Incomplete or ambiguous pagination')
    next_url = next(iter(next_links), None)
    if next_url:
        query = parse_qs(urlsplit(next_url).query)
        if any(query.get(k) != [v] for k, v in {'idConcejo': '32', 'estado': 'V', 'ambito': 'MUN', 'method': 'listPublico'}.items()):
            raise ValueError('Pagination escaped search filter')
    return records, total, start, end, next_url


def parse_detail(html, row):
    soup = BeautifulSoup(html, 'html.parser')
    ident = soup.select_one('input[name="idInstrumento"]')
    if not ident or ident.get('value') != row['rpgur_id']:
        raise ValueError('Detail identity mismatch/blocked source')
    fields, events, documents = {}, [], {}
    for block in soup.select('#instrumentoForm .item_row'):
        label = block.select_one('.label_consulta2')
        value = block.select_one('.item_75')
        if not label or value is None:
            continue
        name, raw = text(label).rstrip(' :'), text(value)
        fields[name] = raw
        if name.lower().startswith(('acuerdo ', 'publicación ')):
            # Only labelled date fields, never dates embedded in notes or titles.
            when = datetime.strptime(raw, '%d/%m/%Y').date().isoformat() if raw else None
            events.append({'concepto': name, 'fecha': when, 'source_url': row['url']})
        for a in value.select('a[href]'):
            target = resolve(soup, a['href'], row['url'])
            host = urlsplit(target).hostname or ''
            if host == 'asturias.es' or host.endswith('.asturias.es'):
                if '/bopa/' in urlsplit(target).path.lower() or name == 'Enlaces':
                    doc = documents.setdefault(target, {'url': target, 'titulos': [], 'source_url': row['url']})
                    if text(a) not in doc['titulos']:
                        doc['titulos'].append(text(a))
    if fields.get('Concejo') != 'LAVIANA' or fields.get('Ámbito') != 'Municipal' or fields.get('Estado') != 'Vigente' or fields.get('Denominación') != row['titulo']:
        raise ValueError('Detail does not match inventory municipality/title/status')
    if (fields.get('Expediente') or None) != row['expediente']:
        raise ValueError('Dossier changed between list and detail')
    dates = {event['concepto'].lower(): event['fecha'] for event in events}
    return {**row, 'id': 'laviana-rpgur-' + row['rpgur_id'],
            'municipio': 'Laviana', 'codigo_ine': '33032', 'provincia': 'Asturias',
            'tipo': 'instrumento de planeamiento' if row['clasificacion'] != 'Gestión' else 'proyecto de gestión urbanística',
            'source': 'ayuntamiento', 'origen': 'registro_autonomico_rpgur',
            'inventory_url': INVENTORY, 'municipal_source_url': MUNICIPAL_SOURCE,
            'fecha': None, 'fecha_acuerdo': dates.get('acuerdo aprobación definitiva'),
            'fecha_aprob': dates.get('acuerdo aprobación definitiva'),
            'fecha_publicacion': dates.get('publicación bopa aprobación definitiva'),
            'fecha_publicacion_texto_refundido': dates.get('publicación bopa texto refundido'),
            'hitos': events, 'notas_fuente': fields.get('Notas'),
            'documentos': list(documents.values()), 'url_documentos': DOCS + row['rpgur_id'],
            'url_mapa': 'https://sigvisor.asturias.es/visorurbanismo/?id_instrumento=' + row['rpgur_id'],
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'Not extracted; official instrument viewer linked'}


def parse_documents(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    if not text(soup.select_one('h1')).startswith('Documentos'):
        raise ValueError('Document inventory blocked or changed')
    if any(text(a).lower() in {'siguiente', 'next'} for a in soup.select('a[href]')):
        raise ValueError('Document tree now paginated; enumeration incomplete')
    if 'No existen Documentos' in text(soup.select_one('#cuerpo_pagina')):
        return []
    tree = soup.select_one('#menuArbol')
    if tree is None:
        raise ValueError('Document tree missing')
    docs = {}
    for a in tree.select('a[href]'):
        target = registry_url(resolve(soup, a['href'], url))
        query = parse_qs(urlsplit(target).query)
        ident = query.get('idDocumento', [''])[0]
        if query.get('method') != ['descargaDocumentosArbol'] or not ident.isdigit():
            raise ValueError('Unexpected document tree link')
        docs[target] = {'url': target, 'titulos': [text(a)], 'rpgur_document_id': ident, 'source_url': url}
    if not docs:
        raise ValueError('Empty/unrecognized document tree')
    return list(docs.values())


class LavianaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        registry_url(url)
        response = session.get(url, timeout=35)
        response.raise_for_status()
        registry_url(response.url)
        if len(response.content) > 5_000_000:
            raise ValueError('Oversized RPGUR HTML response')
        capture = self.config.get('capture_dir')
        if capture:
            # Optional local audit captures, never used as an extraction fallback.
            import hashlib
            folder = Path(capture)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (hashlib.sha256(url.encode()).hexdigest()[:20] + '.html')).write_bytes(response.content)
        # RPGUR declares ISO-8859-1; parsing bytes also respects its HTML meta.
        return response.content

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows, excluded, pages, seen = [], [], [], set()
        expected, inventory_count, end = None, 0, 0
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-laviana/1.0 (public urban planning inventory)'
            url = INVENTORY
            while url:
                if url in pages or len(pages) >= 100:
                    raise ValueError('Pagination loop/limit; no partial snapshot written')
                batch, total, start, last, next_url = parse_inventory(self._fetch(session, url), url)
                if (expected is not None and total != expected) or start != end + 1:
                    raise ValueError('Inventory changed or pagination skipped records')
                expected, end = total, last
                pages.append(url)
                for row in batch:
                    if row['rpgur_id'] in seen:
                        raise ValueError('Duplicate instrument across inventory pages')
                    seen.add(row['rpgur_id'])
                    inventory_count += 1
                    if not SUPPORTED.match(row['titulo']):
                        excluded.append({**row, 'reason': 'Outside named planning/project scope (e.g. convenio)'})
                        continue
                    rows.append(row)
                url = next_url
            if inventory_count != expected or not rows:
                raise ValueError('Incomplete or empty current planning inventory')
            for i, row in enumerate(rows):
                record = parse_detail(self._fetch(session, row['url']), row)
                try:
                    docs = parse_documents(self._fetch(session, record['url_documentos']), record['url_documentos'])
                    existing = {doc['url'] for doc in record['documentos']}
                    record['documentos'].extend(doc for doc in docs if doc['url'] not in existing)
                    record['document_listing_status'] = 'ok' if docs else 'no_documents_in_register'
                except (requests.RequestException, ValueError) as error:
                    # A real, verified instrument remains useful when its optional
                    # file tree is unavailable. Keep the source link and limitation.
                    record['document_listing_status'] = 'unavailable'
                    record['document_listing_error'] = str(error)
                rows[i] = record
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_records': inventory_count,
                'inventory_pages': pages, 'excluded': excluded,
                'source_urls': pages + [r['url'] for r in rows] + [r['url_documentos'] for r in rows],
                'document_listing_unavailable': sum(r['document_listing_status'] == 'unavailable' for r in rows),
                'publication_ready': False, 'coverage': 'current municipal RPGUR instruments; historical and in-progress excluded'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
