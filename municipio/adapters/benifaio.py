"""Benifaió's municipal planning instruments in the official GVA register."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

INVENTORY_URL = (
    'https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/'
    '4%20VALENCIA/46060%20BENIFAI%D3/'
)
LIMITATIONS = [
    'Partial coverage: only the GVA deposited planning inventory for INE 46060; '
    'not the municipal noticeboard, pending plans, works or a licence register.',
    'The municipal www.benifaio.es site closed connections during research. '
    'The 2026 modification no. 1 found in DOGV is outside this inventory.',
    'Registry annotations and judgments are retained with the parent instrument; '
    'listing does not establish current legal validity or an execution phase.',
    'No agreement, approval or publication dates are inferred from filenames, '
    'directory timestamps or case years. No coordinates or geometry extracted.',
    'Document links are inventoried; PDF contents are not parsed by this adapter.',
]


def canonical(url):
    return re.sub(r'%[0-9a-fA-F]{2}', lambda m: m[0].upper(), url)


def within(url, root):
    target, base = urlsplit(url), urlsplit(root)
    return (target.scheme == base.scheme and target.netloc == base.netloc
            and target.path.startswith(base.path) and not target.query
            and not target.fragment)


def parse_directory(html: str, url: str):
    """Parse a complete Apache-style register listing, excluding sort/parent links."""
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.find('h1')
    if not heading or not heading.get_text(strip=True).startswith('Index of /auto/urbanismo/reg-planeamiento/'):
        raise ValueError(f'Not a register directory: {url}')
    if soup.select('[rel~=next], .pagination, .pager'):
        raise ValueError(f'Unexpected pagination requires review: {url}')
    links = {}
    for a in soup.select('a[href]'):
        title = a.get_text(' ', strip=True)
        target = canonical(urljoin(url, a['href']))
        if not title or target == canonical(url) or not within(target, canonical(url)):
            continue
        if target.endswith('/') or urlsplit(target).path.lower().endswith(('.pdf', '.zip')):
            links[target] = {'titulo': title.rstrip('/'), 'url': target,
                             'inventory_url': canonical(url)}
        else:
            raise ValueError(f'Unrecognized register entry: {target}')
    if not links:
        raise ValueError(f'Empty register directory: {url}')
    return list(links.values())


def extract_inventory(fetch):
    """Visit all descendant listings; annotations share the numeric instrument ID."""
    pending = [(INVENTORY_URL, None)]
    visited, records = set(), {}
    while pending:
        url, instrument = pending.pop(0)
        if url in visited:
            continue
        visited.add(url)
        for entry in parse_directory(fetch(url), url):
            target = entry['url']
            if target.endswith('/'):
                match = re.match(r'^46060-(\d{4})([A-Z]?)\b', entry['titulo'])
                owner = instrument
                if match:
                    owner = '46060-' + match[1]
                    record = records.setdefault(owner, {
                        'id': 'benifaio-plan-' + owner,
                        'municipio': 'Benifaió', 'codigo_ine': '46060',
                        'provincia': 'Valencia', 'tipo': 'instrumento de planeamiento',
                        'source': 'generalitat_valenciana',
                        'origen': 'registro_autonomico_planeamiento',
                        'inventory_url': INVENTORY_URL, 'documentos': [],
                        'entradas_registro': [], 'publication_ready': False,
                        'geometry_status': 'unavailable',
                    })
                    record['entradas_registro'].append(entry)
                    if not match[2]:
                        record['titulo'] = entry['titulo']
                        record['url'] = target
                pending.append((target, owner))
            elif instrument:
                records[instrument]['documentos'].append(entry)
            else:
                raise ValueError(f'Document outside a named instrument: {target}')
    if not records or any(not r.get('titulo') or not r['documentos'] for r in records.values()):
        raise ValueError('No complete named planning instruments found')
    return list(records.values()), sorted(visited)


class BenifaioAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        captures = []
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture_dir = Path(capture_dir)
            capture_dir.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'

            def fetch(url):
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if canonical(response.url) != canonical(url):
                    raise ValueError(f'Unexpected register redirect: {response.url}')
                # These directory indexes declare ISO-8859-1 (including escaped paths).
                response.encoding = 'iso-8859-1'
                if capture_dir:
                    path = capture_dir / f'listing-{len(captures):03d}.html'
                    path.write_text(response.text, encoding='utf-8')
                    captures.append({'url': response.url, 'capture': str(path)})
                return response.text

            rows, urls = extract_inventory(fetch)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'source_urls': urls,
                'document_count': sum(len(r['documentos']) for r in rows),
                'coverage': 'current_gva_deposited_planning_inventory',
                'limitations': LIMITATIONS, 'captures': captures, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full refresh: this listing has no reliable incremental publication cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
