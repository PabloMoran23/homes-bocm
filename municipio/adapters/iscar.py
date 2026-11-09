"""Íscar's current PLAU inventory, linked by the municipal urbanism page."""
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

MUNICIPAL_URL = 'https://www.villadeiscar.es/areas/urbanismo-servicios-seguridad-ciudadana/urbanismo-2/'
ROOT = 'https://servicios.jcyl.es/PlanPublica/'
INVENTORY_URL = ROOT + 'lplanes.plau?municipio=470750001'
LIMITATIONS = [
    'Only the current PLAU inventory linked by the municipality; historical filter excluded.',
    'Not a complete inventory of municipal works, pending applications or granted licences.',
    'Dates are PLAU publication and agreement fields; no inferred approval date or geometry.',
    'Document metadata and links retained; PDF contents are not parsed by the adapter.',
    'The 2008 study links to a daily BOCYL index, not an individual act; never used to merge instruments.',
    'Updates replace the complete current snapshot; no incremental deletion history.',
]


def canonical_url(href, base=ROOT):
    parts = urlsplit(urljoin(base, href))
    if parts.hostname != 'servicios.jcyl.es' or not parts.path.startswith('/PlanPublica/'):
        raise ValueError('Unexpected PLAU document origin')
    return urlunsplit(('https', parts.netloc, re.sub(r';jsessionid=[^/?;]+', '', parts.path), parts.query, ''))


def guard_pagination(soup):
    # These listings currently have no page navigation (sorting links are allowed).
    # Refuse unfamiliar pagination rather than returning a partial inventory.
    for a in soup.select('a[href]'):
        text = a.get_text(' ', strip=True).lower()
        if text in {'siguiente', 'next', 'última', 'ultima', '>', '>>'} or a.get('rel') == ['next']:
            raise ValueError('PLAU pagination detected; refusing partial extraction')
        controls = a.get('href', '') + ' ' + a.get('onclick', '')
        if any(int(n) > 0 for n in re.findall(r'pager\.offset[=:%]+(\d+)', controls)):
            raise ValueError('PLAU pagination detected; refusing partial extraction')


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    if not re.search(r'Código INE:\s*47075\b', soup.get_text(' ', strip=True)):
        raise ValueError('Missing Íscar municipality identity (47075)')
    guard_pagination(soup)
    rows = []
    for tr in soup.select('table.cuadroAplicacion tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 6:
            continue
        link = tr.select_one('a[href*="ldoc_files.do"]')
        if not link:
            raise ValueError('Inventory row missing document listing')
        values = [c.get_text(' ', strip=True) for c in cells]
        if values[0] != 'PU' or values[1] not in {'NUM', 'PP', 'ED', 'PE', 'PGOU'}:
            raise ValueError('New instrument category requires review')
        url = canonical_url(link['href'])
        doc_id = parse_qs(urlsplit(url).query)['cDocId'][0]
        if not doc_id.isdigit() or not values[4]:
            raise ValueError('Invalid instrument identity')
        rows.append({
            'source_id': doc_id, 'titulo': values[4], 'instrumento': values[1],
            'fecha_publicacion': datetime.strptime(values[2], '%d/%m/%Y').date().isoformat(),
            'fecha_acuerdo': datetime.strptime(values[3], '%d/%m/%Y').date().isoformat(),
            'url': url,
        })
    if not rows:
        raise ValueError('No current planning instruments found')
    # The observed server page size is 15; even absent navigation, a full page is ambiguous.
    if len(rows) >= 15:
        raise ValueError('PLAU page is full; pagination must be reviewed before extraction')
    if len({r['source_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate source identity')
    return rows


def parse_documents(html):
    soup = BeautifulSoup(html, 'html.parser')
    guard_pagination(soup)
    text = soup.get_text(' ', strip=True)
    if not re.search(r'Íscar\s*\(Valladolid\s*\)', text):
        raise ValueError('Wrong municipality in document listing')
    docs = {}
    for a in soup.select('a[href*="openFichero.do"]'):
        tr = a.find_parent('tr')
        name = tr.find('td').get_text(' ', strip=True) if tr else ''
        if not name:
            raise ValueError('Unnamed source document')
        url = canonical_url(a['href'])
        docs[url] = {'titulo': name, 'url': url}
    if not docs:
        raise ValueError('Instrument has no source documents')
    return list(docs.values())


def group_instruments(entries):
    """Same bulletin, agreement and figure identify duplicate archival packages."""
    groups = {}
    for entry in entries:
        bulletin_identity = entry['boletin_url']
        if urlsplit(bulletin_identity).path.endswith('/boletin.do'):
            bulletin_identity += '|source_id=' + entry['source_id']
        key = (bulletin_identity, entry['fecha_acuerdo'], entry['instrumento'])
        if key not in groups:
            digest = hashlib.sha256('|'.join(key).encode()).hexdigest()[:20]
            groups[key] = {
                'id': 'iscar-plan-' + digest, 'municipio': 'Íscar', 'provincia': 'Valladolid',
                'codigo_ine': '47075', 'titulo': entry['titulo'],
                'tipo': 'planeamiento_urbanistico', 'instrumento': entry['instrumento'],
                'fecha_publicacion': entry['fecha_publicacion'], 'fecha_acuerdo': entry['fecha_acuerdo'],
                'url': entry['url'], 'inventory_url': INVENTORY_URL,
                'municipal_source_url': MUNICIPAL_URL, 'source': 'ayuntamiento',
                'organismo_fuente': 'Junta de Castilla y León — Archivo PLAU',
                'origen': 'inventario_planeamiento_actual', 'boletin_url': entry['boletin_url'],
                'publication_ready': False, 'geometry_status': 'unavailable',
                'entradas_fuente': [], 'documentos': [],
            }
        row = groups[key]
        if row['fecha_publicacion'] != entry['fecha_publicacion']:
            raise ValueError('Conflicting publication dates for shared instrument')
        row['entradas_fuente'].append({k: v for k, v in entry.items() if k != 'documentos'})
        known = {d['url'] for d in row['documentos']}
        row['documentos'].extend(d for d in entry['documentos'] if d['url'] not in known)
    return list(groups.values())


class IscarAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('evidence_dir')
        evidence = Path(captures) if captures else None
        if evidence:
            evidence.mkdir(parents=True, exist_ok=True)
        sources = [MUNICIPAL_URL, INVENTORY_URL]
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-iscar/1.0 (public planning inventory)'

            def fetch(url, name):
                response = session.get(url, timeout=45)
                response.raise_for_status()
                canonical_url(response.url)
                if evidence:
                    (evidence / name).write_bytes(response.content)
                return response.text

            entries = parse_inventory(fetch(INVENTORY_URL, 'inventory.html'))
            for entry in entries:
                entry['documentos'] = parse_documents(fetch(entry['url'], 'documents-' + entry['source_id'] + '.html'))
                sources.append(entry['url'])
                url = ROOT + 'openBoletinDoc.do?cDocId=' + entry['source_id']
                # Resolve the official bulletin identity without downloading every PDF.
                with session.get(url, timeout=45, stream=True) as response:
                    response.raise_for_status()
                    parts = urlsplit(response.url)
                    if parts.scheme != 'https' or parts.hostname != 'bocyl.jcyl.es':
                        raise ValueError('Bulletin did not resolve to official BOCYL')
                    if not (parts.path.endswith('.pdf') or re.fullmatch(r'/html/\d{4}/\d{2}/\d{2}/html/BOCYL-[^/]+\.do', parts.path) or parts.path == '/boletin.do'):
                        raise ValueError('Unrecognized BOCYL bulletin endpoint')
                    entry['boletin_url'] = response.url
                    entry['boletin_alcance'] = 'indice_diario' if parts.path == '/boletin.do' else 'acto_individual'
                sources.extend([url, entry['boletin_url']])
        rows = group_instruments(entries)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(output)
        return {'count': len(rows), 'written': len(rows), 'source_entries': len(entries),
                'source_urls': list(dict.fromkeys(sources)), 'limitations': LIMITATIONS,
                'coverage': 'current_plau_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
