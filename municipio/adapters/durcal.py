"""Selected complete instrument folders in Dúrcal's anonymous official inventory."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://adurcal.sedelectronica.es'
URBANISMO = BASE + '/transparency/93d3a21f-0a01-4306-bd0d-4d90df13202c/'
PLANNING = BASE + '/transparency/358ec28b-a667-4e8c-a86e-3ec5ebdf641e/'
DETAILED = BASE + '/transparency/02d78f61-729b-42d3-9d59-fa3ce5582f84/'
SCOPES = (
    (PLANNING, 'ADAPTACION PARCIAL A LA LOUA DE NNSS DE DÚRCAL', 'adaptación parcial NNSS a LOUA'),
    (PLANNING, 'PGOU', 'modificación puntual del PGOU'),
    (PLANNING, 'PROYECTO DELIMITACIÓN CASCO URBANO', 'proyecto de delimitación'),
    (DETAILED, 'PLAN PARCIAL SECTOR SUBS-I-D1 SAN BLAS', 'plan parcial'),
    (URBANISMO, '7.4. OBRAS PÚBLICAS E INFRAESTRUCTURAS', 'estudio de viabilidad'),
)
LIMITATIONS = [
    'Partial snapshot of five selected instrument/project folders; not all municipal planning or works.',
    'Inventory metadata only; PDF contents and legal validity not interpreted.',
    'No verified publication/agreement/approval dates; filename dates and document creation dates are not used.',
    'No verified project geometry; publication_ready=false. No granted licences extracted.',
    'Excluded: SNU building inventory, environmental programmes, public-information projects and agreements.',
    'Generic PGOU regional search link retained only as a reference, not a distinct plan record.',
]


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, 'html.parser')
    if 'Ayuntamiento de Dúrcal' not in soup.get_text(' ', strip=True):
        raise ValueError('Not the official Dúrcal inventory')
    if not soup.select('td.class_name'):
        raise ValueError('Missing inventory rows (login, empty or changed source)')
    return soup


def folder_action(html: str, title: str) -> tuple[str, int]:
    """Read the public Wicket link as data; never evaluate website JavaScript."""
    matches = []
    for a in _soup(html).select('td.class_name a.exp[onclick]'):
        text = a.get_text(' ', strip=True)
        count = re.fullmatch(r'(.*?)\s*\(\s*(\d+)\s*\)', text)
        if count and count[1].strip() == title:
            action = re.search(r"wicketAjaxGet\('([^']+)'", a['onclick'])
            if not action:
                raise ValueError('Missing public folder action')
            matches.append((action[1], int(count[2])))
    if len(matches) != 1:
        raise ValueError(f'Missing or ambiguous folder: {title}')
    return matches[0]


def parse_documents(html: str, expected: int) -> list[dict]:
    soup = _soup(html)
    if soup.select('td.class_name a.exp'):
        raise ValueError('Unexpected nested folders; refusing partial extraction')
    docs = []
    for a in soup.select('td.class_name a[href]'):
        href = a['href']
        if href == '#':
            raise ValueError('Unresolved document link')
        title = a.get_text(' ', strip=True)
        target = urlparse(href)
        if not title or target.scheme != 'https':
            raise ValueError('Invalid document')
        if target.hostname == urlparse(BASE).hostname and re.fullmatch(
            r'/preview-document/[0-9a-f-]{36}', target.path
        ):
            docs.append({'titulo': title, 'url': href, 'provenance': 'municipal_document_preview'})
        elif href == 'https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf' and title == 'PGOU':
            docs.append({'titulo': title, 'url': href, 'provenance': 'regional_search_reference'})
        else:
            raise ValueError(f'Unexpected document URL: {href}')
    # The parent gives the complete folder count, including documents beyond page 1.
    # Fail closed if pagination is introduced; never emit a truncated snapshot.
    if len(docs) != expected or len({d['url'] for d in docs}) != expected or not docs:
        raise ValueError(f'Incomplete folder/pagination: expected {expected}, found {len(docs)}')
    return docs


def make_record(folder: str, kind: str, url: str, documents: list[dict]) -> dict:
    references = [d for d in documents if d['provenance'] == 'regional_search_reference']
    docs = [d for d in documents if d['provenance'] == 'municipal_document_preview']
    if folder == 'PGOU':
        # The general-plan entry is a generic search link. Only the three clearly
        # named modification documents constitute an identifiable instrument here.
        if len(docs) != 3 or any(not re.search(r'(?:MODIFICACION|MOD)\s*PUNTUAL\s*N[º°]?\s*1\b', d['titulo'], re.I) for d in docs):
            raise ValueError('Ambiguous PGOU modification documents')
        title = 'Modificación puntual nº 1 del PGOU de Dúrcal'
    elif kind == 'estudio de viabilidad':
        if len(docs) != 1 or docs[0]['titulo'] != 'Proyecto viabilidad piscina cubierta':
            raise ValueError('Changed public works folder; grouping needs review')
        title = docs[0]['titulo']
    else:
        title = folder
    if not docs:
        raise ValueError('No instrument documents')
    return {
        'id': 'durcal-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Dúrcal', 'codigo_ine': '18071', 'provincia': 'Granada',
        'titulo': title, 'tipo': kind, 'fase': None,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'url': url, 'inventory_url': url, 'url_documento': docs[0]['url'],
        'documentos': docs, 'referencias': references,
        'source': 'ayuntamiento', 'origen': 'inventario_documental_municipal',
        'descripcion': 'Instrumento/proyecto identificado en el inventario municipal; documentos agrupados. '
                       'Su presencia no acredita aprobación, vigencia ni ejecución de obras.',
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'geometry_status': 'No verified project geometry',
    }


class DurcalAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='durcal', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        captures = self.config.get('capture_dir')
        urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-durcal/1.0 (public inventory research)'

            def fetch(url):
                if urlparse(url).hostname != urlparse(BASE).hostname:
                    raise ValueError('Unexpected source host')
                with session.get(url, timeout=30, stream=True) as response:
                    response.raise_for_status()
                    if urlparse(response.url).hostname != urlparse(BASE).hostname:
                        raise ValueError('Unexpected redirect host')
                    data = bytearray()
                    for chunk in response.iter_content(65536):
                        data.extend(chunk)
                        if len(data) > 3_000_000:
                            raise ValueError('Inventory response exceeds size limit')
                    html = data.decode('utf-8')
                    # Store canonical URLs, not session-specific Wicket action URLs.
                    canonical = response.url
                    if not re.fullmatch(re.escape(BASE) + r'/transparency/[0-9a-f-]{36}/', canonical):
                        raise ValueError('Expected canonical public folder URL')
                    urls.append(canonical)
                    if captures:
                        path = Path(captures)
                        path.mkdir(parents=True, exist_ok=True)
                        (path / (canonical.rstrip('/').rsplit('/', 1)[1] + '.html')).write_text(html, encoding='utf-8')
                    return html, canonical

            rows = []
            for parent, folder, kind in SCOPES:
                # Refresh each parent immediately before following its public action;
                # Wicket tokens belong to the anonymous session and current page.
                html, parent_url = fetch(parent)
                action, expected = folder_action(html, folder)
                html, folder_url = fetch(urljoin(parent_url, action))
                rows.append(make_record(folder, kind, folder_url, parse_documents(html, expected)))
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'live_records': len(rows),
                'source_urls': sorted(set(urls)), 'limitations': LIMITATIONS,
                'coverage': 'five_selected_complete_instrument_folders', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete scoped snapshot, with stable folder identity; no date watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
