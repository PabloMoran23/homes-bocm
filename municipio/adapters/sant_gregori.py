"""Sant Gregori: municipal public-exhibition, definitive-project and POUM pages."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.santgregori.cat'
URBANISME = BASE + '/ca/arees-municipals/urbanisme-i-habitatge/'
SOURCES = {
    'publica': URBANISME + 'projectes-a-exposicio-publica/',
    'definitius': URBANISME + 'projectes-definitius/',
    'poum': URBANISME + 'poum/',
    'documents': URBANISME + 'poum/memoria-i-documentacio/',
}
HEADINGS = {'publica': 'Projectes a exposició pública', 'definitius': 'Projectes definitius',
            'poum': 'POUM', 'documents': 'Memòria i documentació'}
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
LIMITATIONS = [
    'Partial snapshot of municipal public-exhibition and definitive-project inventories and the base POUM; not a complete historical register.',
    'POUM modifications, the separate transparency portal and other municipal works outside these pages are not extracted.',
    'Dates and stages are municipal page assertions, not independent PDF or gazette verification; linked documents are retained without parsing their contents.',
    'No verified project geometry; coordinates remain null and publication_ready is false.',
    'No public granted-licence register verified; licences disabled.',
    'The general urbanism overview calls 22/03/2011 the publication date; the specific POUM page explicitly cites DOGC 5841 of 21/03/2011. The latter is used; 22/03 is entry into force.',
]


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def catalan_date(value):
    match = re.search(r"(\d{1,2})\s+(?:de\s+|d[’'])?(\w+)\s+de\s+(\d{4})", value.lower())
    if not match:
        return None
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


def content(html, kind):
    soup = BeautifulSoup(html, 'html.parser')
    h1 = soup.find('h1')
    if h1 is None or text(h1) != HEADINGS[kind]:
        raise ValueError(f'{kind}: missing municipal inventory heading')
    # The product-style document page has one extra content-block wrapper.
    root = h1.parent.parent.parent if kind == 'documents' else h1.parent.parent
    if root.select('[rel~=next], .pagination, .paginacio, .pager'):
        raise ValueError(f'{kind}: pagination appeared; refusing a partial traversal')
    return root


def documents(root, source):
    found = {}
    for a in root.select('a[href]'):
        url = urljoin(source, a['href'])
        if urlparse(url).scheme in ('https', 'http') and urlparse(url).path.lower().endswith('.pdf'):
            found.setdefault(url, {'titulo': text(a).removesuffix(' (PDF)'), 'url': url, 'source_url': source})
    return list(found.values())


def record(title, source, docs, description, phase, agreement=None, publication=None):
    return {
        'id': 'sant-gregori-proy-' + hashlib.sha256((source + '#' + title.casefold()).encode()).hexdigest()[:16],
        'municipio': 'Sant Gregori', 'provincia': 'Girona', 'codigo_ine': '17163',
        'titulo': title, 'tipo': 'planeamiento' if title.startswith(('Pla ', 'POUM')) else 'obra pública',
        'fase': phase, 'fecha': None, 'fecha_acuerdo': agreement,
        'fecha_publicacion': publication, 'descripcion': description,
        'url': source, 'url_documento': docs[0]['url'] if docs else None,
        'documentos': docs, 'source': 'ayuntamiento', 'origen': 'urbanisme_municipal',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified project geometry from the source pages',
    }


def parse_inventory(html: str, kind: str) -> list[dict[str, Any]]:
    if kind not in ('publica', 'definitius'):
        raise ValueError('Unsupported inventory')
    root = content(html, kind)
    body = root.select_one('.text')
    if body is None:
        raise ValueError(f'{kind}: missing inventory body')
    docs = documents(root, SOURCES[kind])
    rows = []
    used = set()
    for p in body.find_all('p'):
        narrative = text(p)
        # Only a named instrument/work with its own explicit approval assertion.
        if not narrative.startswith(('Projecte constructiu ', 'Pla Parcial Urbanístic ')):
            if 'Aprovat ' in narrative:
                raise ValueError('Unrecognized approved inventory entry')
            continue
        title = narrative.split(' (Aprovat', 1)[0].strip()
        if title == narrative or not any(word in narrative for word in ('Aprovat inicialment', 'Aprovat definitivament')):
            raise ValueError('Project entry has no explicit approval narrative')
        associated = [d for d in docs if title.casefold() in d['titulo'].casefold()]
        # Inline PDF labels can differ from surrounding text (e.g. protected data).
        for doc in documents(p, SOURCES[kind]):
            if doc['url'] not in {d['url'] for d in associated}:
                associated.append(doc)
        if not associated:
            raise ValueError('Project entry has no document provenance')
        used.update(d['url'] for d in associated)
        phase = 'aprobación definitiva' if 'Aprovat definitivament' in narrative else 'aprobación inicial'
        rows.append(record(title, SOURCES[kind], associated, narrative, phase,
                           catalan_date(narrative.split('(Aprovat', 1)[1])))
    if not rows or used != {d['url'] for d in docs}:
        raise ValueError(f'{kind}: empty or unassigned document inventory')
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate project identity')
    return rows


def parse_poum(html: str, document_html: str) -> dict[str, Any]:
    root = content(html, 'poum')
    body = root.select_one('.text')
    if body is None:
        raise ValueError('POUM narrative missing')
    paragraphs = [text(p) for p in body.find_all('p')]
    approvals = [p for p in paragraphs if 'va acordar aprovar definitivament' in p and 'Sant Gregori' in p]
    publications = [p for p in paragraphs if 'DOGC' in p and 'publicació' in p]
    if len(approvals) != 1 or len(publications) != 1:
        raise ValueError('Ambiguous or missing POUM approval/publication narrative')
    publication = re.search(r'DOGC.*?núm\.\s*\d+\s+de\s+(\d{2})/(\d{2})/(\d{4})', publications[0])
    if publication is None:
        raise ValueError('Missing explicit DOGC publication date')
    docs = documents(content(document_html, 'documents'), SOURCES['documents'])
    if not docs:
        raise ValueError('POUM document inventory missing')
    gazettes = [urljoin(SOURCES['poum'], a['href']) for a in body.select('a[href]')
                if urlparse(urljoin(SOURCES['poum'], a['href'])).hostname == 'dogc.gencat.cat']
    if len(set(gazettes)) != 1:
        raise ValueError('POUM gazette reference missing or ambiguous')
    docs.append({'titulo': 'DOGC — publicació del POUM', 'url': gazettes[0], 'source_url': SOURCES['poum']})
    result = record('POUM de Sant Gregori', SOURCES['poum'], docs, '\n'.join(paragraphs),
                    'aprobación definitiva', catalan_date(approvals[0]),
                    date(int(publication[3]), int(publication[2]), int(publication[1])).isoformat())
    result['fecha_aprob'] = result['fecha_acuerdo']
    return result


class SantGregoriAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='sant-gregori', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, kind):
        response = requests.get(SOURCES[kind], timeout=40, stream=True,
                                headers={'User-Agent': 'municipio-sant-gregori/1.0'})
        with response:
            response.raise_for_status()
            if response.url.rstrip('/') != SOURCES[kind].rstrip('/'):
                raise ValueError('Unexpected municipal source redirect')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Municipal source is not HTML')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Municipal HTML response exceeds 4 MB')
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f'{kind}.html').write_bytes(data)
        return data.decode('utf-8')

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        pages = {kind: self._fetch(kind) for kind in SOURCES}
        rows = parse_inventory(pages['publica'], 'publica') + parse_inventory(pages['definitius'], 'definitius')
        rows.append(parse_poum(pages['poum'], pages['documents']))
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(SOURCES.values()),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Refresh all four non-paginated pages; never append duplicate snapshots.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence source'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
