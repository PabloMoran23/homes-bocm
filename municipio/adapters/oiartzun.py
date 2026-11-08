"""Official Oiartzun general-plan inventories, grouped by planning instrument."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.oiartzun.eus'
GENERAL = BASE + '/eu/Hirigintza/Plangintza_Urbanistikoa:_Plan_Orokorra'
MODIFICATIONS = BASE + '/eu/Hirigintza/Plangintza_Urbanistikoa:_Plan_Orokorraren_aldaketak'
MONTHS = dict(zip('urtarrilaren otsailaren martxoaren apirilaren maiatzaren ekainaren uztailaren abuztuaren irailaren urriaren azaroaren abenduaren'.split(), range(1, 13)))


def canonical(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.hostname != 'www.oiartzun.eus':
        raise ValueError('Unexpected nonmunicipal source: ' + url)
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ''))


def parse_inventory(html, source):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.table tbody')
    if table is None:
        raise ValueError('Missing planning inventory table')
    rows = []
    for tr in table.select('tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 3 or not cells[1].select_one('a[href]'):
            raise ValueError('Changed inventory row structure')
        a = cells[1].select_one('a[href]')
        stamp = date.fromisoformat(cells[0].get_text(strip=True)).isoformat()
        url = canonical(urljoin(source, a['href']))
        if not unquote(urlsplit(url).path).lower().startswith(unquote(urlsplit(source).path).lower() + '/'):
            raise ValueError('Detail outside inventory')
        rows.append({'titulo': a.get_text(' ', strip=True), 'url': url, 'fecha_listado': stamp, 'fuente_listado': source})
    pages = set()
    for a in soup.select('a[href]'):
        url = urljoin(source, a['href'])
        p = urlsplit(url)
        same = unquote(p.path).lower() == unquote(urlsplit(source).path).lower()
        if same and p.query:
            query = parse_qs(p.query)
            if set(query) != {'page'} or len(query['page']) != 1 or not query['page'][0].isdigit():
                raise ValueError('Unsupported inventory pagination')
            pages.add(canonical(url))
    for a in soup.select('.pagination a[href], a[rel="next"]'):
        if urljoin(source, a['href']) not in pages:
            raise ValueError('Unrecognized pagination link')
    if not rows:
        raise ValueError('Empty planning inventory requires review')
    return rows, sorted(pages)


def parse_detail(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.container.content')
    if content is None or not content.select_one('h2'):
        raise ValueError('Missing instrument detail')
    body = content.select_one('.col-md-8')
    if body is None:
        raise ValueError('Missing detail narrative')
    text = body.get_text(' ', strip=True)
    docs = {}
    for a in content.select('a[href]'):
        link = urljoin(url, a['href'])
        external = urlsplit(link).scheme == 'https' and urlsplit(link).hostname == 'drive.google.com' and urlsplit(link).path.startswith(('/file/d/', '/drive/folders/'))
        if '/fitxategiak/erab_2/' in urlsplit(link).path or external:
            link = link if external else canonical(link)
            docs[link] = {'titulo': a.get_text(' ', strip=True), 'url': link, 'url_procedencia': url}
    if not docs:
        raise ValueError('Instrument detail has no source documents')
    agreement = None
    # Parse only an explicit meeting/approval sentence, never a date from a file name.
    paragraphs = list(dict.fromkeys(p.get_text(' ', strip=True) for p in body.select('p'))) or [text]
    for sentence in paragraphs:
        if not re.search(r'osoko bilkuran onartutako|bilkuran.*onarpena.*erabaki', sentence, re.I):
            continue
        match = re.search(r'(\d{4})(?:eko|ko)\s+(\w+)\s+(\d{1,2})(?:eko|ko|an)', sentence)
        if match and match[2].lower() in MONTHS:
            agreement = date(int(match[1]), MONTHS[match[2].lower()], int(match[3])).isoformat()
    publication = re.search(r'Boletinean argitaratua:\s*GAO\s+(\d{4}-\d{2}-\d{2})', text)
    phase = 'aprobacion_inicial' if 'hasierako onarpena' in text.lower() else None
    if 'osoko bilkuran onartutako' in text.lower():
        phase = 'aprobacion'
    return {'descripcion': text, 'documentos': list(docs.values()), 'fecha_acuerdo': agreement,
            'fecha_publicacion': date.fromisoformat(publication[1]).isoformat() if publication else None,
            'fase': phase}


class OiartzunAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-oiartzun/1.0'})
        response.raise_for_status()
        canonical(response.url)
        if len(response.content) > 5_000_000:
            raise ValueError('Oversized HTML response')
        capture = self.config.get('capture_dir')
        if capture:
            folder = Path(capture)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (hashlib.sha256(url.encode()).hexdigest() + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    def _inventory(self, source):
        pending, seen, rows = [source], set(), {}
        while pending:
            url = pending.pop(0)
            if url in seen:
                continue
            if len(seen) >= 100:
                raise ValueError('Pagination exceeds safety bound; no output written')
            seen.add(url)
            entries, pages = parse_inventory(self._fetch(url), source)
            for entry in entries:
                old = rows.get(entry['url'])
                if old and old != entry:
                    raise ValueError('Conflicting duplicate inventory entry')
                rows[entry['url']] = entry
            pending.extend(p for p in pages if p not in seen)
        return list(rows.values()), sorted(seen)

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        groups, sources = {}, []
        for inventory in (GENERAL, MODIFICATIONS):
            entries, pages = self._inventory(inventory)
            sources.extend(pages)
            for entry in entries:
                title = entry['titulo']
                if inventory == GENERAL:
                    if 'antolatzeko plan orokorra' not in title.lower():
                        raise ValueError('Unknown general-plan instrument')
                    key = 'pgou'
                else:
                    number = re.search(r'HAPO.*?(\d+)\.\s*aldaketa', title, re.I)
                    if not number:
                        raise ValueError('Unrecognized modification; cannot safely group documents')
                    key = 'pgou-modificacion-' + number[1]
                detail = parse_detail(self._fetch(entry['url']), entry['url'])
                groups.setdefault(key, []).append({**entry, **detail})
        rows = []
        for key, parts in groups.items():
            agreements = {p['fecha_acuerdo'] for p in parts if p['fecha_acuerdo']}
            publications = {p['fecha_publicacion'] for p in parts if p['fecha_publicacion']}
            if len(agreements) > 1 or len(publications) > 1:
                raise ValueError('Multiple dated stages require explicit modeling')
            docs = {d['url']: d for p in parts for d in p['documentos']}
            rows.append({'id': 'oiartzun-proy-' + key, 'municipio': 'Oiartzun', 'codigo_ine': '20063',
                         'provincia': 'Gipuzkoa', 'titulo': 'Hirigintza Antolatzeko Plan Orokorra (HAPO / PGOU)' if key == 'pgou' else parts[0]['titulo'],
                         'tipo': 'plan_general' if key == 'pgou' else 'modificacion_plan_general',
                         'fase': next((p['fase'] for p in parts if p['fase']), None),
                         'fecha_acuerdo': next(iter(agreements), None),
                         'fecha_publicacion': next(iter(publications), None),
                         'url': GENERAL if key == 'pgou' else parts[0]['url'],
                         'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
                         'descripcion': '\n'.join(p['descripcion'] for p in parts if p['descripcion']),
                         'documentos': list(docs.values()), 'fichas_fuente': parts,
                         'geometry': None, 'lat': None, 'lon': None, 'geometry_status': 'unavailable',
                         'publication_ready': False})
        if not rows:
            raise ValueError('No usable instruments')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources,
                'coverage': 'General plan and published modifications only; development planning excluded'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
