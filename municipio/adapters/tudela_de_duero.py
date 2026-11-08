"""Tudela de Duero: municipal-linked JCyL planning inventory, full snapshot."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://servicios.jcyl.es/PlanPublica/'
SOURCE = BASE + ('searchVPubDocMuniPlau.do?bInfoPublica=N&pager.sortname=fPublicacion'
                 '&pager.sortindex=-3&provincia=47&municipio=175')
MUNICIPAL = 'https://tudeladeduero.ayuntamientosdevalladolid.es/'
LIMITATIONS = [
    'Partial coverage: JCyL current-view planning inventory only; historical toggle, licences and public works registers excluded.',
    'Inventory presence does not establish legal validity, approval phase or execution; PGOU has linked later legal events.',
    'Dates are publication/agreement fields, never inferred approval dates; January 1 legacy values retained only as raw text.',
    'Some inventory entries have no downloadable documents; linked PDF contents and geometries are not parsed.',
]


def clean_url(href):
    parts = urlsplit(urljoin(BASE, href))
    if parts.scheme != 'https' or parts.netloc != 'servicios.jcyl.es' or not parts.path.startswith('/PlanPublica/'):
        raise ValueError('Unexpected source URL')
    return urlunsplit((parts.scheme, parts.netloc, re.sub(r';jsessionid=[^/?;]+', '', parts.path), parts.query, ''))


def date_value(raw):
    if not raw or raw.startswith('01/01/'):
        return None
    return datetime.strptime(raw, '%d/%m/%Y').date().isoformat()


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    if not re.search(r'C[oó]digo INE:\s*47175\b', text) or 'TUDELA DE DUERO' not in text:
        raise ValueError('Wrong or missing municipality identity')
    count = re.search(r'Mostrando resultados\s+(\d+)-(\d+)\s+de\s+(\d+)', text)
    table = soup.select_one('table.cuadroAplicacion')
    if not table or not count:
        raise ValueError('Missing inventory or pagination totals')
    entries = []
    for tr in table.select('tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells:
            continue
        if len(cells) != 6:
            raise ValueError('Changed inventory columns')
        book, code, pub, agreement, title = [c.get_text(' ', strip=True) for c in cells[:5]]
        ids = set(re.findall(r'(?:cDocId=|doGoBoletin\(\x27|doOpen\(\x27)(\d+)', str(tr)))
        if len(ids) > 1 or not title:
            raise ValueError('Ambiguous inventory entry')
        doc_id = next(iter(ids), None)
        entries.append({'book': book, 'code': code, 'titulo': title, 'doc_id': doc_id,
                        'fecha_publicacion_raw': pub, 'fecha_acuerdo_raw': agreement,
                        'fecha_publicacion': date_value(pub), 'fecha_acuerdo': date_value(agreement),
                        'files_url': BASE + 'ldoc_files.do?cDocId=' + doc_id if doc_id and tr.select('a[href*="ldoc_files.do"]') else None,
                        'boletin_url': BASE + 'openBoletinDoc.do?cDocId=' + doc_id if doc_id and tr.select('a[onclick*="doGoBoletin"]') else None})
    start, end, total = map(int, count.groups())
    if end - start + 1 != len(entries):
        raise ValueError('Inventory row count disagrees with pagination')
    return entries, (start, end, total)


def parse_files(html):
    soup = BeautifulSoup(html, 'html.parser')
    if 'Tudela de Duero' not in soup.get_text(' ', strip=True):
        raise ValueError('Wrong document municipality')
    files = {}
    for tr in soup.select('table.cuadroAplicacion tr'):
        a = tr.select_one('a[href*="openFichero.do"]')
        if a:
            cells = tr.find_all('td')
            url = clean_url(a['href'])
            if not parse_qs(urlsplit(url).query).get('cFicheroId'):
                raise ValueError('Missing file identifier')
            files[url] = {'nombre': cells[0].get_text(' ', strip=True), 'url': url}
    if not files:
        raise ValueError('Advertised file listing has no files')
    # No file-list pagination observed. Fail instead of dropping new pages.
    if re.search(r'pager\.offset|Mostrando resultados', html):
        raise ValueError('File listing pagination needs review')
    return list(files.values())


def build_records(entries):
    records, legal_events = [], []
    for item in entries:
        title = item['titulo']
        if item['code'] == 'PGOU' and re.match(r'^(SENTENCIA|CORRECCI[ÓO]N DE ERRORES NO ADMITIDA)', title, re.I):
            legal_events.append(item)
            continue
        if item['book'] not in ('PU', 'GU'):
            continue
        if not re.match(r'^(PLAN |PP\b|PERI\b|ESTUDIO DE DETALLE|PROYECTO DE |MODIFICACI[ÓO]N (?:DEL |DE ))', title, re.I):
            continue
        key = item['doc_id'] or hashlib.sha256((item['code'] + ':' + title).encode()).hexdigest()[:16]
        records.append({
            'id': 'tudela-de-duero-plau-' + key,
            'municipio': 'Tudela de Duero', 'provincia': 'Valladolid', 'codigo_ine': '47175',
            'titulo': title, 'tipo': item['code'], 'source': 'jcyl',
            'origen': 'archivo_planeamiento_municipal', 'inventory_url': SOURCE,
            'source_entity_type': 'documento',
            'municipal_source_url': MUNICIPAL,
            'url': item['files_url'] or item['boletin_url'] or SOURCE,
            'source_document_id': item['doc_id'],
            'fecha_publicacion': item['fecha_publicacion'], 'fecha_acuerdo': item['fecha_acuerdo'],
            'fecha_publicacion_raw': item['fecha_publicacion_raw'], 'fecha_acuerdo_raw': item['fecha_acuerdo_raw'],
            'documentos': item.get('documentos', []), 'boletin_url': item['boletin_url'],
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False, 'coverage': 'current_inventory_without_historical_toggle',
        })
    pgou = [r for r in records if r['tipo'] == 'PGOU']
    if legal_events:
        if len(pgou) != 1:
            raise ValueError('Cannot associate later PGOU legal events unambiguously')
        pgou[0]['eventos_relacionados'] = legal_events
    if not records or len({r['id'] for r in records}) != len(records):
        raise ValueError('Empty inventory or duplicate instruments')
    return records


class TudelaDeDueroAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, capture):
        url = clean_url(url)
        response = session.get(url, timeout=45)
        response.raise_for_status()
        clean_url(response.url)
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected HTML source')
        html = response.text
        self.source_urls.append(url)
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / capture).write_text(html, encoding='utf-8')
        return html

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls = []
        entries, seen, offset, expected = [], set(), 0, None
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-tudela-de-duero/1.0'
            while True:
                html = self._fetch(session, SOURCE + f'&pager.size=15&pager.offset={offset}', f'inventory-{offset}.html')
                page, (start, end, total) = parse_inventory(html)
                if start != offset + 1 or (expected is not None and total != expected):
                    raise ValueError('Pagination repeated, skipped or changed during extraction')
                expected = total
                for entry in page:
                    identity = entry['doc_id'] or (entry['code'], entry['titulo'])
                    if identity in seen:
                        raise ValueError('Duplicate across inventory pages')
                    seen.add(identity)
                entries.extend(page)
                if end == total:
                    break
                if end >= total or not page:
                    raise ValueError('Invalid pagination boundary')
                offset = end
            for entry in entries:
                if entry['book'] in ('PU', 'GU') and entry['files_url']:
                    html = self._fetch(session, entry['files_url'], f'files-{entry["doc_id"]}.html')
                    entry['documentos'] = parse_files(html)
        rows = build_records(entries)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'count': len(rows), 'written': len(rows), 'inventory_entries': len(entries),
                'source_urls': self.source_urls, 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
