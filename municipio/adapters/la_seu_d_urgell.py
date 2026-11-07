"""Municipal planning inventory snapshot, with documents grouped by detail page."""
from __future__ import annotations

import hashlib
import html as html_module
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://www.laseu.cat/tramits-i-serveis/ordenances-i-normatives/urbanisme'
STARTS = [ROOT + '/' + p for p in (
    'planejament-general', 'planejament-derivat',
    'pla-de-mobilitat-urbana-sostenible-de-la-seu-durgell')]
MOBILITY_SOURCE = STARTS[2]
LIMITATIONS = [
    'Partial municipal coverage: municipal general/derived planning and mobility inventory only; not a complete RPUC, works or licence register.',
    'One record per municipal instrument detail page; embedded amendments and historical versions remain grouped with that page.',
    'Document links and labels are retained; PDF/archive contents and ongoing legal validity are not verified.',
    'Generic page timestamps are not agreement/publication dates. Dates in document labels apply only to that document.',
    'No verified vector geometry or coordinates; publication_ready=false.',
    'The municipality links PGOU modifications 035 and 037 to the same RPUC identifier 291476; retain separate municipal pages, do not merge by that link.',
]
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def explicit_date(text):
    """Only one unambiguous complete date in the visible text; never filenames."""
    values = []
    for m in re.finditer(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', text):
        values.append((int(m[3]), int(m[2]), int(m[1])))
    for m in re.finditer(r'\b(\d{1,2}) de (\w+) de (\d{4})\b', text.lower()):
        if m[2] in MONTHS:
            values.append((int(m[3]), MONTHS[m[2]], int(m[1])))
    try:
        dates = {date(*v).isoformat() for v in values}
    except ValueError:
        return None
    return next(iter(dates)) if len(dates) == 1 else None


def inventory_url(url):
    p = urlsplit(url)
    return p.scheme == 'https' and p.netloc == 'www.laseu.cat' and any(
        p.path == urlsplit(start).path or p.path.startswith(urlsplit(start).path + '/')
        for start in STARTS)


def parse_page(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    core, heading = soup.select_one('#content-core'), soup.select_one('h1.documentFirstHeading, h1')
    if core is None or heading is None:
        raise ValueError(f'Missing municipal content: {url}')
    children, next_pages = [], []
    for a in soup.select('.batching a[href], .pagination a[href], a[rel~=next], .batchNext a[href]'):
        label = a.get_text(' ', strip=True).lower()
        if not ('next' in a.get('rel', []) or a.find_parent(class_='batchNext') or label in {'next', 'següent', 'següents', 'siguiente', '»', '›'}):
            continue
        target = urljoin(url, a['href'])
        if target != url:
            if not inventory_url(target):
                raise ValueError('Pagination leaves reviewed municipal inventory')
            next_pages.append(target)
    tiles = core.select('.tileItem')
    for tile in tiles:
        a = tile.select_one('a.stretched-link[href]')
        if a is None:
            raise ValueError(f'Unrecognised inventory entry: {url}')
        target = urljoin(url, a['href'])
        if not inventory_url(target):
            raise ValueError(f'Unexpected inventory target: {target}')
        children.append(target)
    if tiles:
        return children, list(dict.fromkeys(next_pages)), None
    if 'Actualment no hi ha elements dins' in core.get_text(' ', strip=True):
        return [], list(dict.fromkeys(next_pages)), None
    body = core.select_one('[id^=parent-fieldname-text]')
    if body is None:
        raise ValueError(f'Missing instrument body: {url}')
    docs, refs = {}, {}
    for a in body.select('a[href]'):
        target = html_module.unescape(urljoin(url, a['href']))
        p = urlsplit(target)
        label = a.get_text(' ', strip=True)
        if p.hostname == 'www.laseu.cat' and p.path.startswith('/fitxers/') and re.search(r'\.(pdf|rar|7z|zip)(/|$)', p.path, re.I):
            if target in docs:
                continue
            item = {'titulo': label or p.path.rsplit('/', 1)[-1], 'url': target, 'source_url': url}
            lower = label.lower()
            if 'dogc' in lower or 'publica' in lower:
                item['fecha_publicacion'] = explicit_date(label)
            elif 'acord' in lower:
                item['fecha_acuerdo'] = explicit_date(label)
            docs[target] = item
        elif p.hostname in {'dtes.gencat.cat', 'ptop.gencat.net'} and 'rpucportal' in p.path:
            refs[target] = {'titulo': label, 'url': target, 'source_url': url}
    if not docs:
        raise ValueError(f'Instrument without source documents: {url}')
    title = heading.get_text(' ', strip=True)
    if 'text-refos-2002' in url:
        title = "PLA GENERAL D'ORDENACIÓ URBANA - " + title
    row = {
        'id': 'la-seu-d-urgell-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': "La Seu d'Urgell", 'provincia': 'Lleida', 'codigo_ine': '25203',
        'titulo': title, 'tipo': 'planeamiento_urbanistico', 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': url, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_urbanisme',
        'descripcion': body.get_text(' ', strip=True),
        'documentos': list(docs.values()), 'referencias': list(refs.values()),
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
    }
    if urlsplit(url).path == urlsplit(MOBILITY_SOURCE).path:
        row['tipo'] = 'plan_movilidad'
        # The explicit narrative refers to this instrument, unlike page metadata
        # or labels for several historical agreements in other detail pages.
        for p in body.select('p'):
            text = p.get_text(' ', strip=True)
            if 'va ser aprovat definitivament pel Ple Municipal del dia' in text:
                approval, sep, publication = text.partition('i publicat al BOP el dia')
                if sep:
                    row['fecha_aprob'] = explicit_date(approval)
                    row['fecha_publicacion'] = explicit_date(publication)
                    row['fase'] = 'aprobación definitiva'
    return [], list(dict.fromkeys(next_pages)), row


class LaSeuDUrgellAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.laseu.cat')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        queue, seen, rows, captures = list(STARTS), set(), {}, []
        capture_dir = self.config.get('capture_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-la-seu-d-urgell/1.0'
            while queue:
                url = queue.pop(0)
                if url in seen:
                    continue
                if len(seen) >= 200:
                    raise ValueError('Inventory exceeds safety bound; refusing truncated output')
                seen.add(url)
                with session.get(url, timeout=40, stream=True) as response:
                    response.raise_for_status()
                    if not inventory_url(response.url):
                        raise ValueError('Unexpected redirect outside inventory')
                    content = bytearray()
                    for chunk in response.iter_content(65536):
                        content.extend(chunk)
                        if len(content) > 4_000_000:
                            raise ValueError('Oversized inventory response')
                    text = content.decode('utf-8')
                if capture_dir:
                    path = Path(capture_dir) / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                    captures.append({'url': url, 'path': str(path), 'sha256': hashlib.sha256(content).hexdigest()})
                children, following, row = parse_page(text, url)
                if any(target in seen for target in following):
                    raise ValueError('Pagination cycle detected; refusing partial snapshot')
                queue.extend(children + following)
                if row:
                    if row['id'] in rows:
                        raise ValueError('Detail page repeated across pagination')
                    rows[row['id']] = row
        if not rows:
            raise ValueError('No usable municipal planning instruments')
        self._write(out_jsonl, list(rows.values()))
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(seen),
                'limitations': LIMITATIONS, 'captures': captures, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
