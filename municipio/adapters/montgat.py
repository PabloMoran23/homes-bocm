"""Montgat's public-exhibition inventory, enriched with the Mallorquines dossier."""
from __future__ import annotations

import hashlib
import json
import re
import ssl
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.montgat.cat'
PLANNING = BASE + '/ajuntament/regulacio-urbanistica/planejament-urbanistic'
INVENTORY = ('https://seu-e.cat/ca/web/montgat/govern-obert-i-transparencia/'
             'accio-de-govern-i-normativa/urbanisme/processos-en-exposicio-publica-361')
CROSS_CERT = 'https://letsencrypt.org/certs/gen-y/root-yr-by-x1.pem'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))
DATE_PATTERN = r'(\d{1,2}) de (\w+) de (\d{4})'


def norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def no_pagination(soup):
    # These sources are static complete pages. Fail if that contract changes.
    for a in soup.select('a[href], button'):
        label = norm(text(a))
        rel = a.get('rel', [])
        if ('next' in rel or label in {'seguent', 'siguiente', 'next', '›', '»'}
                or a.find_parent(class_=re.compile(r'^(?:pagination|paginacio|paginacion|pager)(?:[_-].*)?$'))):
            if not a.has_attr('disabled') and a.get('aria-disabled') != 'true':
                raise ValueError('Pagination detected: extend traversal before extracting')


def content(html, selector):
    soup = BeautifulSoup(html, 'html.parser')
    no_pagination(soup)
    node = soup.select_one(selector)
    if node is None:
        raise ValueError('Official content container missing')
    return soup, node


def parse_inventory(html):
    soup = BeautifulSoup(html, 'html.parser')
    no_pagination(soup)
    candidates = [n for n in soup.select('.journal-content-article')
                  if any(norm(text(p)).startswith(('projecte ', 'pla especial ', 'aprovacio inicial modificacio '))
                         for p in n.select('p'))]
    if len(candidates) != 1:
        raise ValueError('Missing or ambiguous public-exhibition inventory')
    rows = {}
    for p in candidates[0].select('p'):
        title = text(p)
        if not title:
            continue
        if not norm(title).startswith(('projecte ', 'pla especial urbanistic ', 'aprovacio inicial modificacio puntual del pla general ')):
            raise ValueError('Unrecognized inventory entry: ' + title)
        key = norm(title)
        rows.setdefault(key, {
            'id': 'montgat-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Montgat', 'codigo_ine': '08126', 'provincia': 'Barcelona',
            'titulo': title, 'tipo': 'obra pública' if key.startswith('projecte ') else 'planeamiento urbanístico',
            'fase': None, 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': INVENTORY, 'source': 'ayuntamiento',
            'origen': 'inventario_exposicion_publica',
            'descripcion': title, 'documentos': [], 'source_urls': [INVENTORY],
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'limitaciones': ['Listed by municipality; no execution status or project geometry verified.'],
        })
    if not rows:
        raise ValueError('Empty project inventory')
    return list(rows.values())


def parse_planning_index(html):
    _, node = content(html, '#readspeakerPage')
    if node.select_one('h1') is None or text(node.select_one('h1')) != 'Planejament urbanístic':
        raise ValueError('Unexpected planning index')
    links = {}
    for a in node.select('.widgetMenu a[href]'):
        url = urljoin(PLANNING, a['href'])
        if not url.startswith(PLANNING + '/') or urlparse(url).query or urlparse(url).fragment:
            raise ValueError('Unexpected planning detail URL')
        links[url] = text(a)
    if not links:
        raise ValueError('Planning inventory has no detail pages')
    return links


def parse_detail(html, url):
    soup, node = content(html, '#readspeakerPage')
    heading = node.select_one('h1')
    if heading is None or 'mallorquines' not in norm(text(heading)):
        raise ValueError('Unreviewed planning instrument; extend grouping before extraction')
    title = text(heading)
    body = node.select_one('.dinamic')
    if body is None:
        raise ValueError('Planning detail body missing')
    paragraphs = [text(p) for p in body.select('.ddbbtext p') if text(p)]
    if not paragraphs:
        raise ValueError('Missing planning narrative')
    docs = {}
    for a in soup.select('#readspeakerPage .dinamic a[href], #page-documents a[href]'):
        href = urljoin(url, a['href'])
        parsed = urlparse(href)
        is_csv = (parsed.hostname == 'tramits.montgat.cat' and
                  parsed.path == '/Ciutadania/ValidarDocuments.aspx' and
                  re.fullmatch(r'csv=[0-9a-f-]{36}', parsed.query))
        is_file = parsed.hostname == 'www.montgat.cat' and parsed.path.startswith('/media/repository/')
        if not (is_csv or is_file):
            continue
        label = text(a)
        if not label:
            raise ValueError('Source document has no title')
        doc = {'titulo': label, 'url': href, 'source_url': url,
               'etapa': 'aprobacion_inicial' if norm(title).startswith('aprovacio inicial') else 'avance',
               'tipo_enlace': 'validacion_csv' if is_csv else 'archivo_municipal'}
        # Only explicitly labelled BOPB publication dates. Never use file mtime,
        # page update, signature date, or a consultation deadline as approval.
        m = re.search(r'BOPB (\d{2})\.(\d{2})\.(\d{2})(?:\s|$)', label)
        if m:
            doc['fecha_publicacion'] = date(2000 + int(m[3]), int(m[2]), int(m[1])).isoformat()
            doc['fecha_provenance'] = 'Etiqueta del anuncio BOPB en la página municipal'
        docs[href] = doc
    if not docs:
        raise ValueError('Planning instrument lacks linked documents')
    result = {'url': url, 'titulo': title, 'documentos': list(docs.values()), 'narrativa': paragraphs}
    if norm(title).startswith('aprovacio inicial'):
        first = paragraphs[0]
        m = re.search(r'En sessió celebrada el data ' + DATE_PATTERN + r',.*?aprovació inicial', first)
        ref = re.search(r'exp\.\s*(\d+-\d+/\d{4})', first)
        later = re.search(r'Posteriorment, en data ' + DATE_PATTERN + r', va acordar sotmetre-la novament', first)
        if not m or not ref or not later:
            raise ValueError('Initial approval/agreement evidence changed')
        def iso(match):
            return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()
        result.update(fecha_aprob=iso(m), expediente=ref[1], fecha_nueva_exposicion=iso(later))
    elif not norm(title).startswith('avanc de planejament'):
        raise ValueError('Unknown planning phase')
    return result


def enrich(rows, details):
    targets = [r for r in rows if 'mallorquines' in norm(r['titulo']) and r['tipo'] == 'planeamiento urbanístico']
    current = [d for d in details if 'fecha_aprob' in d]
    if len(targets) != 1 or len(current) != 1:
        raise ValueError('Ambiguous Mallorquines instrument grouping')
    row, approved = targets[0], current[0]
    row.update(url=approved['url'], expediente=approved['expediente'], fase='aprobación inicial',
               fecha_aprob=approved['fecha_aprob'], fecha_acuerdo=approved['fecha_aprob'])
    row['eventos'] = [
        {'tipo': 'aprobacion_inicial', 'fecha_acuerdo': approved['fecha_aprob'], 'source_url': approved['url']},
        {'tipo': 'nueva_informacion_publica', 'fecha_acuerdo': approved['fecha_nueva_exposicion'], 'source_url': approved['url']},
    ]
    docs = {}
    for detail in details:
        row['source_urls'].append(detail['url'])
        for doc in detail['documentos']:
            docs.setdefault(doc['url'], doc)
    row['documentos'] = list(docs.values())
    row['descripcion'] = '\n'.join(approved['narrativa'])
    row['limitaciones'] += [
        'Publication dates belong to individual linked BOPB notices; record publication date is unknown.',
        'Advance documents grouped with initial approval; incomplete historic agreement date is not inferred.',
        'D8-02 owners document is described as withdrawn and has no public link.',
        'CSV validation links retained as published; document contents not downloaded by the adapter.',
    ]
    return rows


class MontgatAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='montgat', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url, context=None):
        req = Request(url, headers={'User-Agent': 'municipio-montgat/1.0'})
        with urlopen(req, timeout=35, context=context) as response:
            raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise ValueError('Source exceeds reviewed response size')
            if urlparse(response.url).hostname != urlparse(url).hostname:
                raise ValueError('Unexpected cross-host source redirect')
            result = raw.decode(response.headers.get_content_charset() or 'utf-8')
        capture = self.config.get('capture_dir')
        if capture:
            dest = Path(capture)
            dest.mkdir(parents=True, exist_ok=True)
            (dest / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(result, encoding='utf-8')
        return result

    def backfill_proyectos(self, out_jsonl):
        # Server omits the new Root YR cross-sign. Obtain it over already
        # verified HTTPS from its issuer, keeping hostname and TLS verification.
        context = ssl.create_default_context()
        context.load_verify_locations(cadata=self._fetch(CROSS_CERT))
        rows = parse_inventory(self._fetch(INVENTORY))
        index = parse_planning_index(self._fetch(PLANNING, context))
        details = [parse_detail(self._fetch(url, context), url) for url in index]
        rows = enrich(rows, details)
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [INVENTORY, PLANNING, *index],
                'publication_ready': False, 'coverage': 'Complete visible exhibition list; partial municipal coverage'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        # No verified granted-licence inventory: never turn forms into grants.
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
