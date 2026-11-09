"""Municipal statutory planning inventory; no licence or news inference."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.cerdedo-cotobade.gal'
SOURCE = BASE + '/servizos/urbanismo/'
EXCLUDED = {'pmus-plan-de-mobilidade', 'axenda-urbana-de-cerdedo-cotobade'}
LIMITATIONS = [
    'Partial coverage: statutory planning pages linked from municipal Urbanismo only; no news, procurement, historic noticeboard or licence register.',
    'NNSS modifications I and III are separate instruments; correction of errors belongs to III. Undated map variants remain in the NNSS document inventory with their original labels.',
    'No publication/agreement/approval dates established from HTML; upload paths, file names and WordPress modification times are not legal dates.',
    'Document URLs are retained as published, including external hosting and large archives; linked file contents and availability are not exhaustively validated.',
    'No verified vector geometry or coordinates; raster/PDF maps are documents, not extracted geometries.',
]


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main .entry-content')
    if main is None:
        raise ValueError('Missing municipal main entry content')
    if soup.select('a[rel~=next], .pagination, .nav-links .next, .page-links'):
        raise ValueError('Pagination detected: traversal must be reviewed before extraction')
    for a in main.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'seguinte', 'siguiente', 'next', 'ver máis', 'cargar máis'}:
            raise ValueError('Uncovered pagination in municipal inventory')
    return main


def parse_inventory(html):
    pages = {}
    for a in content(html).select('a[href]'):
        url = urljoin(SOURCE, a['href'])
        p = urlsplit(url)
        if p.netloc != urlsplit(BASE).netloc or not p.path.startswith('/servizos/urbanismo/'):
            continue
        key = p.path.rstrip('/').rsplit('/', 1)[-1]
        if key == 'urbanismo' or key in EXCLUDED:
            continue
        title = a.get_text(' ', strip=True)
        if not title:
            continue
        if not re.search(r'PXOM|Plan Especial|P\.\s*E\.|Normas subsidiarias', title, re.I):
            raise ValueError('Unclassified urbanismo inventory entry: ' + title)
        pages.setdefault(key, {'url': BASE + p.path.rstrip('/') + '/', 'titulo': title})
    if not pages:
        raise ValueError('No statutory planning inventory entries')
    return list(pages.values())


def parse_instrument(html, page):
    main = content(html)
    documents = {}
    for a in main.select('a[href]'):
        title = a.get_text(' ', strip=True)
        url = urljoin(page['url'], a['href'])
        p = urlsplit(url)
        # Unlabelled Drive links are copy/paste artefacts on the EL/ZV-30 page.
        if not title or p.scheme not in {'http', 'https'}:
            continue
        if not (re.search(r'\.(pdf|jpg|jpeg|png|zip)$', unquote(p.path), re.I)
                or (p.netloc == 'drive.google.com' and p.path.startswith('/file/d/'))):
            continue
        documents.setdefault(url, {'titulo': title, 'url': url, 'pagina_fuente': page['url']})
    if not documents:
        raise ValueError('Planning page has no labelled source documents: ' + page['url'])
    groups = {'principal': []}
    nnss = page['url'].rstrip('/').endswith('/normas-subsidiarias-cotobade')
    for doc in documents.values():
        key = 'principal'
        if nnss:
            label = doc['titulo'].casefold()
            if re.search(r'modificaci[oó]n\s+iii\b', label) or 'corrección de erros' in label:
                key = 'modificacion-iii'
            elif re.search(r'modificaci[oó]n\s+i\b', label):
                key = 'modificacion-i'
        groups.setdefault(key, []).append(doc)
    rows = []
    for key, docs in groups.items():
        if not docs:
            continue
        if key == 'modificacion-iii' and not any(re.search(r'modificaci[oó]n\s+iii\b', d['titulo'], re.I) for d in docs):
            raise ValueError('Correction without its modification III document')
        suffix = '' if key == 'principal' else '-' + key
        title = page['titulo']
        if suffix:
            title += ' — ' + ('Modificación I' if key == 'modificacion-i' else 'Modificación III y corrección de errores')
        rows.append({
            'id': 'cerdedo-cotobade-proy-' + page['url'].rstrip('/').rsplit('/', 1)[-1] + suffix,
            'municipio': 'Cerdedo-Cotobade', 'codigo_ine': '36902', 'provincia': 'Pontevedra',
            'titulo': title, 'tipo': 'planeamiento_urbanistico',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': page['url'], 'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
            'documentos': docs, 'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    return rows


class CerdedoCotobadeAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        r = requests.get(url, timeout=40, headers={'User-Agent': 'municipio-cerdedo-cotobade/1.0'})
        r.raise_for_status()
        if len(r.content) > 5_000_000 or 'text/html' not in r.headers.get('Content-Type', ''):
            raise ValueError('Unexpected municipal HTML response: ' + url)
        html = r.content.decode(r.encoding or 'utf-8')
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1]
            (directory / (name + '.html')).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        pages = parse_inventory(self._fetch(SOURCE))
        rows = []
        for page in pages:
            rows.extend(parse_instrument(self._fetch(page['url']), page))
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Duplicate instrument IDs')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + [p['url'] for p in pages],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of the current static inventory; state is not a cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
