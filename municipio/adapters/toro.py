"""Toro's municipal-linked PLAU inventory; no licence or geometry inference."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://servicios.jcyl.es/PlanPublica/'
MUNICIPAL_SOURCE = 'https://www.toroayto.es/urbanismo.php'
SOURCE = BASE + 'searchVPubDocMuniPlau.do?' + urlencode({
    'bInfoPublica': 'N', 'pager.sortname': 'fPublicacion',
    'pager.sortindex': '-3', 'provincia': '49', 'municipio': '219'})
LIMITATIONS = [
    'Archivo PLAU vigente enlazado por el Ayuntamiento; no incluye históricos ni información pública en trámite.',
    'Se excluyen sentencias y convenios; no es un inventario completo de obras municipales ni de licencias.',
    'Las fechas son publicación y acuerdo del inventario, no concesión de licencia ni aprobación inferida.',
    'Se conservan enlaces y nombres de ficheros; no se interpreta el contenido de todos los PDF ni se certifica vigencia jurídica.',
    'Sin geometría verificada; los registros no están preparados para publicación.',
]


def endpoint(action, key, value):
    return BASE + action + '?' + urlencode({key: value})


def canonical(url):
    return re.sub(r';jsessionid=[^?/#]+', '', url)


def parse_inventory(html):
    """Parse all rows, including excluded kinds, so pagination counts are auditable."""
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    match = re.search(r'Mostrando resultados\s+(\d+)-(\d+)\s+de\s+(\d+)', text)
    if not match:
        raise ValueError('Missing PLAU result count')
    start, end, total = map(int, match.groups())
    entries = []
    for tr in soup.select('table.cuadroAplicacion tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells:
            continue
        if len(cells) != 6:
            raise ValueError('Unexpected inventory row structure')
        call = tr.select_one('[onclick*="doGoBoletin"]')
        ident = re.search(r"doGoBoletin\('(\d+)',\s*'(49219-[^']+)'\)", call.get('onclick', '')) if call else None
        if not ident:
            raise ValueError('Missing Toro document identity')
        values = [c.get_text(' ', strip=True) for c in cells]
        def date(value):
            return datetime.strptime(value, '%d/%m/%Y').date().isoformat() if value else None
        files = tr.select_one('a[href*="ldoc_files.do"]')
        entries.append({
            'plau_id': ident[1], 'codigo_documento': ident[2],
            'libro': values[0], 'instrumento': values[1],
            'fecha_publicacion': date(values[2]), 'fecha_acuerdo': date(values[3]),
            'titulo': values[4],
            'url': endpoint('openBoletinDoc.do', 'cDocId', ident[1]),
            'files_url': canonical(urljoin(BASE, files['href'])) if files else None,
        })
    if len(entries) != end - start + 1 or not (1 <= start <= end <= total):
        raise ValueError('Inventory range does not match parsed rows')
    return entries, (start, end, total)


def parse_files(html, source_url):
    soup = BeautifulSoup(html, 'html.parser')
    if not re.search(r'Toro\s*\(Zamora\s*\)', soup.get_text(' ', strip=True)):
        raise ValueError('File list is not identified as Toro (Zamora)')
    docs = {}
    for a in soup.select('a[href*="openFichero.do"]'):
        url = canonical(urljoin(source_url, a['href']))
        if urlparse(url).hostname != 'servicios.jcyl.es':
            raise ValueError('Unexpected file host')
        cells = a.find_parent('tr').find_all('td', recursive=False)
        title = cells[0].get_text(' ', strip=True)
        if not title:
            raise ValueError('Missing file name')
        docs[url] = {'titulo': title, 'url': url, 'inventory_url': source_url}
    # The current file lists have no pager; reject changes rather than truncate.
    if soup.select('[onclick*="pager.offset"], a[href*="pager.offset"], .rnavLink'):
        raise ValueError('File inventory became paginated')
    if not docs:
        raise ValueError('Empty document file list')
    return list(docs.values())


def instrument_key(entry):
    title = unicodedata.normalize('NFKD', entry['titulo']).encode('ascii', 'ignore').decode().upper()
    title = re.sub(r'\bN\.?O\b', 'N', title)
    title = re.sub(r'^CORRECCION DE ERRORES DE LA ', '', title)
    # Observed original and correction differ only in punctuation/spacing (N.º / Nº).
    title = re.sub(r'[^A-Z0-9]+', ' ', title).strip()
    return (entry['instrumento'], entry['fecha_acuerdo'], title)


def group_instruments(entries):
    selected = [e for e in entries if e['libro'] in {'PU', 'GU', 'OT'}
                and not e['titulo'].upper().startswith('SENTENCIA')]
    groups = {}
    for entry in selected:
        groups.setdefault(instrument_key(entry), []).append(entry)
    rows = []
    for key, members in groups.items():
        members.sort(key=lambda e: (e['fecha_publicacion'] or '', e['plau_id']))
        first = members[0]
        if first['titulo'].upper().startswith('CORRECCIÓN DE ERRORES'):
            raise ValueError('Correction without matching instrument; review grouping')
        documents = {}
        for member in members:
            for doc in member.get('documentos', []):
                documents.setdefault(doc['url'], doc)
        rows.append({
            'id': 'toro-plau-' + hashlib.sha256('|'.join(str(v) for v in key).encode()).hexdigest()[:16],
            'municipio': 'Toro', 'provincia': 'Zamora', 'codigo_ine': '49219',
            'titulo': first['titulo'], 'tipo': 'instrumento_urbanistico',
            'instrumento': first['instrumento'], 'url': first['url'],
            'id_origen': first['plau_id'], 'source_entity_type': 'documento',
            'fecha_publicacion': first['fecha_publicacion'], 'fecha_acuerdo': first['fecha_acuerdo'],
            'source': 'ayuntamiento', 'organismo_fuente': 'Junta de Castilla y León — PLAU',
            'origen': 'archivo_planeamiento_vigente', 'inventory_url': SOURCE,
            'municipal_source_url': MUNICIPAL_SOURCE,
            'publicaciones': members, 'documentos': list(documents.values()),
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    if not rows:
        raise ValueError('No usable Toro instruments')
    return rows


class ToroAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(url, timeout=45)
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(url).hostname:
            raise ValueError('Unexpected source redirect')
        self.source_urls.append(url)
        evidence = self.config.get('evidence_dir')
        if evidence:
            directory = Path(evidence)
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
            (directory / name).write_bytes(response.content)
            self.captures[url] = name
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        self.source_urls, self.captures = [], {}
        with requests.Session() as session:
            session.headers.update({'User-Agent': 'municipio-toro-inventory/1.0'})
            municipal = BeautifulSoup(self._fetch(session, MUNICIPAL_SOURCE), 'html.parser')
            linked = [parse_qs(urlparse(a['href']).query) for a in municipal.select('a[href]')
                      if urlparse(a['href']).hostname == 'servicios.jcyl.es'
                      and 'searchVPubDocMuniPlau.do' in a['href']]
            if not any(q.get('provincia') == ['49'] and q.get('municipio') == ['219'] for q in linked):
                raise ValueError('Municipal link to Toro PLAU inventory missing')
            entries, offset, expected_total = [], 0, None
            seen = set()
            while True:
                url = SOURCE if offset == 0 else SOURCE + '&' + urlencode({'pager.offset': offset, 'pager.size': 15, 'pager.reload': 'no'})
                html = self._fetch(session, url)
                if offset == 0 and not re.search(r'Código INE:\s*49219\b', BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)):
                    raise ValueError('Wrong municipality inventory')
                page, (start, end, total) = parse_inventory(html)
                if start != offset + 1 or (expected_total is not None and total != expected_total):
                    raise ValueError('Pagination changed or page repeated')
                expected_total = total
                for entry in page:
                    if entry['plau_id'] in seen:
                        raise ValueError('Duplicate document across pages')
                    seen.add(entry['plau_id'])
                entries.extend(page)
                if end == total:
                    break
                offset = end
            if len(entries) != expected_total:
                raise ValueError('Incomplete inventory')
            for entry in entries:
                if entry['libro'] not in {'PU', 'GU', 'OT'} or entry['titulo'].upper().startswith('SENTENCIA'):
                    continue
                entry['documentos'] = parse_files(self._fetch(session, entry['files_url']), entry['files_url']) if entry['files_url'] else []
            rows = group_instruments(entries)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(output)
        return {'count': len(rows), 'written': len(rows), 'inventory_entries': len(entries),
                'excluded_entries': len(entries) - sum(len(r['publicaciones']) for r in rows),
                'source_urls': self.source_urls, 'captures': self.captures,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        """Refresh the entire current inventory; never use a date watermark."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
