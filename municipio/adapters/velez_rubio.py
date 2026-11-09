"""Current municipal planning board: expand every category, retain provenance."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://www.velezrubio.es/Servicios/cmsdipro/index.nsf/'
          'tablon_view_entidad_rol_categoria12.xsp?cat1=Territorio&'
          'cat2=Planeamiento+Urban%C3%ADstico&p=VelezR')
LIMITATIONS = [
    'Snapshot of the current municipal planning board only, not a complete historical register.',
    'Publication dates are board dates, not agreement or approval dates; PDF narratives are not parsed.',
    'NNSS and historic-centre plan modification remain one documentary package as published.',
    'No verified geometry, granted-licence register or exhaustive public-works coverage.',
]


def norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def soup_for(html):
    return BeautifulSoup(html, 'html.parser')


def check_entity(url):
    parsed = urlparse(url)
    if (parsed.scheme != 'https' or parsed.hostname != 'www.velezrubio.es'
            or parse_qs(parsed.query).get('p') != ['VelezR']):
        raise ValueError('Unexpected municipal entity or source URL')


def inventory(html, url=SOURCE):
    check_entity(url)
    soup = soup_for(html)
    panel = soup.select_one('#cmsdip-pro-tablon-view')
    if panel is None:
        raise ValueError('Missing planning inventory')
    # This board has no pager today. Fail closed if the publisher introduces one:
    # a partial first page must never be emitted as a successful extraction.
    if panel.select('[class*="Pager"], [class*="pager"], a[rel="next"]'):
        raise ValueError('Pagination introduced: traversal needs review')
    collapsed = [b['id'].removesuffix('button') for b in panel.select('button[id]')
                 if b.select_one('img[src$="/expand.gif"]')]
    links = {}
    for a in panel.select('a[href]'):
        target = urljoin(url, a['href'])
        if urlparse(target).path.endswith('/tablon.xsp'):
            check_entity(target)
            ids = parse_qs(urlparse(target).query).get('documentId', [])
            if len(ids) != 1 or not re.fullmatch('[A-F0-9]{32}', ids[0]):
                raise ValueError('Invalid notice identity')
            links[target] = a.get_text(' ', strip=True)
    return soup, collapsed, links


def selected(title):
    return bool(re.match(r'^(aprobacion de estudio de detalle|normas subsidiarias|'
                         r'proyecto de actuacion|actuacion extraordinaria)\b', norm(title)))


def parse_notice(html, url):
    check_entity(url)
    soup = soup_for(html)
    title = soup.select_one('#doc-dipalme-titulo h1')
    content = soup.select_one('#doc-lectura-cultura')
    if title is None or content is None:
        raise ValueError('Missing notice content')
    entity = content.select_one('.left h2')
    if entity is None or entity.get_text(' ', strip=True) != 'Ayuntamiento de Vélez Rubio':
        raise ValueError('Notice belongs to another entity')
    title = ' '.join(title.get_text(' ', strip=True).split())
    if not selected(title):
        raise ValueError('Notice is not a named planning instrument or project')
    published = content.select_one('.right')
    match = re.search(r'Publicado:\s*(\d{2}/\d{2}/\d{4})', published.get_text(' ', strip=True) if published else '')
    if not match:
        raise ValueError('Missing publication date')
    publication = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
    documents = {}
    for a in content.select('#attachments a[href]'):
        target = urljoin(url, a['href'])
        parsed = urlparse(target)
        if (parsed.scheme != 'https' or parsed.hostname != 'www.velezrubio.es'
                or not parsed.path.lower().startswith('/servicios/tablon/anexos.nsf/')
                or '/$file/' not in parsed.path.lower()):
            raise ValueError('Unexpected attachment provenance')
        if target not in documents:
            documents[target] = {'titulo': a.get_text(' ', strip=True), 'url': target,
                                 'source_url': url, 'fecha_publicacion': publication}
    if not documents:
        raise ValueError('No supporting planning documents')
    return {'titulo': title, 'url': url, 'fecha_publicacion': publication,
            'documentos': list(documents.values())}


def identity(notice):
    title = norm(notice['titulo'])
    # Two publication stages use slightly different spelling/spacing. Match
    # the complete location AND promoter, never a generic category or date.
    if 'explotacion porcina' in title:
        match = re.search(r'poligono\s+(\d+)\s+parcelas?\s+(.+?)\.?\s*promotor:\s*(.+)', title)
        if not match:
            raise ValueError('Cannot safely identify pig-farm project')
        parcels = tuple(sorted(set(re.findall(r'\d+', match[2].replace('.', ''))), key=int))
        promoter = re.sub(r'[^a-z0-9]+', ' ', match[3]).strip()
        return 'porcina|' + match[1] + '|' + ','.join(parcels) + '|' + promoter
    return parse_qs(urlparse(notice['url']).query)['documentId'][0]


def group_notices(notices):
    groups = {}
    for notice in notices:
        groups.setdefault(identity(notice), []).append(notice)
    rows = []
    for key, items in sorted(groups.items()):
        items = sorted({n['url']: n for n in items}.values(), key=lambda n: (n['fecha_publicacion'], n['url']))
        rows.append({
            'id': 'velez-rubio-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Vélez-Rubio', 'codigo_ine': '04099', 'provincia': 'Almería',
            'titulo': items[0]['titulo'], 'tipo': 'instrumento o proyecto urbanístico',
            'url': items[0]['url'], 'source': 'ayuntamiento', 'inventory_url': SOURCE,
            'origen': 'tablon_planeamiento_municipal',
            'fecha_publicacion': items[0]['fecha_publicacion'],
            'fecha_publicacion_semantica': 'primera ficha observada de este conjunto',
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'publicaciones': items,
            'documentos': [d for n in items for d in n['documentos']],
            'publication_ready': False, 'geometry_status': 'unavailable',
            'coverage': 'current_board_documentary_package',
        })
    if not rows:
        raise ValueError('No genuine planning instruments/projects found')
    return rows


class VelezRubioAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='velez-rubio', config=None, base_url=''):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path):
        capture_dir = self.config.get('capture_dir')
        captures = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-velez-rubio/1.0'

            def fetch(method, url, **kwargs):
                check_entity(url)
                response = session.request(method, url, timeout=45, **kwargs)
                response.raise_for_status()
                check_entity(response.url)
                if capture_dir:
                    path = Path(capture_dir) / f'live-{len(captures):03d}.html'
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(response.text, encoding='utf-8')
                    captures.append({'url': response.url, 'method': method,
                                     'path': str(path), 'sha256': hashlib.sha256(response.content).hexdigest()})
                return response.text

            html = fetch('GET', SOURCE)
            visited = set()
            while True:
                soup, collapsed, links = inventory(html)
                if not collapsed:
                    break
                # Every expansion is a read-only XPages view-state submission.
                signature = hashlib.sha256(html.encode()).hexdigest()
                if signature in visited or len(visited) >= 200:
                    raise ValueError('Inventory expansion stalled or exceeded safety limit')
                visited.add(signature)
                form = soup.select_one('form.xspForm')
                if form is None or not form.select_one('input[name="$$viewid"]'):
                    raise ValueError('Missing XPages expansion state')
                data = {i['name']: i.get('value', '') for i in form.select('input[name]')}
                data['$$xspsubmitid'] = collapsed[0]
                html = fetch('POST', SOURCE, data=data)
            if not links:
                raise ValueError('Empty expanded inventory')
            notices = [parse_notice(fetch('GET', url), url)
                       for url, title in links.items() if selected(title)]
        rows = group_notices(notices)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'live_records': len(rows), 'notices': len(notices),
                'inventory_entries': len(links), 'expanded_categories': len(visited),
                'source_urls': [SOURCE, *links], 'limitations': LIMITATIONS,
                'captures': captures, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full current snapshot; never advance a historical cursor on this board.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
