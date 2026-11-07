"""Official in-progress planning inventory, one record per municipal instrument."""
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

BASE = 'https://ciutada.platjadaro.com'
DETAIL_PREFIX = BASE + '/seu_electronica/informacio-urbanistica/planejament-urbanistic/'
SOURCE = DETAIL_PREFIX
SLUG = 'castell-d-aro-platja-d-aro-i-s-agaro'
NAME = "Castell d'Aro, Platja d'Aro i s'Agaró"
PHASES = {'Aprovació inicial': 'aprobación inicial',
          'Aprovació provisional': 'aprobación provisional',
          'Aprovació definitiva': 'aprobación definitiva'}


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _check_pagination(soup):
    # This reviewed inventory is unpaginated. Fail closed if that changes instead
    # of accepting the first page of an unknown paging/AJAX protocol.
    if soup.select('.pagination, .page-numbers, .nav-links, a[rel~=next], '
                   '[data-next-page], [data-total-pages]'):
        raise ValueError('Pagination detected; review crawler before extracting')
    for a in soup.select('main a[href], main button'):
        if re.search(r'^(següent|següents|siguiente|next|carrega més|carregar més|'
                     r'mostra més|mostrar més|load more)\b', _text(a), re.I):
            raise ValueError('More inventory results detected; cannot truncate')


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    _check_pagination(soup)
    panels = [p for p in soup.select('main .vc_tta-panel')
              if p.select_one('.vc_tta-title-text') and
              _text(p.select_one('.vc_tta-title-text')) == 'En tràmit']
    if len(panels) != 1:
        raise ValueError('Missing or ambiguous En tràmit inventory')
    rows = {}
    for card in panels[0].select('.planejament-urbanist-list'):
        a = card.select_one('a[href]')
        title = card.select_one('.main p')
        if not a or not title:
            raise ValueError('Malformed planning inventory card')
        url = urljoin(SOURCE, a['href'])
        if not url.startswith(DETAIL_PREFIX) or url == SOURCE or urlparse(url).query:
            raise ValueError('Unexpected planning detail URL')
        title = _text(title)
        if not re.match(r'^(Modificació puntual|Pla Especial Urbanístic)\b', title, re.I):
            raise ValueError('Unreviewed instrument type: ' + title)
        item = {'url': url, 'titulo': title}
        if url in rows and rows[url] != item:
            raise ValueError('Conflicting inventory titles')
        rows[url] = item
    if not rows:
        raise ValueError('No real planning instruments in inventory')
    return list(rows.values())


def parse_detail(html: str, item: dict) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    contents = soup.select('main article.type-planejament_urbanist .planejament_urbanistic')
    if len(contents) != 1:
        raise ValueError('Missing municipal planning detail content')
    content = contents[0]
    title, badge = content.select_one('h3'), content.select_one('.badge-aro')
    if not title or _text(title) != item['titulo'] or not badge or _text(badge) != 'Planejament en tràmit':
        raise ValueError('Inventory/detail identity or status mismatch')
    documents = {}
    milestones = []
    for row in content.select('article .row'):
        label, day = row.select_one('.label h4'), row.select_one('.data')
        if not label or not day or _text(label) not in PHASES:
            raise ValueError('Unknown or incomplete agreement milestone')
        agreement = datetime.strptime(_text(day), '%d/%m/%Y').date().isoformat()
        milestones.append({'fase': PHASES[_text(label)], 'fecha_acuerdo': agreement,
                           'etiqueta_fuente': _text(label), 'source_url': item['url']})
    if not milestones:
        raise ValueError('Instrument lacks dated agreement milestones')
    for a in content.select('a[href]'):
        url = urljoin(item['url'], a['href'])
        parsed = urlparse(url)
        allowed = (parsed.scheme == 'https' and
                   ((parsed.hostname == 'ciutada.platjadaro.com' and parsed.path.startswith('/wp-content/uploads/')) or
                    (parsed.hostname == 'bpm.platjadaro.cat' and parsed.path.startswith(('/OAC/download/', '/download4j/download/')))))
        if not allowed:
            raise ValueError('Unreviewed document destination: ' + url)
        ancestor = a.find_parent(class_='row')
        stage = ancestor.select_one('.label h4') if ancestor else None
        doc = {'titulo': _text(a), 'url': url, 'source_url': item['url'],
               'etapa_fuente': _text(stage) if stage else None}
        documents.setdefault((url, doc['titulo'], doc['etapa_fuente']), doc)
    if not documents:
        raise ValueError('Instrument has no source documents')
    # Retain all agreement stages. Document creation/publication dates and upload
    # directory years must never override the date explicitly labelled by town hall.
    latest = max(milestones, key=lambda m: m['fecha_acuerdo'])
    description = '\n'.join(_text(p) for p in content.find_all('p', recursive=False) if _text(p))
    return {
        'id': SLUG + '-proy-' + hashlib.sha256(item['url'].encode()).hexdigest()[:16],
        'municipio': NAME, 'codigo_ine': '17048', 'provincia': 'Girona',
        'titulo': item['titulo'],
        'tipo': 'modificacion_poum' if item['titulo'].lower().startswith('modificació') else 'plan_especial_urbanistico',
        'fase': latest['fase'], 'estado_fuente': _text(badge),
        'fecha': None, 'fecha_acuerdo': latest['fecha_acuerdo'],
        'fecha_aprob': latest['fecha_acuerdo'], 'fecha_publicacion': None,
        'hitos': milestones, 'descripcion': description,
        'url': item['url'], 'source_url': SOURCE,
        'source': 'ayuntamiento', 'origen': 'planejament_en_tramit',
        'documentos': list(documents.values()),
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'coverage': 'Partial: municipal En tràmit planning inventory only; no granted licences or complete works inventory',
    }


class CastellDAroPlatjaDAroISAgaroAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug=SLUG, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        with requests.get(url, timeout=(10, 40), stream=True,
                          headers={'User-Agent': self.config.get('user_agent', 'municipio-research-17048/1.0')}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != urlparse(url).hostname:
                raise ValueError('Source redirected outside municipal host')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected municipal HTML')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Source exceeds response size limit')
                chunks.append(chunk)
            body = b''.join(chunks)
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest() + '.html'
            (directory / name).write_bytes(body)
        return body.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        items = parse_inventory(self._fetch(SOURCE))
        rows = [parse_detail(self._fetch(item['url']), item) for item in items]
        # Publish the local snapshot only after every detail has parsed correctly.
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows),
                'source_urls': [SOURCE] + [item['url'] for item in items],
                'publication_ready': False, 'coverage': 'En tràmit planning inventory only'}

    def update_proyectos(self, out_jsonl, state_path):
        # Full current snapshot; no date cutoff discards ongoing instruments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
