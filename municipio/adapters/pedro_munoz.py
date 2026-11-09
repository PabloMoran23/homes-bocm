"""Pedro Muñoz: municipal planning documents, not a register of licences."""
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

SOURCE = ('https://www.pedro-munoz.es/category/portal-transparencia/normativa/'
          'normativa-urbanismo-med-ambiente/')
HOSTS = {'www.pedro-munoz.es', 'pedro-munoz.es'}
MONTHS = dict(zip(('enero febrero marzo abril mayo junio julio agosto septiembre '
                   'octubre noviembre diciembre').split(), range(1, 13)))


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn')


def official(url):
    p = urlparse(url)
    return p.scheme in {'http', 'https'} and p.hostname in HOSTS


def instrument(title):
    text = norm(title)
    return (text.startswith('plan de ordenacion municipal') or
            ('convenio urbanistico' in text and 'modificacion puntual' in text))


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, 'html.parser')
    titles = soup.select('h2.entry-title a[href]')
    if not titles:
        raise ValueError('Missing municipal inventory entries')
    entries = {}
    for a in titles:
        title = a.get_text(' ', strip=True)
        target = urljoin(url, a['href']).split('#')[0]
        if instrument(title):
            if not official(target) or not urlparse(target).path.startswith('/urbanismo/'):
                raise ValueError('Unexpected instrument URL')
            entries[target] = title
    pages = set()
    for a in soup.select('.penci-pagination a[href], .pagination a[href], '
                         'a.page-numbers[href], a[rel=next], a[rel=prev]'):
        target = urljoin(url, a['href']).split('#')[0]
        if not official(target) or not urlparse(target).path.startswith(urlparse(SOURCE).path):
            raise ValueError('Unexpected pagination URL')
        pages.add(target)
    if soup.select('.penci-ajax-more-button, .penci-load-more, [data-nextpage]'):
        raise ValueError('Unsupported dynamic pagination; review before extracting')
    return entries, pages


def parse_detail(html, url, expected_title):
    soup = BeautifulSoup(html, 'html.parser')
    heading = soup.select_one('h1.entry-title')
    body = soup.select_one('#penci-post-entry-inner.entry-content')
    if not heading or not body or not body.get_text(' ', strip=True):
        raise ValueError('Missing instrument title or body')
    title = heading.get_text(' ', strip=True)
    if norm(title) != norm(expected_title) or not instrument(title):
        raise ValueError('Detail does not match inventory')
    # First published timestamp belongs to the main heading, before related posts.
    stamp = heading.find_next('time', class_='published')
    if not stamp or not stamp.get('datetime'):
        raise ValueError('Missing explicit publication timestamp')
    published = date.fromisoformat(stamp['datetime'][:10]).isoformat()
    text = body.get_text(' ', strip=True)
    convenio = 'convenio urbanistico' in norm(title)
    docs = [{'titulo': title, 'url': url, 'tipo': 'texto_municipal_html',
             'source_url': url}]
    seen = set()
    for a in body.select('a[href]'):
        raw = a['href']
        cleaned = re.sub(r'\s+', '', raw)
        target = urljoin(url, cleaned)
        if not urlparse(target).path.lower().endswith('.pdf'):
            continue
        if target in seen:
            continue
        seen.add(target)
        doc = {'titulo': a.get_text(' ', strip=True), 'href_original': raw,
               'source_url': url}
        if official(target):
            doc.update(url=target, tipo='pdf', enlace_status='publicado_no_verificado')
        else:
            # The 2020 page actually publishes //images/documentos/..., not a
            # municipal download URL. Preserve it without inventing a repair.
            doc.update(url=None, tipo='pdf', enlace_status='enlace_no_municipal_o_malformado')
        docs.append(doc)
    if not convenio and not seen:
        raise ValueError('POM lacks published documents')
    row = {
        'id': 'pedro-munoz-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Pedro Muñoz', 'provincia': 'Ciudad Real', 'codigo_ine': '13061',
        'titulo': title, 'tipo': 'convenio_urbanistico' if convenio else 'plan_ordenacion_municipal',
        'url': url, 'inventory_url': SOURCE, 'source': 'ayuntamiento',
        'origen': 'inventario_normativa_urbanistica', 'fecha_publicacion': published,
        'descripcion': text, 'documentos': docs,
        'publication_ready': False, 'geometry_status': 'unavailable',
        'cobertura': 'Inventario documental parcial; sin verificación de vigencia ni aprobación definitiva.',
    }
    # Only the explicit opening statement of a plenary session supplies an
    # agreement date. Proposal/report dates later in the text are not used.
    match = re.search(r'sesi[oó]n\s+ordinaria\s+celebrada.{0,65}?el d[ií]a\s+'
                      r'(\d{1,2}) de (\w+) de (\d{4})', text[:650], re.I)
    if convenio and match:
        day, month, year = match.groups()
        row['fecha_acuerdo'] = date(int(year), MONTHS[norm(month)], int(day)).isoformat()
        row['fecha_acuerdo_fuente'] = {'url': url, 'texto': match.group(0),
                                      'alcance': 'Acuerdo del convenio; no aprobación definitiva de la modificación del POM.'}
    return row


class PedroMunozAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        if not official(url):
            raise ValueError('Non-municipal source')
        response = requests.get(url, timeout=45, headers={
            'User-Agent': 'municipio-pedro-munoz/1.0 (public planning inventory)'})
        response.raise_for_status()
        if not official(response.url):
            raise ValueError('Unexpected source redirect')
        response.encoding = response.apparent_encoding
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(
                response.text, encoding='utf-8')
        self.source_urls.append(url)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        pending, visited, entries = {SOURCE}, set(), {}
        while pending:
            url = sorted(pending)[0]
            pending.remove(url)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Pagination safety limit reached; no partial output written')
            found, pages = parse_inventory(self._fetch(url), url)
            visited.add(url)
            entries.update(found)
            pending.update(pages - visited)
        if not entries:
            raise ValueError('No usable municipal planning instruments')
        rows = [parse_detail(self._fetch(url), url, title)
                for url, title in sorted(entries.items())]
        return {**self._write(out_jsonl, rows), 'source_urls': self.source_urls,
                'inventory_pages': len(visited), 'coverage': 'partial_planning_document_inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
