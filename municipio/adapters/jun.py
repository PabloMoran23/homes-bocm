"""Jun: current planning folders and public-works approval notices.

Only public inventories are read. No licence, implementation status, agreement
 date or geometry is inferred from a document title or CMS timestamp.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'ayuntamientojun.sedelectronica.es'
BOARD = f'https://{HOST}/board'
PLANNING = f'https://{HOST}/transparency/b12db815-40c7-4e1f-a3a4-4d473bf4cdec/'
LIMITATIONS = [
    'Cobertura parcial: carpetas de planeamiento y anuncios vigentes del tablón; no histórico completo.',
    'No se extraen licencias concedidas, contratos ni noticias.',
    'Las fechas del tablón son de publicación; no se extraen fechas de acuerdo del contenido PDF.',
    'Sin geometría verificada ni inferencia de ejecución o vigencia jurídica del planeamiento.',
    'Se conservan enlaces estables a fichas documentales; las descargas PDF usan tokens de sesión.',
]


def clean(text):
    return ' '.join(text.split())


def official(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != HOST:
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def checked_soup(html, selector):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one(selector)
    if table is None:
        raise ValueError(f'Inventory structure missing: {selector}')
    # Fail closed if the portal adds a paginator, including Wicket onclick links.
    for node in soup.select('a, button, [class], [rel]'):
        attrs = ' '.join([str(node.get(k, '')) for k in ('class', 'rel', 'title', 'aria-label')]).lower()
        if ('disabled' in attrs or node.get('aria-disabled') == 'true'):
            continue
        if any(word in attrs for word in ('pagin', 'navigator')) or re.search(r'\b(next|last|siguiente|última)\b', attrs + ' ' + node.get_text(' ', strip=True).lower()):
            raise ValueError('Pagination detected; refusing partial extraction')
    return soup, table


def documents(table, url):
    docs = {}
    for a in table.select('a[href]'):
        target = urljoin(url, a['href'])
        if '/preview-document/' in urlparse(target).path:
            official(target)
            docs[target] = {'titulo': clean(a.get_text(' ', strip=True)), 'url': target,
                            'inventory_url': url}
    return list(docs.values())


def base_record(key, title, url, kind):
    return {'id': 'jun-' + hashlib.sha256(key.encode()).hexdigest()[:20],
            'municipio': 'Jun', 'codigo_ine': '18111', 'provincia': 'Granada',
            'titulo': title, 'tipo': kind, 'url': url, 'source': 'ayuntamiento',
            'publication_ready': False, 'geometry_status': 'unavailable'}


def parse_board(html, url=BOARD):
    _, table = checked_soup(html, 'table.AdvertisementBoardListPanel')
    rows = {}
    for tr in table.select('tbody tr'):
        def cell(name):
            td = tr.select_one('td.class_' + name)
            return clean(td.get_text(' ', strip=True)) if td else ''
        description = cell('description')
        # Approval of a named physical works project, not a procurement notice.
        match = re.search(r'APROBACI[ÓO]N (?:DEFINITIVA|INICIAL) DEL PROYECTO\s+(.+)', description, re.I)
        if not match or not re.search(r'\b(MEJORA|PAVIMENTACI[ÓO]N|CONSTRUCCI[ÓO]N|URBANIZACI[ÓO]N|REHABILITACI[ÓO]N)\b', match[1], re.I):
            continue
        docs = documents(tr, url)
        expediente = cell('folderCode')
        if not docs or not expediente:
            raise ValueError('Approval notice lacks document or expediente')
        date = datetime.strptime(cell('dateFrom'), '%d/%m/%Y').date().isoformat()
        title = clean(match[1]).strip('“”" ')
        # Project code identifies the instrument independently of the notice UUID.
        code = re.search(r'\b\d{4}/\d+/[A-Z]+/\d+-\d+\b', title)
        key = code[0] if code else expediente + ':' + title.casefold()
        if key not in rows:
            row = base_record('works:' + key, title, docs[0]['url'], 'proyecto_obra_publica')
            row.update(inventory_url=url, expediente=expediente,
                       descripcion=description, fecha_publicacion=date,
                       origen='tablon_anuncio_aprobacion_proyecto', documentos=[])
            rows[key] = row
        for doc in docs:
            doc.update(fecha_publicacion=date, descripcion=description)
            if doc['url'] not in {d['url'] for d in rows[key]['documentos']}:
                rows[key]['documentos'].append(doc)
    return list(rows.values())


def planning_folders(html, url=PLANNING):
    _, table = checked_soup(html, 'table.TransparencyListPanel')
    folders = []
    for a in table.select('a[onclick]'):
        title = clean(a.get_text(' ', strip=True))
        if not re.search(r'\b(INNOVACI[ÓO]N|MODIFICACI[ÓO]N|PLAN GENERAL|PLAN PARCIAL|PLAN ESPECIAL|ESTUDIO DE DETALLE)\b', title, re.I):
            continue
        callback = re.search(r"wicketAjaxGet\('([^']+)'", a['onclick'])
        count = re.search(r'\(\s*(\d+)\s*\)\s*$', title)
        if not callback or not count:
            raise ValueError('Planning folder lacks callback or document count')
        title = re.sub(r'^\d+(?:\.\d+)*\.\s*', '', title[:count.start()]).strip(' “')
        folders.append((title, official(urljoin(url, callback[1])), int(count[1])))
    if not folders:
        raise ValueError('No named planning folders found')
    return folders


def parse_instrument(html, url, title, expected_count):
    _, table = checked_soup(html, 'table.TransparencyListPanel')
    docs = documents(table, url)
    if not docs or len(docs) != expected_count:
        raise ValueError('Planning document count mismatch; possible incomplete inventory')
    row = base_record(url, title, url, 'planeamiento_urbanistico')
    row.update(inventory_url=PLANNING, origen='carpeta_planeamiento', documentos=docs)
    return row


class JunAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'MunicipalInventory/1.0 (public documents)'

            def fetch(url):
                official(url)
                response = session.get(url, timeout=40)
                response.raise_for_status()
                official(response.url)
                source_urls.append(response.url)
                if self.config.get('evidence_dir'):
                    dest = Path(self.config['evidence_dir'])
                    dest.mkdir(parents=True, exist_ok=True)
                    name = hashlib.sha256(response.url.encode()).hexdigest()[:20] + '.html'
                    (dest / name).write_text(response.text, encoding='utf-8')
                return response.text, response.url

            html, url = fetch(PLANNING)
            if '7.1. PLANEAMIENTO URBANÍSTICO' not in BeautifulSoup(html, 'html.parser').get_text(' ', strip=True):
                raise ValueError('Unexpected planning inventory')
            rows = []
            for title, callback, count in planning_folders(html, url):
                content, canonical = fetch(callback)
                if not urlparse(canonical).path.startswith('/transparency/') or urlparse(canonical).query:
                    raise ValueError('Folder did not resolve to stable transparency URL')
                rows.append(parse_instrument(content, canonical, title, count))
            html, url = fetch(BOARD)
            rows.extend(parse_board(html, url))
            for row in rows:
                for doc in row['documentos']:
                    content, _ = fetch(doc['url'])
                    soup = BeautifulSoup(content, 'html.parser')
                    if not soup.select_one('iframe[src*="/preview/pdf/"]'):
                        raise ValueError('Document preview no longer exposes PDF')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'source_urls': list(dict.fromkeys(source_urls)),
                'coverage': 'current_planning_folders_and_board_approval_notices', 'limitations': LIMITATIONS}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full current snapshot, not an append-only historical archive.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
