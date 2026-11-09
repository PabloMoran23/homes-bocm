"""La Lastrilla's municipal inventory in the official Castilla y León PLAU.

One record per archive instrument, with all its file links. This is a current
archive snapshot, not a complete municipal works or granted-licence register.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://servicios.jcyl.es/PlanPublica/'
SOURCE = BASE + 'searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=112'
LIMITATIONS = [
    'Partial coverage: PLAU municipal planning and land-management inventory only; '
    'excludes CU agreements, OT regional instruments, judicial notices, PLAI, licences and other public works.',
    'Dates transcribed from PLAU publication/agreement columns; not independently verified against gazette PDFs. '
    'An agreement date is not asserted to be an approval date.',
    'Archive listing does not establish current legal validity; judicial notices are excluded from project records.',
    'Some inventory entries have no technical files; their archive bulletin resolver is retained, not guaranteed available.',
    'No verified project coordinates or geometries; no municipal-centroid substitution.',
]


def _text(node):
    return node.get_text(' ', strip=True)


def _canonical(href, base=BASE):
    url = re.sub(r';jsessionid=[^?/#]+', '', urljoin(base, href), flags=re.I)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'servicios.jcyl.es' or not parsed.path.startswith('/PlanPublica/'):
        raise ValueError('Unexpected archive URL: ' + url)
    return url


def _date(text):
    return datetime.strptime(text, '%d/%m/%Y').date().isoformat() if text else None


def parse_inventory(html, *, first_page=False):
    soup = BeautifulSoup(html, 'html.parser')
    text = _text(soup)
    if first_page and not re.search(r'LASTRILLA\s*\(LA\).*?Código INE:\s*40112', text, re.S):
        raise ValueError('Inventory is not La Lastrilla, INE 40112')
    tables = [t for t in soup.select('table.cuadroAplicacion')
              if [_text(h) for h in t.select('th')][:5] ==
              ['Libro', 'Instrumento', 'Fecha de publicación', 'Fecha de acuerdo', 'Título']]
    if len(tables) != 1:
        raise ValueError('Changed PLAU inventory columns')
    match = re.search(r'Mostrando resultados\s+(\d+)-(\d+)\s+de\s+(\d+)', text)
    if not match:
        raise ValueError('Missing inventory result count')
    start, end, total = map(int, match.groups())
    entries = []
    for tr in tables[0].select('tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells:
            continue
        if len(cells) != 6:
            raise ValueError('Changed inventory row')
        book, kind, published, agreement, title = [_text(c) for c in cells[:5]]
        identity = re.search(r"doGoBoletin\('(\d+)',\s*'([0-9]{5}-[^']+)'\)", str(cells[2]))
        if not identity:
            raise ValueError('Missing municipal document identity')
        doc_id, archive_code = identity.groups()
        if book != 'OT' and not archive_code.startswith('40112-'):
            raise ValueError('Document belongs to another municipality')
        files = cells[5].select_one('a[href*="ldoc_files.do"]')
        no_files = cells[5].select_one('img[alt="No hay documentos"]')
        if not files and not no_files:
            raise ValueError('Unknown document availability')
        entries.append({
            'doc_id': doc_id, 'archive_code': archive_code, 'book': book,
            'kind': kind, 'title': title, 'published': _date(published),
            'agreement': _date(agreement),
            'files_url': _canonical(files['href']) if files else None,
        })
    if len(entries) != end - start + 1:
        raise ValueError('Inventory row count mismatch')
    next_links = [a for a in soup.select('a[onclick]') if _text(a).startswith('Siguiente')]
    next_url = None
    if end < total:
        if len(next_links) != 1:
            raise ValueError('Missing/ambiguous next page')
        target = re.search(r"unescape\('([^']+)'\)", next_links[0]['onclick'])
        if not target:
            raise ValueError('Unknown next-page action')
        next_url = _canonical(unquote(target[1]))
        params = parse_qs(urlparse(next_url).query)
        if (urlparse(next_url).path != '/PlanPublica/searchVPubDocMuniPlau.do'
                or params.get('municipio') != ['112'] or params.get('provincia') != ['40']
                or params.get('bInfoPublica') != ['N'] or params.get('pager.offset') != [str(end)]):
            raise ValueError('Next page changed municipal scope or offset')
    elif next_links:
        raise ValueError('Unexpected next page after final result')
    return entries, (start, end, total), next_url


def parse_files(html):
    soup = BeautifulSoup(html, 'html.parser')
    if not re.search(r'Lastrilla, La\s*\(Segovia\s*\)', _text(soup)):
        raise ValueError('File list belongs to another municipality')
    docs = {}
    for tr in soup.select('table.cuadroAplicacion tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells:
            continue
        if len(cells) != 2:
            raise ValueError('Changed file-list row')
        a = cells[1].select_one('a[href*="openFichero.do"]')
        if not a or not _text(cells[0]):
            raise ValueError('Missing file link/title')
        url = _canonical(a['href'])
        if not re.fullmatch(r'\d+', parse_qs(urlparse(url).query).get('cFicheroId', [''])[0]):
            raise ValueError('Invalid archive file identifier')
        docs[url] = {'titulo': _text(cells[0]), 'url': url, 'origen': 'PLAU'}
    # File lists currently have no pager. Fail closed if the provider adds one.
    if soup.select('.rnavLink') or re.search(r'Mostrando resultados|Siguiente|Mostrar más', _text(soup), re.I):
        raise ValueError('File-list pagination requires review')
    if not docs:
        raise ValueError('Empty technical file list')
    return list(docs.values())


class LaLastrillaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []

    def _fetch(self, session, url):
        response = session.get(url, timeout=45)
        response.raise_for_status()
        _canonical(response.url)
        self.source_urls.append(url)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:20] + '.html')).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        entries, seen, expected_total, url = [], set(), None, SOURCE
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-la-lastrilla/1.0 (public planning inventory)'
            while url:
                page, (start, end, total), next_url = parse_inventory(
                    self._fetch(session, url), first_page=not entries)
                if start != len(entries) + 1 or (expected_total is not None and total != expected_total):
                    raise ValueError('Inventory changed during pagination')
                expected_total = total
                for entry in page:
                    if entry['doc_id'] in seen:
                        raise ValueError('Repeated inventory document during pagination')
                    seen.add(entry['doc_id'])
                    entries.append(entry)
                url = next_url
            if not entries or len(entries) != expected_total:
                raise ValueError('Incomplete/empty inventory')
            rows, excluded = [], []
            for item in entries:
                if item['book'] not in {'PU', 'GU'} or item['title'].startswith('SENTENCIA'):
                    excluded.append({'archive_id': item['doc_id'], 'titulo': item['title'],
                                     'reason': 'Outside municipal planning/land-management instrument scope'})
                    continue
                if item['kind'] not in {'PP', 'ED', 'NS', 'NUM', 'PE', 'PAU', 'PN'}:
                    raise ValueError('Unreviewed municipal instrument type')
                docs = parse_files(self._fetch(session, item['files_url'])) if item['files_url'] else []
                bulletin = BASE + 'openBoletinDoc.do?cDocId=' + item['doc_id']
                rows.append({
                    'id': 'la-lastrilla-plau-' + item['doc_id'],
                    'municipio': 'La Lastrilla', 'provincia': 'Segovia', 'codigo_ine': '40112',
                    'titulo': item['title'], 'tipo': item['kind'],
                    'fecha': None, 'fecha_publicacion': item['published'],
                    'fecha_acuerdo': item['agreement'], 'fecha_aprob': None,
                    'fase': None, 'url': SOURCE, 'url_documento': item['files_url'] or bulletin,
                    'url_boletin': bulletin, 'source': 'junta_castilla_y_leon',
                    'origen': 'PLAU', 'source_entity_type': 'documento',
                    'archivo_id': item['doc_id'],
                    'archivo_codigo': item['archive_code'], 'documentos': docs,
                    'documentos_status': 'enlazados' if docs else 'sin_ficheros_en_inventario',
                    'fechas_procedencia': 'Columnas Fecha de publicación y Fecha de acuerdo del inventario PLAU',
                    'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                    'geometry_status': 'Sin geometría verificada',
                })
        if not rows:
            raise ValueError('No usable municipal instruments')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_entries': len(entries),
                'excluded': excluded, 'source_urls': self.source_urls, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current snapshot; removals and all pages are reconsidered.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
