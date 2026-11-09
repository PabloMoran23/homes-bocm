"""Snapshot of physical works in Anglès' public municipal project inventory."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://som.angles.cat/projectes/llistat'
LIMITATIONS = [
    'Partial municipal coverage: legacy Som.Anglès project inventory, not a current works or licence register.',
    'Social inclusion and community mediation programmes excluded; no general news or procurement scraping.',
    'Linked documents retained with municipal-page provenance; their availability/content is not verified.',
    'No approval/agreement dates or geometry verified; publication dates are page publication dates.',
    'Node 162 reports an end date before its start date; source values retained with quality warning.',
]


def _text(node):
    return node.get_text(' ', strip=True) if node else ''


def _local(url):
    p = urlparse(url)
    if p.scheme != 'https' or p.netloc != 'som.angles.cat':
        raise ValueError('Unexpected inventory/detail host: ' + url)
    return url


def _write(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    tmp.replace(path)


class AnglesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://som.angles.cat')

    @staticmethod
    def parse_inventory(html, page_url=SOURCE):
        soup = BeautifulSoup(html, 'html.parser')
        articles = soup.select('.view-content article.node-projecte')
        if not articles:
            raise ValueError('Missing municipal project inventory')
        entries = []
        for article in articles:
            a = article.select_one('h2 a[href]')
            node_id = article.get('id', '')
            if not a or not re.fullmatch(r'node-\d+', node_id):
                raise ValueError('Invalid project inventory entry')
            title = _text(a)
            # This inventory also includes programmes without any physical works.
            if title.startswith(('Projecte d´Acció Social', 'Polítiques d´habitatge')):
                included = False
            elif title.startswith(('Rehabilitació dels habitatges', 'Reforma dels lavabos',
                                   'Connexió de les aigües residuals', 'Adequació dels locals')):
                included = True
            else:
                raise ValueError('Unreviewed project category: ' + title)
            url = _local(urljoin(page_url, a['href']))
            if not re.fullmatch(r'/(?:projecte/[^/?#]+|node/\d+)', urlparse(url).path):
                raise ValueError('Unexpected project detail path')
            entries.append({'node_id': node_id, 'titulo': title, 'url': url, 'included': included})
        pages = set()
        # Follow every linked pager page, not just the first page or next arrow.
        for a in soup.select('.pager a[href], a[rel~=next]'):
            url = _local(urljoin(page_url, a['href']))
            if urlparse(url).path not in {'/projectes', '/projectes/llistat'}:
                raise ValueError('Unexpected inventory pagination path')
            pages.add(url)
        return entries, sorted(pages)

    @staticmethod
    def parse_project(html, entry):
        soup = BeautifulSoup(html, 'html.parser')
        articles = soup.select('#main-content article.node-projecte')
        title = _text(soup.select_one('h1.page-title'))
        if len(articles) != 1 or articles[0].get('id') != entry['node_id'] or title != entry['titulo']:
            raise ValueError('Project detail identity mismatch')
        article = articles[0]
        body = article.select_one('.field-name-body .field-items')
        description = _text(body)
        if not description or not re.search(r'\b(?:obres|obra|rehabilitar)\b', description, re.I):
            raise ValueError('No physical works narrative in project detail')
        submitted = _text(article.select_one('.submitted'))
        match = re.search(r'Publicat .*? (\d{2}/\d{2}/\d{4})', submitted)
        publication = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat() if match else None

        def field_date(name):
            raw = _text(article.select_one(f'.field-name-field-projecte-{name} .date-display-single'))
            return datetime.strptime(raw, '%d/%m/%Y').date().isoformat() if raw else None

        start, end = field_date('inici'), field_date('fi')
        warnings = ['Source end date precedes start date; neither value corrected'] if start and end and end < start else []
        links, documents = {}, {}
        for a in article.select('.field-name-body a[href], .field-name-field-projecte-documentacio a[href]'):
            url = urljoin(entry['url'], a['href'])
            if urlparse(url).scheme not in {'https', 'http'}:
                continue
            link = {'titulo': _text(a), 'url': url, 'source_url': entry['url'], 'content_verified': False}
            links.setdefault(url, link)
            if '.pdf' in urlparse(url).path.lower() or '/download/' in urlparse(url).path or a.find_parent(class_='field-name-field-projecte-documentacio'):
                documents.setdefault(url, link)
        return {
            'id': 'angles-proy-' + entry['node_id'], 'municipio': 'Anglès', 'codigo_ine': '17008',
            'provincia': 'Girona', 'titulo': title, 'tipo': 'obra_publica', 'fase': None,
            'fecha': None, 'fecha_publicacion': publication, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'fecha_inicio': start, 'fecha_fin': end, 'descripcion': description,
            'url': entry['url'], 'source': 'ayuntamiento', 'origen': 'inventario_municipal_proyectos',
            'source_inventory': SOURCE, 'source_node_id': entry['node_id'],
            'documentos': list(documents.values()), 'enlaces_relacionados': list(links.values()),
            'quality_warnings': warnings, 'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'geometry_status': 'No verified project geometry in source',
        }

    def _fetch(self, url):
        _local(url)
        response = requests.get(url, timeout=30, headers={'User-Agent': 'municipio-angles/1.0'}, stream=True)
        with response:
            response.raise_for_status()
            _local(response.url)
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 5_000_000:
                    raise ValueError('Source exceeds response size limit')
            html = content.decode('utf-8')
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha256(url.encode()).hexdigest()[:16]
            (folder / (key + '.html')).write_text(html, encoding='utf-8')
        return html

    def backfill_proyectos(self, out_jsonl):
        pending, visited, entries = [SOURCE], set(), {}
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError('Pagination exceeds safety limit; no partial snapshot written')
            page_entries, pages = self.parse_inventory(self._fetch(url), url)
            visited.add(url)
            for entry in page_entries:
                previous = entries.setdefault(entry['node_id'], entry)
                if previous != entry:
                    raise ValueError('Conflicting duplicate project identity')
            pending.extend(p for p in pages if p not in visited and p not in pending)
        rows = [self.parse_project(self._fetch(e['url']), e) for e in entries.values() if e['included']]
        if not rows:
            raise ValueError('No usable physical projects; no snapshot written')
        _write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'inventory_entries': len(entries),
                'excluded': [e for e in entries.values() if not e['included']],
                'source_urls': sorted(visited | {e['url'] for e in entries.values() if e['included']}),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot; no time filter loses historically published works.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        _write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
