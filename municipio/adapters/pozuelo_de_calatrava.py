"""Reviewed physical works in the official 2026 news archive (partial coverage)."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.pozuelodecalatrava.es/'
ARCHIVE = BASE + 'actualidad.php'
MONTHS = ('enero febrero marzo abril mayo junio julio agosto septiembre octubre '
          'noviembre diciembre').split()
# Narrow reviewed subjects; this is not a classifier for every municipal news item.
# Each requires evidence of physical execution in its own article body.
SUBJECTS = (
    ('pabellon', r'nuevo (?:pabellon deportivo|polideportivo) municipal',
     r'inicio oficial de las obras|actualmente en ejecucion'),
    ('parque-municipal', r'entorno del parque municipal',
     r'ya han empezado a ejecutarse'),
    ('perte-agua', r'red hidrica.*perte', r'ya se estan ejecutando'),
    ('parques-infantiles', r'renovacion y mejora de sus parques infantiles',
     r'ha culminado.*renovacion de los parques infantiles'),
    ('guardapasos', r'inaugura su guardapasos', r'inauguro.*guardapasos municipal'),
    ('arbolado-inesperada', r'planta.*arboles.*inesperada',
     r'con la plantacion de cerca de un centenar de arboles'),
    ('asfaltado', r'plan de asfaltado.*varias calles', r'ha ejecutado un nuevo plan de asfaltado'),
)


def norm(value):
    return unicodedata.normalize('NFKD', value.lower()).encode('ascii', 'ignore').decode()


def official_url(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.netloc == urlparse(BASE).netloc


def publication_date(text):
    match = re.fullmatch(r'(\d{1,2})[. ]([a-zá]+)[., ]+(\d{4})', text.strip().lower())
    if not match or match[2] not in MONTHS:
        raise ValueError(f'Unrecognized publication date: {text!r}')
    return date(int(match[3]), MONTHS.index(match[2]) + 1, int(match[1])).isoformat()


def parse_inventory(html, url):
    """Read only main cards; honor the GET form behind reversed ANTERIOR labels."""
    soup = BeautifulSoup(html, 'html.parser')
    form = soup.select_one('form[name="frmPaginacion"]')
    pager = soup.select_one('.barraPag')
    cards = soup.select('.listado .noticiaListado')
    if not form or not pager or not cards:
        raise ValueError('Missing archive cards, pagination form or controls')
    fields = {x['name']: x.get('value', '') for x in form.select('input[name]')}
    query = parse_qs(urlparse(url).query)
    for key in ('d', 'h', 'p'):
        if fields.get(key) != query.get(key, ['1' if key == 'p' else ''])[0]:
            raise ValueError('Archive filter/page was not honored')
    current = int(fields['p'])
    items = []
    for card in cards:
        a = card.select_one('h2 a[href]')
        if not a:
            raise ValueError('Archive card lacks article link')
        target = urljoin(url, a['href'])
        if not official_url(target) or not re.fullmatch(r'/actualidad/\d+/[^/]+', urlparse(target).path):
            raise ValueError('Unexpected article URL')
        items.append((a.get_text(' ', strip=True), target))
    pages = []
    for control in pager.select('[onclick]'):
        match = re.fullmatch(r'fncPaginacion\((\d+)\);?', control['onclick'])
        if not match:
            raise ValueError('Unknown pagination control')
        page = int(match[1])
        if page > current:
            if page != current + 1:
                raise ValueError('Archive pagination skips a page')
            pages.append(page)
    if len(pages) > 1:
        raise ValueError('Ambiguous pagination')
    next_url = None
    if pages:
        fields['p'] = str(pages[0])
        next_url = urljoin(url, form.get('action', 'actualidad.php')) + '?' + urlencode(fields)
        if not official_url(next_url) or urlparse(next_url).path != '/actualidad.php':
            raise ValueError('Unexpected pagination destination')
    return items, next_url


def subject(title):
    if re.search(r'licitacion|adjudica|licencia|bases|empleo', norm(title)):
        return None
    for key, title_pattern, _ in SUBJECTS:
        if re.search(title_pattern, norm(title)):
            return key
    return None


def parse_article(html, url, expected_title):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('.listado.noticia')
    if not article or not article.select_one('h2'):
        raise ValueError('Missing article body')
    title = article.select_one('h2').get_text(' ', strip=True)
    if title != expected_title:
        raise ValueError('Article title differs from inventory')
    key = subject(title)
    if key is None:
        return None
    paragraphs = [p.get_text(' ', strip=True) for p in article.find_all('p', recursive=False)]
    pattern = next(rule[2] for rule in SUBJECTS if rule[0] == key)
    evidence = next((p for p in paragraphs if re.search(pattern, norm(p))), None)
    if evidence is None:
        return None  # A subject mention or procurement notice alone is insufficient.
    published = article.select_one('.datosNoticia .fecha .f')
    if not published:
        raise ValueError('Missing publication date')
    doc = {'titulo': title, 'url': url, 'tipo': 'noticia_municipal',
           'fecha_publicacion': publication_date(published.get_text(strip=True)),
           'evidencia_ejecucion': evidence}
    attachments = {}
    for a in article.select('.documentosAdjuntos a[href]'):
        target = urljoin(url, a['href'])
        if official_url(target) and urlparse(target).path.startswith('/ARCHIVO/'):
            attachments[target] = {'titulo': a.get_text(' ', strip=True) or 'Adjunto municipal',
                                   'url': target, 'source_url': url,
                                   'tipo': 'fotografia' if '/fotografias/' in target else 'documento'}
    doc['adjuntos'] = list(attachments.values())
    return key, doc


def group_projects(documents, inventory_url):
    groups = {}
    for key, doc in documents:
        groups.setdefault(key, {})[doc['url']] = doc
    rows = []
    for key, docs in sorted(groups.items()):
        ordered = sorted(docs.values(), key=lambda d: (d['fecha_publicacion'], d['url']))
        first = ordered[0]
        rows.append({'id': 'pozuelo-de-calatrava-obra-' + key,
                     'municipio': 'Pozuelo de Calatrava', 'codigo_ine': '13066',
                     'provincia': 'Ciudad Real', 'titulo': first['titulo'],
                     'tipo': 'obra_publica', 'url': first['url'],
                     'fecha_publicacion': first['fecha_publicacion'],
                     'source': 'ayuntamiento', 'origen': 'noticias_obras_ejecutadas',
                     'inventory_url': inventory_url, 'documentos': ordered,
                     'coverage': 'seleccion_revisada_obras_archivo_2026',
                     'publication_ready': False, 'geometry_status': 'unavailable'})
    if not rows:
        raise ValueError('No verified physical works in reviewed archive')
    return rows


class PozueloDeCalatravaAyuntamientoAdapter(AyuntamientoAdapter):
    """Full pagination within a declared fixed year; update refreshes that same scope."""

    def backfill_proyectos(self, out_jsonl: Path):
        start, end = '20260101', '20261231'
        inventory = ARCHIVE + '?' + urlencode({'d': start, 'h': end, 'p': 1})
        sources, seen_articles, visited, documents = [], set(), set(), []
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            Path(capture_dir).mkdir(parents=True, exist_ok=True)

        def fetch(url):
            response = requests.get(url, timeout=35, headers={
                'User-Agent': 'municipio-pozuelo-de-calatrava/1.0 (public works inventory)'})
            response.raise_for_status()
            if not official_url(response.url):
                raise ValueError('Unexpected source redirect')
            sources.append(url)
            if capture_dir:
                Path(capture_dir, f'live-{len(sources):03d}.html').write_text(response.text, encoding='utf-8')
            return response.text

        url = inventory
        while url:
            if url in visited or len(visited) >= 100:
                raise ValueError('Pagination cycle or unexpected archive growth; no partial output')
            visited.add(url)
            items, next_url = parse_inventory(fetch(url), url)
            for title, article_url in items:
                if article_url in seen_articles:
                    raise ValueError('Repeated archive card across pages')
                seen_articles.add(article_url)
                if subject(title):
                    parsed = parse_article(fetch(article_url), article_url, title)
                    if parsed:
                        if not '2026-01-01' <= parsed[1]['fecha_publicacion'] <= '2026-12-31':
                            raise ValueError('Article outside declared archive year')
                        documents.append(parsed)
            url = next_url
        rows = group_projects(documents, inventory)
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows), 'archive_pages': len(visited),
                'archive_articles': len(seen_articles), 'source_urls': sources,
                'coverage': 'reviewed physical works in complete 2026 news archive'}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
