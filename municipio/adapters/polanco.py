"""Municipal planning catalogue; one record per unambiguous instrument page."""
from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOME = 'https://www.aytopolanco.org/'
CATALOGUE = HOME + 'planeamiento/'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def canonical(url):
    parts = urlsplit(url)
    if parts.hostname != 'www.aytopolanco.org' or parts.scheme not in ('http', 'https'):
        raise ValueError(f'Unexpected municipal source: {url}')
    return urlunsplit(('https', parts.netloc, quote(unquote(parts.path), safe='/'), parts.query, ''))


def check_pagination(soup):
    # These are static WordPress pages. Fail on pagination rather than quietly
    # turning a newly paginated catalogue/document list into a partial snapshot.
    if soup.select('[rel~=next], .page-numbers, .page-links, .pagination'):
        raise ValueError('Pagination detected; catalogue traversal needs review')
    for a in soup.select('a[href]'):
        if a.get_text(' ', strip=True).casefold() in {'siguiente', 'next', 'siguientes', 'más resultados'}:
            raise ValueError('Pagination detected; catalogue traversal needs review')


def boc_date(text):
    if 'BOC' not in text.upper():
        return None
    match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if match:
        day, month, year = map(int, match.groups())
    else:
        match = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', text.lower())
        if not match or match[2] not in MONTHS:
            return None
        day, month, year = int(match[1]), MONTHS.index(match[2]) + 1, int(match[3])
    return date(year, month, day).isoformat()


class PolancoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        check_pagination(soup)
        parents = [a.parent for a in soup.select('li > a[href]')
                   if urljoin(HOME, a['href']).rstrip('/') == CATALOGUE.rstrip('/')]
        links = {}
        for parent in parents:
            submenu = parent.find('ul', recursive=False)
            if submenu is None:
                raise ValueError('Planeamiento submenu missing')
            for a in submenu.select('a[href]'):
                url = canonical(urljoin(HOME, a['href']))
                if not url.startswith(CATALOGUE) or url == CATALOGUE:
                    raise ValueError('Unexpected catalogue child')
                links[url] = a.get_text(' ', strip=True)
        if not links:
            raise ValueError('Municipal Planeamiento menu missing or empty')
        return links

    @staticmethod
    def parse_detail(html, url):
        soup = BeautifulSoup(html, 'html.parser')
        check_pagination(soup)
        title = soup.select_one('main h1.entry-title')
        content = soup.select_one('main .entry-content')
        if not title or not content:
            raise ValueError(f'Planning detail markup missing: {url}')
        title = title.get_text(' ', strip=True)
        if not re.match(r'^(Plan General|Modificación puntual|Estudio de detalle|Plan Parcial)', title, re.I):
            raise ValueError(f'Unreviewed instrument type: {title}')
        documents = {}
        approval_publications = set()
        for a in content.select('a[href]'):
            raw_url = urljoin(url, a['href'])
            if not urlsplit(raw_url).path.lower().endswith('.pdf'):
                raise ValueError(f'Unreviewed non-PDF detail link: {raw_url}')
            doc_url = canonical(raw_url)
            label = a.get_text(' ', strip=True)
            heading = a.find_previous(['h2', 'h3'])
            section = heading.get_text(' ', strip=True) if heading and heading in content.descendants else None
            published = boc_date(label)
            documents.setdefault(doc_url, {
                'titulo': label, 'url': doc_url, 'url_original': raw_url,
                'seccion': section, 'pagina_fuente': url,
                'fecha_publicacion': published,
            })
            context = (section or '') + ' ' + label
            if published and 'aprobación definitiva' in context.casefold() and 'corrección' not in label.casefold():
                approval_publications.add(published)
        if not documents:
            raise ValueError(f'No supporting planning documents: {url}')
        # The URB-10 page mixes labels for URB10 with PDF filenames URB-8.
        # Do not assert these documents belong to a single verified instrument.
        sector = re.search(r'URB[-_ ]*(\d+)', title, re.I)
        if sector and any(re.search(r'URB[-_ ]*(?!' + re.escape(sector[1]) + r'\b)\d+', unquote(d['url']), re.I)
                          for d in documents.values()):
            return None
        if len(approval_publications) > 1:
            raise ValueError(f'Ambiguous approval publication dates: {url}')
        if title.lower().startswith('modificación'):
            kind = 'modificacion_planeamiento'
        elif title.lower().startswith('estudio'):
            kind = 'estudio_de_detalle'
        else:
            kind = 'planeamiento_urbanistico'
        published = next(iter(approval_publications), None)
        return {
            'id': 'polanco-proy-' + urlsplit(url).path.rstrip('/').split('/')[-1],
            'municipio': 'Polanco', 'codigo_ine': '39054', 'provincia': 'Cantabria',
            'titulo': title, 'tipo': kind,
            'fase': 'aprobación definitiva' if published else None,
            'fecha': None, 'fecha_publicacion': published,
            'fecha_publicacion_tipo': 'BOC del anuncio de aprobación definitiva' if published else None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': url, 'source': 'ayuntamiento', 'origen': 'catalogo_planeamiento',
            'documentos': list(documents.values()),
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }

    def _fetch(self, session, url):
        with session.get(url, timeout=35, stream=True) as response:
            response.raise_for_status()
            if canonical(response.url) != canonical(url):
                raise ValueError(f'Unexpected redirect: {url} -> {response.url}')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 5_000_000:
                    raise ValueError('Municipal HTML exceeds reviewed response bound')
            html = body.decode('utf-8')
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = urlsplit(url).path.rstrip('/').split('/')[-1] or 'home'
            (directory / (name + '.html')).write_text(html, encoding='utf-8')
        return html

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows, excluded = [], []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-polanco/1.0'
            inventory = self.parse_inventory(self._fetch(session, HOME))
            for url in inventory:
                time.sleep(.2)
                row = self.parse_detail(self._fetch(session, url), url)
                if row is None:
                    excluded.append({'url': url, 'reason': 'Conflicting URB sector in title and document filenames'})
                else:
                    rows.append(row)
        if not rows:
            raise ValueError('No usable planning instruments')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_count': len(inventory),
                'source_urls': [HOME, *inventory], 'excluded': excluded,
                'coverage': 'Current municipal planning menu, not a complete historical register'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
