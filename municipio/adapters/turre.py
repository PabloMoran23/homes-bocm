"""Turre's public planning board: live XPages categories and linked documents.

Only this current thematic inventory is covered, not the historical board.
Unexpected pagination fails explicitly rather than returning a partial snapshot.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, quote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://www.turre.es/Servicios/cmsdipro/index.nsf/'
          'tablon_view_entidad_rol_categoria2.xsp?cat2=Planeamiento+Urban%C3%ADstico&p=Turre')
LIMITATIONS = [
    'Solo inventario actual de Planeamiento Urbanístico; no histórico, BOP completo ni otras categorías.',
    'Excluye bases, estatutos y escrituras de juntas de compensación; no son proyectos físicos.',
    'Fechas de publicación de las fichas, no fechas de acuerdo o aprobación; estas quedan sin extraer.',
    'Documentos enlazados, sin extracción automática del contenido PDF ni comprobación de vigencia.',
    'Sin licencias concedidas verificadas, coordenadas ni geometría; publication_ready=false.',
    'Si aparece paginación nueva, la extracción falla explícitamente; no devuelve una primera página parcial.',
]
# Both linked BOP PDFs explicitly identify the same modification (RAIU 7918,
# approved 11 June 2009). This is an identity mapping, not a record inventory.
RELATED_NOTICES = {
    '90513C74461DBAC2C125844F00248B30': 'raiu-7918',
    'DD74FA168760928FC12583B400279658': 'raiu-7918',
}


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


def official_url(href, base=SOURCE):
    url = urljoin(base, href)
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'www.turre.es':
        raise ValueError('Unexpected off-site Turre source URL')
    return quote(url, safe=":/?=&%+$(),;@-_.!~*'")


def notice_id(url):
    query = parse_qs(urlsplit(url).query)
    ident = query.get('documentId', [''])[0]
    if not re.fullmatch(r'[A-Fa-f0-9]{32}', ident) or query.get('p') != ['Turre']:
        raise ValueError('Invalid Turre notice identifier')
    return ident.upper()


def instrument_type(title):
    text = normalized(title)
    if re.search(r'\b(licitacion|contratacion|licencia|modelo|formulario)\b', text):
        return None
    if re.search(r'proyecto de (reparcelacion|actuacion|urbanizacion)\b', text):
        return 'proyecto urbanístico'
    if re.search(r'\b(innovacion|modificacion)\b', text) and re.search(r'plan parcial|p\.?g\.?o\.?u\.?', text):
        return 'instrumento de planeamiento'
    if re.match(r'^(plan (general|parcial|especial)|estudio de detalle)\b', text):
        return 'instrumento de planeamiento'
    return None


def inventory_state(html):
    soup = BeautifulSoup(html, 'html.parser')
    panel = soup.select_one('#cmsdip-pro-tablon-view')
    form = soup.select_one('form.xspForm')
    if panel is None or form is None:
        raise ValueError('Turre inventory/form missing')
    # The observed footer is empty. Never silently ignore a new paging control.
    if panel.select('[class*="xspPager"], [id*="pager"], [id*="Pager"], a[rel="next"]'):
        raise ValueError('Unexpected pagination in Turre inventory; traversal requires review')
    for footer in panel.select('[class*="Footer"]'):
        if footer.select('a, button, input, select'):
            raise ValueError('Unexpected inventory footer controls/pagination')
    buttons = [b for b in panel.select('button[id]')
               if b.select_one('img[src$="/expand.gif"]')]
    links = {}
    for a in panel.select('.tablon-container .titulo a[href]'):
        url = official_url(a['href'])
        ident = notice_id(url)
        if not urlsplit(url).path.endswith('/tablon.xsp'):
            raise ValueError('Unexpected inventory notice path')
        links[ident] = (url, a.get_text(' ', strip=True))
    return form, buttons, links


def parse_notice(html, url):
    url = official_url(url)
    ident = notice_id(url)
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#cmsdip-pro-tablon-anuncios')
    if content is None:
        raise ValueError('Turre notice content missing')
    heading = content.select_one('#doc-dipalme-titulo h1')
    body = content.select_one('#doc-lectura-cultura')
    if heading is None or body is None or body.select_one('h2') is None:
        raise ValueError('Turre notice structure changed')
    if body.select_one('h2').get_text(' ', strip=True) != 'Ayuntamiento de Turre':
        raise ValueError('Notice belongs to another municipality')
    title = ' '.join(heading.get_text(' ', strip=True).split())
    kind = instrument_type(title)
    if not kind:
        raise ValueError('Notice is not a project or planning instrument')
    published = re.search(r'Publicado:\s*(\d{2}/\d{2}/\d{4})', body.get_text(' ', strip=True))
    if not published:
        raise ValueError('Notice publication date missing')
    publication = datetime.strptime(published[1], '%d/%m/%Y').date().isoformat()
    documents = {}
    for a in body.select('a[href]'):
        if '/$file/' not in a['href']:
            continue
        target = official_url(a['href'], url)
        if not urlsplit(target).path.lower().startswith('/servicios/tablon/'):
            raise ValueError('Unexpected document path')
        label = a.get('title') or a.get_text(' ', strip=True)
        if target not in documents:
            documents[target] = {'titulo': label, 'url': target, 'source_url': url}
    if not documents:
        raise ValueError('Instrument notice has no linked documents')
    expediente = re.search(r'\b\d{4}/\d{6}/\d{3}-\d{3}/\d{5}\b', title)
    key = RELATED_NOTICES.get(ident) or (f'exp-{expediente[0]}' if expediente else f'notice-{ident}')
    return {'key': key, 'notice_id': ident, 'titulo': title, 'tipo': kind,
            'expediente': expediente[0] if expediente else None,
            'url': url, 'fecha_publicacion': publication,
            'documentos': list(documents.values())}


def group_instruments(notices):
    grouped = {}
    for notice in notices:
        grouped.setdefault(notice['key'], {})[notice['notice_id']] = notice
    rows = []
    for key, members in sorted(grouped.items()):
        publications = sorted(members.values(), key=lambda n: (n['fecha_publicacion'], n['notice_id']))
        primary = next((n for n in publications if not re.search(r'correccion|rectificacion', normalized(n['titulo']))), publications[0])
        documents = {}
        for n in publications:
            for doc in n['documentos']:
                documents.setdefault(doc['url'], doc)
        rows.append({
            'id': 'turre-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Turre', 'codigo_ine': '04093', 'provincia': 'Almería',
            'titulo': primary['titulo'], 'tipo': primary['tipo'],
            'expediente': primary['expediente'], 'url': primary['url'],
            'inventory_url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'fecha_publicacion': primary['fecha_publicacion'],
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'publicaciones': [{k: v for k, v in n.items() if k not in ('key', 'tipo', 'expediente', 'documentos')} for n in publications],
            'documentos': list(documents.values()),
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    if not rows:
        raise ValueError('No usable Turre instruments found')
    return rows


class TurreAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='turre', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.turre.es')

    def _request(self, session, url, *, data=None):
        response = session.request('POST' if data is not None else 'GET', url, data=data, timeout=45)
        response.raise_for_status()
        if official_url(response.url) != official_url(url):
            raise ValueError('Unexpected source redirect')
        return response.content

    def _capture(self, name, html):
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(html)

    def _inventory(self, session):
        html = self._request(session, SOURCE)
        seen = set()
        for step in range(100):
            self._capture(f'inventory-{step:02d}.html', html)
            form, buttons, links = inventory_state(html)
            if not buttons:
                if not links:
                    raise ValueError('Empty Turre inventory')
                return links
            fingerprint = hashlib.sha256(str(form).encode()).hexdigest()
            if fingerprint in seen:
                raise ValueError('Turre category expansion did not progress')
            seen.add(fingerprint)
            data = {x['name']: x.get('value', '') for x in form.select('input[name]')}
            if not data.get('$$viewid'):
                raise ValueError('Missing anonymous XPages view state')
            data['$$xspsubmitid'] = buttons[0]['id'].removesuffix('button')
            # Public UI category expansion only; never a submission of an application.
            html = self._request(session, SOURCE, data=data)
        raise ValueError('Turre category expansion limit exceeded')

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-turre/1.0 (public planning inventory)'
            links = self._inventory(session)
            notices, excluded = [], []
            for ident, (url, title) in links.items():
                if not instrument_type(title):
                    excluded.append({'url': url, 'titulo': title})
                    continue
                html = self._request(session, url)
                self._capture(f'notice-{ident}.html', html)
                notices.append(parse_notice(html, url))
        rows = group_instruments(notices)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'live_records': len(rows),
                'inventory_notices': len(links), 'selected_notices': len(notices),
                'source_urls': [SOURCE] + [n['url'] for n in notices],
                'excluded_notices': excluded, 'limitations': LIMITATIONS,
                'coverage': 'current_thematic_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
