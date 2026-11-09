"""Gelida's municipal planning inventory (planning instruments only)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.gelida.cat/ajuntament/urbanisme-i-territori/planejament-urbanistic-i-projectes'
MONTHS = 'gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split()


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def planning_title(title):
    text = norm(re.sub(r'^\d{6}_', '', title).strip())
    if any(word in text for word in ('conveni', 'estatuts', 'reparcel', 'redaccio', 'projecte')):
        # AGROPARC's modification title mentions the underlying project.
        if not text.startswith('agroparc_aprovacio provisional de la modificacio del poum'):
            return False
    return text == 'poum' or bool(re.search(r'\bpoum\b|p\.g\.o\.m|pla (especial|parcial)', text))


def catalan_date(text):
    match = re.search(r"(\d{1,2})\s+(?:de\s+|d[’'])?(\w+)\s+de\s+(\d{4})", text.lower())
    if not match or match[2] not in MONTHS:
        return None
    return date(int(match[3]), MONTHS.index(match[2]) + 1, int(match[1])).isoformat()


class GelidaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.gelida.cat')

    @staticmethod
    def parse_inventory(html, page_url=SOURCE):
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.select_one('#readspeakerPage h1')
        if not heading or heading.get_text(' ', strip=True) != 'Planejament urbanístic i projectes':
            raise ValueError('Unexpected Gelida inventory heading')
        items = soup.select('.articlelist > .article-item')
        if not items:
            raise ValueError('Empty or changed Gelida inventory')
        rows = []
        for item in items:
            anchor = item.select_one('.tplDefault > a[href]')
            stamp = item.select_one('.date')
            if not anchor or not stamp:
                raise ValueError('Inventory entry lacks title or publication date')
            title = anchor.get_text(' ', strip=True)
            url = urljoin(page_url, anchor['href'])
            if urlparse(url).hostname != 'www.gelida.cat' or not url.startswith(SOURCE + '/'):
                raise ValueError('Unexpected municipal detail URL')
            if planning_title(title):
                rows.append({'titulo': title, 'url': url,
                             'fecha_publicacion': datetime.strptime(stamp.get_text(strip=True), '%d/%m/%Y').date().isoformat(),
                             'inventory_url': page_url})
        pages = {SOURCE}
        for anchor in soup.select('.paginacio a[href]'):
            url = urljoin(page_url, anchor['href'])
            if url.split('?')[0] != SOURCE:
                raise ValueError('Unexpected pagination URL')
            query = parse_qs(urlparse(url).query)
            if query and (set(query) != {'pag'} or not re.fullmatch(r'[1-9]\d*', query['pag'][0])):
                raise ValueError('Unsupported pagination')
            pages.add(url)
        totals = {int(n) for n in re.findall(r'(\d+)\s+pàgines', soup.get_text(' ', strip=True))}
        if len(totals) != 1:
            raise ValueError('Missing or ambiguous page count')
        return rows, pages, totals.pop()

    @staticmethod
    def parse_detail(html, entry):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('#readspeakerPage')
        heading = main.select_one('h1') if main else None
        if not heading or heading.get_text(' ', strip=True) != entry['titulo']:
            raise ValueError('Detail title differs from inventory')
        narrative = '\n'.join(x.get_text(' ', strip=True) for x in main.select('.ddbbtext'))
        docs = {}
        for anchor in soup.select('main .documents a[href], #readspeakerPage .ddbbtext a[href]'):
            linked_url = urljoin(entry['url'], anchor['href'])
            url = linked_url
            if urlparse(url).hostname and urlparse(url).hostname.endswith('.safelinks.protection.outlook.com'):
                url = parse_qs(urlparse(url).query).get('url', [''])[0]
            parsed = urlparse(url)
            if parsed.hostname not in {'www.gelida.cat', 'bpm.gelida.cat'}:
                continue
            if not (parsed.path.startswith('/media/repository/') or parsed.path.startswith('/OAC/')):
                continue
            docs.setdefault(url, {'titulo': anchor.get_text(' ', strip=True), 'url': url,
                                  'url_enlace_original': linked_url, 'source_url': entry['url']})
        approval = dogc = None
        # Only the base POUM has reviewed, explicit narrative dates. Filename
        # prefixes and the page's publication timestamp are never approval dates.
        if entry['titulo'] == 'POUM':
            match = re.search(r'Aprovat definitivament.*? el (.*?), i publicat en el DOGC.*? el ([^\n]+)', narrative)
            if not match:
                raise ValueError('POUM approval narrative changed')
            approval, dogc = catalan_date(match[1]), catalan_date(match[2])
            if not approval or not dogc:
                raise ValueError('Unparseable explicit POUM dates')
        elif not docs:
            raise ValueError('Planning instrument has no document links')
        return {
            **entry, 'id': 'gelida-plan-' + hashlib.sha256(entry['url'].encode()).hexdigest()[:16],
            'municipio': 'Gelida', 'codigo_ine': '08091', 'provincia': 'Barcelona',
            'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación definitiva' if approval else None,
            'fecha': None, 'fecha_acuerdo': None, 'fecha_aprob': approval,
            'fecha_publicacion_dogc': dogc, 'descripcion': narrative or None,
            'documentos': list(docs.values()), 'url_documento': next(iter(docs), None),
            'source': 'ayuntamiento', 'origen': 'inventario_municipal_planeamiento',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'limitaciones': 'Cobertura parcial: instrumentos de planeamiento; sin geometría ni comprobación de vigencia. Fases de otras fichas no normalizadas; fechas de acuerdos desconocidas.',
        }

    def _fetch(self, url):
        response = requests.get(url, timeout=(10, 40), stream=True,
                                headers={'User-Agent': 'municipio-gelida/1.0'})
        with response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'www.gelida.cat':
                raise ValueError('Unexpected source redirect')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 5_000_000:
                    raise ValueError('Source exceeds response limit')
            html = data.decode('utf-8')
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir'])
            path.mkdir(parents=True, exist_ok=True)
            (path / (hashlib.sha256(url.encode()).hexdigest() + '.html')).write_text(html, encoding='utf-8')
        return html

    def backfill_proyectos(self, out_jsonl):
        pending, visited, entries, totals = {SOURCE}, set(), {}, set()
        signatures = set()
        while pending:
            url = min(pending)
            pending.remove(url)
            html = self._fetch(url)
            rows, pages, total = self.parse_inventory(html, url)
            signature = BeautifulSoup(html, 'html.parser').select_one('.articlelist').get_text(' ', strip=True)
            if signature in signatures:
                raise ValueError('Repeated inventory page; pagination may have been ignored')
            signatures.add(signature)
            visited.add(url)
            totals.add(total)
            if total > 100 or len(visited) > 100:
                raise ValueError('Pagination exceeds safety bound; no output written')
            pending.update(pages - visited)
            for row in rows:
                if row['url'] in entries and entries[row['url']]['fecha_publicacion'] != row['fecha_publicacion']:
                    raise ValueError('Conflicting duplicate instrument dates')
                entries.setdefault(row['url'], row)
        if totals != {len(visited)}:
            raise ValueError('Incomplete pagination')
        if not entries:
            raise ValueError('No planning instruments found')
        rows = [self.parse_detail(self._fetch(url), entry) for url, entry in sorted(entries.items())]
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'inventory_pages': len(visited),
                'source_urls': sorted(visited | set(entries)), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register; forms excluded'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
