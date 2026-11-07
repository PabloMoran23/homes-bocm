"""Bailén's municipal-linked PGOU archive: documentary coverage, not licences."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://pgoubailen.es/index.html'
AUTHORITY = 'https://ayto-bailen.com/urbanismo/'


def clean(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def documents(node, url):
    found = {}
    for a in node.select('a[href]'):
        target = urljoin(url, a['href'])
        if urlsplit(target).hostname not in ('pgoubailen.es', 'www.pgoubailen.es'):
            continue
        if not re.search(r'\.(pdf|zip)$', urlsplit(target).path, re.I):
            continue
        found.setdefault(target, {'titulo': clean(a), 'url': target, 'inventory_url': url})
    return list(found.values())


def record(title, docs, url, narrative=''):
    if not title or not docs:
        raise ValueError('Instrument without title or documents: ' + url)
    row = {
        'id': 'bailen-plan-' + hashlib.sha256((url + '#' + title).encode()).hexdigest()[:16],
        'municipio': 'Bailén', 'provincia': 'Jaén', 'codigo_ine': '23010',
        'titulo': title, 'tipo': 'instrumento de planeamiento urbanístico',
        'url': url, 'inventory_url': url, 'authority_url': AUTHORITY,
        'documentos': docs, 'source': 'ayuntamiento', 'origen': 'archivo_pgou_municipal',
        'publication_ready': False, 'geometry_status': 'unavailable',
        'coverage': 'Archivo documental parcial; no acredita vigencia actual ni licencia concedida',
    }
    # Only an explicit agreement date; no inference from CMS or document filenames.
    match = re.search(r'Aprobación inicial:\s*Sesión plenaria de fecha (\d{2}-\d{2}-\d{4})', narrative)
    if match:
        row['fase'] = 'aprobación inicial'
        row['fecha_acuerdo'] = datetime.strptime(match[1], '%d-%m-%Y').date().isoformat()
        row['fecha_acuerdo_texto'] = match[0]
    if narrative:
        row['descripcion'] = narrative
    return row


def parse_inventory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('div.content')
    heading = content.find('h2') if content else None
    if not heading:
        raise ValueError('Missing planning inventory content: ' + url)
    title = clean(heading)
    rows = []
    if title in ('P.G.O.U.', 'Adaptación Parcial a la L.O.U.A.'):
        rows.append(record(title + ' — Bailén', documents(content, url), url))
    elif title == 'Revisiones del P.G.O.U.':
        for h in content.find_all('h3'):
            name = re.sub(r'^\d+\.\s*', '', clean(h))
            if not name:
                continue
            if not name.startswith('Revisión'):
                raise ValueError('Unrecognized revision heading: ' + name)
            fragment = BeautifulSoup('', 'html.parser')
            for sibling in h.next_siblings:
                if getattr(sibling, 'name', None) == 'h3':
                    break
                fragment.append(BeautifulSoup(str(sibling), 'html.parser'))
            rows.append(record(name, documents(fragment, url), url, clean(fragment)))
    elif title == 'Modificaciones del P.G.O.U.':
        for li in content.select('li'):
            docs = documents(li, url)
            if not docs:
                continue  # External historical PUA index is not an individual instrument.
            name = clean(li)
            if not name.startswith('Modificación puntual'):
                raise ValueError('Unrecognized modification: ' + name)
            rows.append(record(name, docs, url))
    else:
        raise ValueError('Unrecognized inventory heading: ' + title)
    if not rows:
        raise ValueError('No documented instruments: ' + url)
    # Follow navigation and any HTML continuations/next pages; no page-count cap.
    pages = set()
    for a in soup.select('.nav a[href], .content a[href], a[rel~=next], .pagination a[href]'):
        target = urldefrag(urljoin(url, a['href']))[0]
        parts = urlsplit(target)
        if parts.hostname in ('pgoubailen.es', 'www.pgoubailen.es') and parts.path.endswith('.html'):
            pages.add(target.replace('https://www.pgoubailen.es/', 'https://pgoubailen.es/'))
        elif 'next' in (a.get('rel') or []) or a.find_parent(class_='pagination'):
            raise ValueError('Unsupported pagination link: ' + target)
    return rows, sorted(pages)


class BailenAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        queue, seen, records = [SOURCE], set(), {}
        captures = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-bailen/1.0 (public planning inventory)'
            while queue:
                url = queue.pop(0)
                if url in seen:
                    continue
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if urlsplit(response.url).hostname not in ('pgoubailen.es', 'www.pgoubailen.es'):
                    raise ValueError('Unexpected inventory redirect: ' + response.url)
                # Live pages use UTF-8 BOM despite a stale ISO-8859-1 declaration.
                try:
                    html = response.content.decode('utf-8-sig')
                except UnicodeDecodeError:
                    html = response.content.decode('iso-8859-1')
                rows, pages = parse_inventory(html, url)
                if captures:
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / Path(urlsplit(url).path).name).write_bytes(response.content)
                seen.add(url)
                for row in rows:
                    if row['id'] in records and records[row['id']] != row:
                        raise ValueError('Conflicting instrument identity')
                    records[row['id']] = row
                queue.extend(p for p in pages if p not in seen)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records.values()), encoding='utf-8')
        return {'count': len(records), 'source_urls': sorted(seen), 'coverage': 'partial_current_archive', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
