"""Ordizia's published planning documents; deliberately partial municipal coverage."""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.ordizia.eus'
INVENTORY = BASE + '/es/ayuntamiento/el-ayuntamiento/urbanismo'
PLAN = BASE + '/es/plan-general-de-ordenacion-urbana'


def official_url(href, base=BASE):
    url = urljoin(base, href)
    if urlparse(url).hostname != 'www.ordizia.eus' or urlparse(url).scheme != 'https':
        raise ValueError('Unexpected non-municipal source link')
    return url


def api_url(view, category):
    return f'{BASE}/index.php?option=com_dropfiles&view={view}&format=json&id={int(category)}'


def no_pagination(soup):
    # These sources are full pages/tree responses. Fail closed if this changes.
    if soup.select('.pagination, [rel="next"], [rel="prev"]'):
        raise ValueError('Unexpected pagination: implement traversal before accepting output')


def record(identifier, title, url, kind):
    return {
        'id': 'ordizia-proy-' + identifier, 'municipio': 'Ordizia',
        'codigo_ine': '20076', 'provincia': 'Gipuzkoa',
        'titulo': title, 'tipo': kind, 'url': url,
        'source': 'ayuntamiento', 'origen': 'documentacion_planeamiento_municipal',
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'lat': None, 'lon': None, 'geometry': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
    }


class OrdiziaAyuntamientoAdapter(AyuntamientoAdapter):
    """Refresh two current documentary inventories, never the news/procurement feed."""

    def __init__(self, slug='ordizia', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('#sp-main-body')
        if main is None:
            raise ValueError('Missing municipal Urbanismo content')
        no_pagination(main)
        plans = []
        rows = {}
        for a in main.select('a[href]'):
            title = a.get_text(' ', strip=True)
            if title.casefold() == 'revisión del plan general':
                plans.append(official_url(a['href'], INVENTORY))
            # A document link named for a concrete instrument, not a licence form.
            if not re.match(r'^Estudio de detalle\s+["“\w]', title, re.I):
                continue
            url = official_url(a['href'], INVENTORY)
            if not urlparse(url).path.lower().endswith('.pdf'):
                raise ValueError('Study link is no longer a direct source document')
            key = re.sub(r'\s+', ' ', title).casefold()
            row = rows.setdefault(key, record(
                hashlib.sha256(key.encode()).hexdigest()[:16], title,
                INVENTORY, 'estudio_de_detalle'))
            doc = {'titulo': title, 'url': url, 'source_url': INVENTORY}
            if doc not in row.setdefault('documentos', []):
                row['documentos'].append(doc)
        if set(plans) != {PLAN} or not rows:
            raise ValueError('Reviewed planning inventory missing or changed')
        return list(rows.values())

    @staticmethod
    def parse_plan(html, fetch_json):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('#sp-main-body')
        if main is None:
            raise ValueError('Missing PGOU content')
        no_pagination(main)
        roots = main.select('.dropfiles-content-tree[data-category]')
        if len(roots) != 1:
            raise ValueError('Expected one PGOU document tree')
        root = roots[0]
        heading = root.select_one('.tree-category-title')
        title = heading.get_text(' ', strip=True) if heading else ''
        if not re.fullmatch(r'PLAN GENERAL DE ORDENACIÓN URBANA\s*-\s*Avance 2017', title, re.I):
            raise ValueError('PGOU stage changed; review before extraction')
        root_id = int(root['data-category'])
        visible_children = {int(a['data-idcat']) for a in root.select('a.catlink[data-idcat]')}
        queue = [(root_id, None, [])]
        seen = set()
        docs = {}
        while queue:
            cat, expected, path = queue.pop(0)
            if cat in seen:
                raise ValueError('Cycle or duplicate category in PGOU tree')
            seen.add(cat)
            if len(seen) > 200:
                raise ValueError('Tree exceeds reviewed safety bound; no partial output written')
            responses = {}
            for view, key in [('frontcategories', 'categories'), ('frontfiles', 'files')]:
                payload = fetch_json(api_url(view, cat))
                allowed = {key, 'category'} | ({'fileview'} if key == 'files' else set())
                if not isinstance(payload, dict) or set(payload) - allowed:
                    raise ValueError('Unexpected API metadata/pagination; review completeness')
                if not isinstance(payload.get(key), list) or int(payload['category']['id']) != cat:
                    raise ValueError('Invalid category response')
                responses[key] = payload[key]
            if cat == root_id and visible_children != {int(c['id']) for c in responses['categories']}:
                raise ValueError('API root categories differ from the visible inventory')
            files = responses['files']
            if expected is not None and len(files) != expected:
                raise ValueError('API file count differs from parent inventory; possible truncation')
            file_ids = set()
            for f in files:
                fid = str(int(f['id']))
                if fid in file_ids or int(f['catid']) != cat:
                    raise ValueError('Duplicate/misplaced document')
                file_ids.add(fid)
                url = official_url(f['link'])
                if not f.get('title') or not f.get('ext'):
                    raise ValueError('Document lacks title/type')
                doc = {
                    'id': fid, 'titulo': f['title'], 'url': url,
                    'formato': f['ext'], 'carpeta': path,
                    'source_url': api_url('frontfiles', cat),
                    # API metadata is a file upload date, not plan publication/approval.
                    'fecha_alta_documento': f.get('created_time'),
                }
                if fid in docs and docs[fid]['url'] != url:
                    raise ValueError('Conflicting document identity')
                docs.setdefault(fid, doc)
            for child in responses['categories']:
                if int(child['parent_id']) != cat:
                    raise ValueError('Unexpected child category parent')
                queue.append((int(child['id']), int(child['files']), path + [child['title']]))
        if not docs:
            raise ValueError('PGOU tree has no documents')
        row = record('pgou-' + str(root_id), title, PLAN, 'planeamiento_urbanistico')
        row.update(fase='avance', documentos=list(docs.values()),
                   descripcion='Avance 2017 publicado en el inventario municipal; no acredita aprobación definitiva.',
                   categorias_recorridas=len(seen))
        return row

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        capture = self.config.get('evidence_dir')
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-ordizia/1.0 (public planning inventory)'

            def fetch(url):
                time.sleep(0.15)
                response = session.get(url, timeout=40)
                response.raise_for_status()
                official_url(response.url)
                if len(response.content) > 8_000_000:
                    raise ValueError('Inventory response exceeds safety bound')
                self.source_urls.append(url)
                if capture:
                    dest = Path(capture)
                    dest.mkdir(parents=True, exist_ok=True)
                    suffix = '.json' if 'format=json' in url else '.html'
                    (dest / (hashlib.sha256(url.encode()).hexdigest()[:20] + suffix)).write_bytes(response.content)
                return response

            studies = self.parse_inventory(fetch(INVENTORY).text)
            plan = self.parse_plan(fetch(PLAN).text, lambda u: fetch(u).json())
        return {**self._write(out_jsonl, [plan] + studies), 'source_urls': self.source_urls,
                'coverage': 'PGOU Avance 2017 tree and direct detail-study documents on Urbanismo'}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of this documentary scope; state is not an approval date.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
