"""Moratalla: existing hydraulic public works in the official CH Segura inventory.

This is a partial inventory of physical works, not a licence or new-project feed.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

INVENTORY_URL = 'https://www.chsegura.es/es/cuenca/infraestructuras/embalses/listado-de-embalses/'
HOST = 'www.chsegura.es'
LIMITATIONS = [
    'Cobertura parcial: presas existentes del inventario CH Segura cuya ficha sitúa la presa en Moratalla (Murcia).',
    'No cubre el planeamiento, las obras municipales recientes ni las licencias concedidas.',
    'El Cenajo es compartido con Hellín (Albacete); se conserva la jurisdicción literal de la fuente.',
    'Sin fechas de publicación, acuerdo o aprobación verificadas; el año de construcción no es una fecha de aprobación.',
    'Sin geometría extraída; planos y ortofotos permanecen como documentos enlazados.',
    'Las fichas técnicas describen obras históricas; su disponibilidad actual no prueba actualización de su contenido.',
]


def norm(value):
    return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower().strip()


def official_url(base, href):
    url = urldefrag(urljoin(base, href.strip()))[0]
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != HOST or parsed.username or parsed.password:
        raise ValueError('Unexpected non-official source URL')
    return url


def check_pagination(soup):
    # The current DataTable contains ALL rows in HTML. Do not accept a future
    # server-paginated replacement as a complete snapshot.
    for a in soup.select('a[href]'):
        label = norm(a.get_text(' ', strip=True))
        classes = ' '.join(a.get('class', []))
        if ('next' in a.get('rel', []) or label in {'siguiente', 'next', 'ultima', 'last'}
                or 'paginate_button' in classes or a.find_parent(class_='pagination')):
            if a['href'].strip() not in {'', '#'}:
                raise ValueError('Server pagination detected; inventory coverage requires review')
    if re.search(r'\b(?:serverSide|ajax)\s*["\x27]?\s*:', str(soup)):
        raise ValueError('Remote table data detected; inventory coverage requires review')


def parse_inventory(html, url=INVENTORY_URL):
    soup = BeautifulSoup(html, 'html.parser')
    check_pagination(soup)
    table = soup.select_one('table#sortTable')
    if table is None:
        raise ValueError('Missing official reservoir inventory table')
    headers = [norm(th.get_text(' ', strip=True)) for th in table.select('thead th')]
    if len(headers) != 8 or headers[0] != 'nombre' or headers[6] != 'gestor/propietario':
        raise ValueError('Inventory schema changed')
    entries = {}
    for tr in table.select('tbody > tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 8:
            raise ValueError('Incomplete inventory row')
        a = cells[0].select_one('a[href]')
        if not a or not a.get_text(strip=True):
            raise ValueError('Inventory row lacks named detail link')
        target = official_url(url, a['href'])
        if not urlparse(target).path.startswith('/es/cuenca/infraestructuras/embalses/Embalse-'):
            raise ValueError('Unexpected reservoir detail route')
        entry = {'titulo': a.get_text(' ', strip=True), 'url': target,
                 'uso_inventario': cells[2].get_text(' ', strip=True),
                 'construccion_inventario': cells[3].get_text(' ', strip=True),
                 'gestor_propietario_inventario': cells[6].get_text(' ', strip=True)}
        if target in entries and entries[target] != entry:
            raise ValueError('Conflicting duplicate reservoir')
        entries[target] = entry
    if not entries:
        raise ValueError('Empty reservoir inventory')
    return list(entries.values())


def parse_detail(html, entry):
    soup = BeautifulSoup(html, 'html.parser')
    jurisdiction = {}
    # The inventory uses several table classes (ficha, fichatres, Bootstrap).
    # Exact field labels, rather than a visual class, define the jurisdiction.
    for tr in soup.select('table tr'):
        th, td = tr.find('th'), tr.find('td')
        if th and td:
            label = norm(th.get_text(' ', strip=True))
            if label in {'provincia', 'termino municipal', 'terminos municipales'}:
                key = 'provincia' if label == 'provincia' else 'municipio'
                value = td.get_text(' ', strip=True)
                if key in jurisdiction and jurisdiction[key] != value:
                    raise ValueError('Conflicting jurisdiction in detail')
                jurisdiction[key] = value
    if set(jurisdiction) != {'provincia', 'municipio'}:
        raise ValueError('Detail lacks structured province/municipality; cannot safely filter')
    # A name in narrative text, a menu or the river name never establishes location.
    if not re.search(r'\bmoratalla\b', norm(jurisdiction['municipio'])):
        return None
    if not re.search(r'\bmurcia\b', norm(jurisdiction['provincia'])):
        raise ValueError('Moratalla detail does not establish Murcia province')
    heading = soup.select_one('h2.title-componentes')
    if not heading or norm(heading.get_text(' ', strip=True)) != norm(entry['titulo']):
        raise ValueError('Reservoir detail title mismatch')
    sections = {norm(h.get_text(' ', strip=True)): h.parent for h in soup.select('h3')}
    plans = sections.get('planos')
    documents = {}
    if plans:
        for a in plans.select('a[href]'):
            target = official_url(entry['url'], a['href'])
            if urlparse(target).path.lower().endswith('.pdf'):
                documents[target] = {'titulo': a.get_text(' ', strip=True), 'url': target,
                                     'source_url': entry['url']}
    if not documents:
        raise ValueError('Moratalla work lacks linked technical documents')
    purpose = sections.get('finalidad')
    description = ' '.join(p.get_text(' ', strip=True) for p in purpose.select('p')
                           if p.get_text(strip=True) and not p.find('img')) if purpose else ''
    row = {'id': 'moratalla-chs-' + hashlib.sha256(entry['url'].encode()).hexdigest()[:16],
           **entry, 'municipio': 'Moratalla', 'codigo_ine': '30028', 'provincia': 'Murcia',
           'tipo': 'obra_publica_hidraulica', 'naturaleza': 'infraestructura existente',
           'source': 'confederacion_hidrografica_del_segura', 'origen': 'inventario_oficial_embalses',
           'inventory_url': INVENTORY_URL, 'situacion_fuente': jurisdiction,
           'documentos': list(documents.values()), 'publication_ready': False,
           'geometry_status': 'unavailable'}
    if description:
        row['descripcion'] = description
        row['descripcion_source_section'] = 'Finalidad'
    return row


class MoratallaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get('evidence_dir')
        capture_dir = Path(captures) if captures else None
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
        sources = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-moratalla/1.0 (public infrastructure inventory)'

            def fetch(url):
                response = session.get(url, timeout=(15, 45))
                response.raise_for_status()
                official_url(url, response.url)
                if 'html' not in response.headers.get('Content-Type', '').lower():
                    raise ValueError('Expected HTML inventory/detail')
                sources.append(response.url)
                if capture_dir:
                    name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
                    (capture_dir / name).write_bytes(response.content)
                # CHS declares UTF-8 inside HTML; HTTP may default to Latin-1.
                # Let BeautifulSoup inspect the original bytes and charset meta.
                return response.content

            entries = parse_inventory(fetch(INVENTORY_URL))
            rows = []
            for entry in entries:
                time.sleep(.15)
                row = parse_detail(fetch(entry['url']), entry)
                if row:
                    rows.append(row)
        if not rows:
            raise ValueError('No verified Moratalla public works in live inventory')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'inventory_entries': len(entries),
                'details_checked': len(entries), 'excluded_other_municipalities': len(entries) - len(rows),
                'source_urls': sources, 'limitations': LIMITATIONS,
                'coverage': 'existing_hydraulic_public_works', 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Re-read the complete current inventory; no artificial incremental cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
