"""Snapshot of Alella's official works-project inventory (not granted licences)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urldefrag, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

INVENTORY = 'https://alella.cat/fitxes.php?id=68'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
LIMITATIONS = [
    'Partial coverage: current municipal works-project inventory only; separate planning inventory and historical archives not extracted.',
    'No verified granted-licence register; licence procedures and forms excluded.',
    'Documents retained as links, not downloaded or interpreted; malformed and expiring source links may be unusable.',
    'Dates and phases reflect labelled municipal fields, not independent verification of agreements or execution status.',
    'No verified project geometry; coordinates remain null and publication_ready is false.',
]


def text(node):
    return node.get_text(' ', strip=True) if node else ''


def parse_date(value):
    """Parse only a single explicit Catalan/numeric date; never a crawl date."""
    value = value.lower().replace('’', "'")
    dates = set()
    for d, m, y in re.findall(r'\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b', value):
        dates.add(date(int(y), int(m), int(d)).isoformat())
    for d, m, y in re.findall(r"\b(\d{1,2})\s+(?:de\s+|d'\s*)?([a-zç]+)\s+de\s+(\d{4})\b", value):
        if m in MONTHS:
            dates.add(date(int(y), MONTHS[m], int(d)).isoformat())
    if len(dates) > 1:
        raise ValueError('Ambiguous dates in a single date field')
    return next(iter(dates), None)


def municipal_url(url, path):
    u = urlsplit(url)
    return u.scheme == 'https' and u.netloc == 'alella.cat' and u.path == path


def parse_inventory(html, url=INVENTORY):
    soup = BeautifulSoup(html, 'html.parser')
    listing = soup.select_one('#LLISTAT .llista-fitxes')
    if not listing or text(soup.select_one('title')) != "Ajuntament d'Alella - Projectes obres":
        raise ValueError('Missing Alella works inventory')
    projects = {}
    for a in listing.select('li.fitxes .titol a[href]'):
        title = text(a)
        target = urldefrag(urljoin(url, a['href']))[0]
        if not re.match(r'^(?:PROJECTE|AVANTPROJECTE)\b', title, re.I):
            raise ValueError('Unexpected non-project entry in works inventory')
        if not municipal_url(target, '/fitxa.php') or not re.fullmatch(r'id=\d+', urlsplit(target).query):
            raise ValueError('Unexpected works detail URL')
        projects[target] = title
    if not projects:
        raise ValueError('Empty works inventory')
    # Follow every advertised inventory page, not a guessed first-N slice.
    pages = set()
    for a in soup.select('a[href]'):
        target = urldefrag(urljoin(url, a['href']))[0]
        u = urlsplit(target)
        q = parse_qs(u.query)
        rel_next = 'next' in a.get('rel', [])
        pager = a.find_parent(class_=re.compile(r'pagin|pager', re.I))
        same_inventory = municipal_url(target, '/fitxes.php') and q.get('id') == ['68']
        if same_inventory and not ({'per_imprimir', 'idioma'} & q.keys()):
            if target != url:
                pages.add(target)
        elif rel_next or pager:
            raise ValueError('Unrecognized pagination target; refusing partial extraction')
    for form in soup.select('form'):
        if form.select('select[name*=pag], input[name*=pag], select[name*=offset]'):
            raise ValueError('Unsupported form pagination')
    return projects, sorted(pages)


def parse_project(html, url, expected_title):
    soup = BeautifulSoup(html, 'html.parser')
    doc = soup.select_one('#COLDRETA2 .DOCUMENT')
    title = text(doc.select_one('.COS > .TITOL .eltitol')) if doc else ''
    fields = doc.select_one('#FCBE') if doc else None
    if title != expected_title or not fields:
        raise ValueError('Works detail missing or mismatched with inventory')
    raw, nodes = {}, {}
    for field in fields.select('.camp_fitxa'):
        label, body = text(field.select_one('.txt_titol_fitxa')), field.select_one('.cos_fitxa')
        if label in raw or not label or body is None:
            raise ValueError('Ambiguous works field structure')
        raw[label], nodes[label] = text(body), body
    if not raw.get('Nom del projecte') or not raw.get('Documents'):
        raise ValueError('Missing concrete project or documents')
    documents = {}
    for label, node in nodes.items():
        for a in node.select('a[href]'):
            href = a['href']
            # Preserve malformed source hrefs without inventing repaired URLs.
            malformed = bool(re.match(r'^[^:/]+https?://', href, re.I))
            target = href if malformed else urljoin(url, href)
            if not malformed and urlsplit(target).scheme not in ('http', 'https'):
                raise ValueError('Unexpected document protocol')
            image = a.select_one('img[alt]')
            caption = text(a) or (image['alt'] if image else '')
            item = documents.setdefault(target, {
                'url': target, 'source_href': href, 'titulo': caption,
                'source_url': url, 'source_field': label,
                'link_status': 'malformed_source_href' if malformed else ('expiring_signed_link_not_fetched' if 'X-Amz-' in target else 'not_fetched'),
            })
            if not item['titulo']:
                item['titulo'] = caption
    if not documents:
        raise ValueError('Project has no document links')
    initial = parse_date(raw.get('Data aprovació inicial', ''))
    definitive = parse_date(raw.get('Data aprovació definitiva', ''))
    phase = text(doc.select_one('.COS > .sotstitol')) or None
    if not phase:
        phase = 'aprobación definitiva' if definitive else ('aprobación inicial' if initial else ('anteproyecto' if title.startswith('AVANTPROJECTE') else None))
    return {
        'id': 'alella-proy-' + parse_qs(urlsplit(url).query)['id'][0],
        'municipio': 'Alella', 'provincia': 'Barcelona', 'codigo_ine': '08003',
        'titulo': title, 'tipo': 'anteproyecto de obras' if title.startswith('AVANTPROJECTE') else 'proyecto de obras',
        'fase': phase, 'url': url, 'inventory_url': INVENTORY,
        'source': 'ayuntamiento', 'origen': 'inventario_municipal_proyectos_obras',
        'fecha': None,
        'fecha_publicacion': parse_date(text(doc.select_one('.CAP .PUBLICACIO .DMA'))),
        'fecha_anuncio_bopb': parse_date(raw.get('Data anunci BOPB', '')),
        'fecha_aprobacion_inicial': initial, 'fecha_aprobacion_definitiva': definitive,
        'fecha_aprob': definitive or initial,
        'descripcion': raw.get('Descripció'),
        'source_fields': raw, 'documentos': list(documents.values()),
        'lat': None, 'lon': None, 'geometry': None,
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class AlellaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='alella', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://alella.cat')
        if slug != 'alella':
            raise ValueError('Alella adapter requires slug alella')
        self.captures = []

    def _fetch(self, url):
        if not (municipal_url(url, '/fitxes.php') or municipal_url(url, '/fitxa.php')):
            raise ValueError('Fetch outside municipal inventory/detail scope')
        with requests.get(url, timeout=40, stream=True, headers={'User-Agent': 'municipio-alella/1.0'}) as response:
            response.raise_for_status()
            if urlsplit(response.url).netloc != 'alella.cat':
                raise ValueError('Unexpected source redirect')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Source exceeds 4 MB; refusing truncated extraction')
                chunks.append(chunk)
            body = b''.join(chunks)
            html = body.decode(response.encoding or 'utf-8')
            capture = {'url': url, 'final_url': response.url, 'status': response.status_code,
                       'retrieved_at': datetime.now(timezone.utc).isoformat(),
                       'sha256': hashlib.sha256(body).hexdigest()}
            if self.config.get('evidence_dir'):
                folder = Path(self.config['evidence_dir'])
                folder.mkdir(parents=True, exist_ok=True)
                name = 'source-' + hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
                (folder / name).write_bytes(body)
                capture['capture_file'] = name
            self.captures.append(capture)
            return html

    def backfill_proyectos(self, out_jsonl: Path):
        self.captures = []
        pending, visited, projects = [INVENTORY], set(), {}
        fingerprints = set()
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Pagination safety limit reached; no partial output written')
            found, pages = parse_inventory(self._fetch(url), url)
            fingerprint = tuple(sorted(found))
            if fingerprint in fingerprints:
                raise ValueError('Repeated inventory page; pagination may be ignored by server')
            fingerprints.add(fingerprint)
            visited.add(url)
            for target, title in found.items():
                if target in projects and projects[target] != title:
                    raise ValueError('Conflicting titles for a project')
                projects[target] = title
            pending.extend(p for p in pages if p not in visited and p not in pending)
        rows = [parse_project(self._fetch(url), url, title) for url, title in projects.items()]
        # Write only after every page and detail succeeds.
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'live_records': len(rows),
                'inventory_pages': sorted(visited), 'source_urls': [c['url'] for c in self.captures],
                'captures': self.captures, 'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        """Refresh the whole advertised inventory; no unsupported incremental cursor."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': LIMITATIONS[1]}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
