"""Official works reports since 2026; complete AJAX archive traversal, partial thematic coverage."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://herencia.es/seccion/noticias/obras-urbanismo'
AJAX = 'https://herencia.es/wp-admin/admin-ajax.php'
SINCE = '2026-01-01'


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def official(url):
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'herencia.es':
        raise ValueError(f'Unexpected source URL: {url}')
    return url


def parse_cards(html):
    soup = BeautifulSoup(html, 'html.parser')
    cards = {}
    for a in soup.select('.edgtf-post-item h3 a[href], .edgtf-post-item h5 a[href], .edgtf-post-example-item-three-title a[href]'):
        url = official(urljoin(SOURCE, a['href']).split('#')[0])
        cards[url] = a.get_text(' ', strip=True)
    if not cards:
        raise ValueError('Missing archive cards')
    return cards


def parse_archive(html):
    soup = BeautifulSoup(html, 'html.parser')
    holder = soup.select_one('[data-base="edgtf_post_layout_small"]')
    if holder is None:
        raise ValueError('Missing AJAX pagination metadata')
    params = {k[5:]: v for k, v in holder.attrs.items() if k.startswith('data-')}
    pages = int(params['max_pages'])
    if pages < 1 or params.get('category_id') != '15' or params.get('paged') != '1':
        raise ValueError('Unexpected category/pagination')
    return parse_cards(html), params, pages


def candidate(title):
    t = norm(title)
    if re.search(r'licitacion|adjudica|autoriza|convocatoria|bolsa de empleo|balance|terrenos.*viviendas', t):
        return False
    return bool(re.search(r'se renueva|se reabre|se ejecutan las obras|recupera.*trabajos de restauracion|'
                          r'se integra.*semipeatonal|se implementa.*red de riego|instalacion de placas solares|'
                          r'se inician las obras|acta de replanteo.*fase ii|instala un sistema de placas solares|'
                          r'actuaciones.*pedriza', t))


def parse_report(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.select_one('h2.entry-title')
    body = soup.select_one('.edgtf-post-text-inner')
    published = soup.select_one('meta[property="article:published_time"]')
    if title is None or body is None or published is None:
        raise ValueError(f'Missing report structure: {url}')
    title = title.get_text(' ', strip=True)
    when = date.fromisoformat(published['content'][:10]).isoformat()
    if when < SINCE or not candidate(title):
        return None
    text = body.get_text(' ', strip=True)
    if re.search(r'para licitar las obras|abierta la licitaci[oó]n|salen a licitaci[oó]n', text, re.I):
        return None
    if not re.search(r'obras|trabajos|instala|construcci[oó]n|actuaci[oó]n|restauraci[oó]n', text, re.I):
        raise ValueError('Selected report lacks physical intervention evidence')
    docs = [{'titulo': title, 'url': official(url), 'tipo': 'noticia_municipal', 'fecha_publicacion': when}]
    for a in body.select('a[href]'):
        target = urljoin(url, a['href'])
        if urlparse(target).path.lower().endswith('.pdf'):
            docs.append({'titulo': a.get_text(' ', strip=True), 'url': target, 'tipo': 'documento_enlazado', 'pagina_origen': url})
    # Two named interventions have both start and completion/funding reports in this archive.
    t = norm(title)
    group = ('calle-concepcion-2026' if 'calle concepcion' in t else
             'pedriza-2026' if ('pedriza' in t or 'copa' in t) else url)
    return {'group': group, 'titulo': title, 'fecha_publicacion': when, 'url': url,
            'descripcion': text, 'documentos': docs}


def group_reports(reports):
    groups = {}
    for report in sorted(reports, key=lambda r: (r['fecha_publicacion'], r['url'])):
        key = report['group']
        if key not in groups:
            groups[key] = {'id': 'herencia-obra-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                           'municipio': 'Herencia', 'provincia': 'Ciudad Real', 'codigo_ine': '13047',
                           'titulo': report['titulo'], 'tipo': 'obra_publica', 'url': report['url'],
                           'fecha_publicacion': report['fecha_publicacion'],
                           'source': 'ayuntamiento', 'origen': 'noticia_municipal_obras',
                           'inventory_url': SOURCE, 'publication_ready': False,
                           'geometry_status': 'unavailable', 'documentos': [], 'reportes': []}
        row = groups[key]
        row['reportes'].append({k: v for k, v in report.items() if k not in {'group', 'documentos'}})
        for doc in report['documentos']:
            if doc['url'] not in {d['url'] for d in row['documentos']}:
                row['documentos'].append(doc)
    return list(groups.values())


class HerenciaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        session = requests.Session()
        session.headers['User-Agent'] = 'municipio-herencia/1.0 (public municipal works inventory)'
        captures = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        source_urls = [SOURCE]

        def fetch(url, label, data=None):
            official(url)
            response = session.get(url, timeout=40) if data is None else session.post(url, data=data, timeout=40)
            response.raise_for_status()
            official(response.url)
            if captures:
                captures.mkdir(parents=True, exist_ok=True)
                (captures / label).write_text(response.text, encoding='utf-8')
            return response

        first = fetch(SOURCE, 'archive-1.html')
        cards, params, pages = parse_archive(first.text)
        signatures = {frozenset(cards)}
        for page in range(2, pages + 1):
            payload = {**params, 'action': 'magazinevibe_edge_list_ajax', 'paged': page}
            response = fetch(AJAX, f'archive-{page}.json', payload).json()
            if response.get('showNextPage') is not True:
                raise ValueError(f'Pagination stopped before advertised page {page}/{pages}')
            new = parse_cards(response['html'])
            signature = frozenset(new)
            if signature in signatures or not (set(new) - set(cards)):
                raise ValueError(f'Repeated archive page {page}')
            signatures.add(signature)
            cards.update(new)
        source_urls.append(AJAX)
        reports = []
        for url, title in sorted(cards.items()):
            if not candidate(title):
                continue
            label = 'report-' + hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
            report = parse_report(fetch(url, label).text, url)
            source_urls.append(url)
            if report:
                reports.append(report)
        rows = group_reports(reports)
        if not rows:
            raise ValueError('No usable physical works reports since ' + SINCE)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(output)
        return {'count': len(rows), 'live_records': len(rows), 'archive_pages': pages,
                'archive_cards': len(cards), 'selected_reports': len(reports), 'source_urls': source_urls,
                'coverage': 'selected physical works reported since 2026-01-01; full category pagination'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {'count': 0, 'disabled': True, 'reason': 'No verified register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
