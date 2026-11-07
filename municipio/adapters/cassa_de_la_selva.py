"""Complete snapshot of the municipal works-document inventory, not licences."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://repo.cassa.cat/urbanisme/projectesobra/'
MUNICIPAL_SOURCE = 'https://www.cassa.cat/index.php/ajuntament/poble-urbanisme/urbanisme-projectes-d-obra'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _bop_date(label):
    # Only an explicitly labelled BOP publication date, never an agreement date.
    if not label.startswith('BOP '):
        return None
    match = re.search(r'de data (\d{1,2}) (?:de |d[’\'])(' + '|'.join(MONTHS) + r') de (\d{4})', label)
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat() if match else None


class CassaDeLaSelvaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.cassa.cat')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.select_one('h1#titol')
        if not heading or _text(heading) != "Projectes d'obra":
            raise ValueError('Municipal works inventory missing; refusing navigation/login content')
        # Reviewed source is one complete static page. Fail if pagination appears.
        if soup.select('.pagination, .pagenav, [rel~=next], [rel~=prev]'):
            raise ValueError('Inventory pagination requires crawler review')
        for a in soup.select('a[href]'):
            label = _text(a).lower()
            if label in {'next', 'següent', 'següents', 'siguiente', 'anterior', 'més', 'carrega més'} or re.search(r'[?&](?:page|start|offset)=', a['href']):
                raise ValueError('Inventory pagination requires crawler review')
        rows = {}
        headings = soup.select('h2')
        if not headings:
            raise ValueError('No works sections found')
        for h in headings:
            title = _text(h)
            # An administrative service-cost structure is not a physical project.
            if 'estructura de costos' in title.lower():
                continue
            if not re.match(r'^(?:Obra |Aprovació (?:de la )?memòria valorada |Millora asfaltatge |Actualització del projecte |Projecte |Memòria [Vv]alorada |Modificació instal·lació |Text refos del projecte |Reforma del gimnàs)', title):
                raise ValueError(f'Unreviewed inventory section: {title}')
            block = h.find_next_sibling()
            if block is None or block.name != 'ul':
                raise ValueError(f'Missing document group: {title}')
            docs = {}
            identifiers = set()
            for a in block.select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                parts = urlsplit(url)
                if parts.scheme != 'https' or parts.netloc != 'repo.cassa.cat' or not parts.path.startswith('/urbanisme/projectesobra/') or not parts.path.lower().endswith('.pdf') or parts.query:
                    raise ValueError(f'Unexpected document URL: {url}')
                url = quote(unquote(url), safe=':/')
                ids = re.findall(r'(?<![A-Z0-9])[XE]\d{10}(?!\d)', unquote(parts.path))
                if len(ids) != 1:
                    raise ValueError(f'Missing/ambiguous source expediente: {url}')
                identifiers.update(ids)
                label = _text(a)
                docs[url] = {'titulo': label, 'url': url, 'source_url': SOURCE,
                             'fecha_publicacion': _bop_date(label)}
            if len(identifiers) != 1 or not docs:
                raise ValueError(f'Missing/conflicting documents: {title}')
            expediente = next(iter(identifiers))
            if expediente not in rows:
                rows[expediente] = {
                    'id': 'cassa-de-la-selva-proy-' + expediente,
                    'municipio': 'Cassà de la Selva', 'codigo_ine': '17044',
                    'provincia': 'Girona', 'expediente': expediente,
                    'titulo': title, 'titulos_fuente': [],
                    'tipo': 'proyecto de obra', 'fase': None,
                    'fecha': None, 'fecha_publicacion': None,
                    'fecha_acuerdo': None, 'fecha_aprob': None,
                    'url': SOURCE, 'source': 'ayuntamiento',
                    'origen': 'inventario_municipal_projectes_obra',
                    'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                    'publication_ready': False,
                    'geometry_status': 'No verified project geometry extracted',
                }
            row = rows[expediente]
            if title not in row['titulos_fuente']:
                row['titulos_fuente'].append(title)
            existing = {d['url']: d for d in row['documentos']}
            existing.update(docs)
            row['documentos'] = list(existing.values())
        if not rows:
            raise ValueError('No genuine physical projects found')
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'municipio-cassa-de-la-selva/1.0'}, stream=True)
        with response:
            response.raise_for_status()
            chunks = []
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 2_000_000:
                    raise ValueError('Inventory exceeds reviewed response size')
                chunks.append(chunk)
            html = b''.join(chunks).decode('utf-8-sig')
        rows = self.parse_projects(html)
        # Optional local capture; only after a valid complete parse.
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'works-live.html').write_text(html, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [MUNICIPAL_SOURCE, SOURCE],
                'coverage': 'complete current works index; partial municipal coverage',
                'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # No date cursor: refresh every section, including changed attachments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
