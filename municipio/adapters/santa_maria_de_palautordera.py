"""Complete snapshots of the two reviewed municipal planning/work inventories."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.smpalautordera.cat'
PLANNING = BASE + '/ajuntament/normativa/poum-pla-dordenacio-urbanistica-municipal'
WORKS = BASE + '/el-municipi/obra-municipal-ordinaria'
MONTHS = dict(zip('gener febrer març abril maig juny juliol agost setembre octubre novembre desembre'.split(), range(1, 13)))


def _date(text):
    match = re.search(r'(\d{1,2}) de (\w+) de (\d{4})', text)
    if not match:
        return None
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


def _page(html, heading):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main#main-content')
    h1 = main.select_one('h1') if main else None
    if not h1 or h1.get_text(' ', strip=True) != heading:
        raise ValueError('Missing municipal inventory heading')
    # These are single-page inventories. Fail visibly if pagination is introduced.
    if main.select('.pagination, .paginacio, .paginator, [rel~=next]'):
        raise ValueError('Inventory now paginated; review crawler before extraction')
    for a in main.select('a[href]'):
        if a.get_text(' ', strip=True).lower() in {'següent', 'siguiente', 'next', '»', '›'}:
            raise ValueError('Unexpected next-page link')
    return main


def _links(node, source):
    docs = {}
    if node:
        for a in node.select('a[href]'):
            url = urljoin(source, a['href'])
            if urlparse(url).scheme not in {'http', 'https'}:
                raise ValueError('Unexpected document URL')
            title = re.sub(r'\s*\([\d.]+\s*[KMGT]?B\)\s*$', '', a.get_text(' ', strip=True)).strip()
            docs.setdefault(url, {'titulo': title, 'url': url, 'url_fuente': source})
    return list(docs.values())


def _record(title, kind, source, identity, docs):
    return {
        'id': 'santa-maria-de-palautordera-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
        'municipio': 'Santa Maria de Palautordera', 'codigo_ine': '08259',
        'provincia': 'Barcelona', 'titulo': title, 'tipo': kind,
        'source': 'ayuntamiento', 'origen': 'inventario_municipal',
        'url': source, 'url_documento': docs[0]['url'], 'documentos': docs,
        'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'fase': None,
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
    }


class SantaMariaDePalautorderaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_planning(html):
        main = _page(html, "POUM: Pla d'Ordenació Urbanística Municipal")
        narrative = next((b.get_text(' ', strip=True) for b in main.select('.ddbbtext')
                          if b.get_text(' ', strip=True).startswith('El Text refós del')), None)
        docs = _links(main.select_one('#page-documents'), PLANNING)
        if not narrative or 'aprovat definitivament' not in narrative or not docs:
            raise ValueError('Missing POUM narrative or documents')
        title = "Text refós del Pla d'Ordenació Urbanística Municipal de Santa Maria de Palautordera"
        base = _record(title, 'POUM', PLANNING, PLANNING, docs)
        base.update(descripcion=narrative, fase='aprobación definitiva',
                    fecha_aprob=_date(narrative.split('i publicat')[0]),
                    fecha_publicacion=_date(narrative.split('i publicat')[-1]) if 'i publicat' in narrative else None,
                    enlaces=_links(main.select_one('#page-links'), PLANNING))
        rows = {base['id']: base}
        items = main.select('.ddbbtext li')
        if not items:
            raise ValueError('Missing derived planning inventory')
        for li in items:
            title = li.get_text(' ', strip=True)
            if not re.match(r'^\d{4}\s*-\s*(?:Modificació|Pla especial)', title):
                raise ValueError('Unrecognized planning inventory item: ' + title)
            docs = _links(li, PLANNING)
            if not docs or any(not (re.fullmatch(r'https?://dtes\.gencat\.cat/rpucportal/#/consulta/detallExpedient/\d+', d['url'])
                                  or (urlparse(d['url']).hostname == 'www.smpalautordera.cat'
                                      and urlparse(d['url']).path.startswith('/media/repository/')
                                      and urlparse(d['url']).path.lower().endswith('.pdf'))) for d in docs):
                raise ValueError('Planning item lacks reviewed document/dossier links')
            # One list item is one instrument, even when it has multiple documents.
            row = _record(title, 'planeamiento_urbanistico', PLANNING, docs[0]['url'], docs)
            row['descripcion'] = title
            row['anio_referencia_fuente'] = int(title[:4])  # Not an approval/publication date.
            dossier = re.search(r'/detallExpedient/(\d+)$', docs[0]['url'])
            if dossier:
                row['rpuc_id'] = dossier[1]
            if row['id'] in rows:
                existing = rows[row['id']]['documentos']
                existing.extend(d for d in docs if d['url'] not in {x['url'] for x in existing})
            else:
                rows[row['id']] = row
        return list(rows.values())

    @staticmethod
    def parse_works(html):
        main = _page(html, 'Obra municipal ordinària')
        docs = _links(main.select_one('#page-documents'), WORKS)
        if not docs:
            raise ValueError('Empty municipal works inventory')
        rows = {}
        for doc in docs:
            title = doc['titulo']
            if not re.match(r"^Aprovació (?:incial|inicial) del projecte d'", title):
                raise ValueError('Unreviewed works inventory entry: ' + title)
            if not (doc['url'].startswith(BASE + '/media/repository/') and doc['url'].lower().endswith('.pdf')):
                raise ValueError('Missing municipal works PDF')
            row = _record(title, 'obra_publica', WORKS, doc['url'], [doc])
            row.update(fase='aprobación inicial', descripcion=title)
            rows[row['id']] = row
        return list(rows.values())

    def _fetch(self, url, capture_name):
        response = requests.get(url, timeout=(10, 45), stream=True,
                                headers={'User-Agent': self.config.get('user_agent', 'municipio-santa-maria-de-palautordera/1.0')})
        with response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Inventory exceeds reviewed response size')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Expected HTML inventory')
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir'])
            path.mkdir(parents=True, exist_ok=True)
            (path / capture_name).write_bytes(data)
        return data.decode('utf-8')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = self.parse_planning(self._fetch(PLANNING, 'poum.html'))
        rows += self.parse_works(self._fetch(WORKS, 'obra-municipal.html'))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [PLANNING, WORKS], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
