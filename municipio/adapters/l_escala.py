"""Snapshot of L'Escala's municipal planning-document inventory (not licences)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/escala/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/planejament-urbanistic')


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _document(url):
    parsed = urlsplit(url)
    return (parsed.scheme == 'https' and parsed.hostname in {'seu-e.cat', 'www.seu-e.cat'}
            and parsed.path.startswith('/documents/2475467/'))


class LEscalaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.lescala.cat')

    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, 'html.parser')
        # A changed/paginated inventory must be reviewed, never silently clipped.
        for a in soup.select('a[href]'):
            if ('next' in a.get('rel', []) or
                _text(a).lower() in {'següent', 'següents', 'siguiente', 'next', '›', '»'} or
                re.search(r'(?:[?&](?:page|start|_.*cur)=)', a['href'], re.I)):
                if a['href'] not in {'', '#'}:
                    raise ValueError('Pagination detected; inventory requires crawler review')
        contents = [c for c in soup.select('.journal-content-article')
                    if any(_document(urljoin(SOURCE, a['href'])) for a in c.select('a[href]'))]
        if len(contents) != 1:
            raise ValueError('Expected one municipal planning-document inventory')
        content = contents[0]
        update = re.search(r'Actualització:\s*(\d{2}/\d{2}/\d{4})', soup.get_text(' ', strip=True))
        updated = datetime.strptime(update[1], '%d/%m/%Y').date().isoformat() if update else None
        groups = {}
        accounted = set()
        for li in content.select('li'):
            if li.find_parent('li') is not None:
                continue
            heading = BeautifulSoup(str(li), 'html.parser').li
            for child in heading.select('ul, ol'):
                child.decompose()
            title = _text(heading)
            docs = {}
            other_links = []
            for a in li.select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                if _document(url):
                    docs.setdefault(url, {'titulo': _text(a), 'url': url, 'url_fuente': SOURCE})
                elif a['href'].strip():
                    other_links.append({'titulo': _text(a), 'url_original': a['href']})
            if not docs:
                # These are navigation to the POUM microsite and regional map.
                if title in {'POUM EN REVISIÓ', 'MAPA URBANÍSTIC DE CATALUNYA'}:
                    continue
                raise ValueError('Unrecognized inventory entry without documents: ' + title)
            if title.startswith('MP_PGOU_Estany_Poma_'):
                key = 'MP_PGOU_Estany_Poma'
                display = 'Modificació del PGOU — Estany de Poma'
                kind = 'modificacion_planeamiento'
            elif re.match(r'^(Aprovar inicialment la Modificació|Modificació del PGOU)', title):
                key = display = title
                kind = 'modificacion_planeamiento'
            elif title.startswith('PLA PARCIAL URBANÍSTIC'):
                key = display = title
                kind = 'plan_parcial'
            elif title.startswith('PLA ESPECIAL DE PROTECCIÓ'):
                key = display = title
                kind = 'plan_especial'
            else:
                raise ValueError('Unrecognized planning instrument: ' + title)
            group = groups.setdefault(key, {'titulo': display, 'tipo': kind, 'docs': {}, 'links': []})
            group['docs'].update(docs)
            group['links'].extend(other_links)
            accounted.update(docs)
        all_docs = {urljoin(SOURCE, a['href']) for a in content.select('a[href]')
                    if _document(urljoin(SOURCE, a['href']))}
        if not groups or all_docs != accounted:
            raise ValueError('Empty or incompletely grouped document inventory')
        rows = []
        for key, group in groups.items():
            docs = list(group['docs'].values())
            rows.append({
                'id': 'l-escala-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': "L'Escala", 'codigo_ine': '17062', 'provincia': 'Girona',
                'titulo': group['titulo'], 'tipo': group['tipo'], 'fase': None,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fecha_actualizacion_fuente': updated,
                'url': SOURCE, 'url_documento': docs[0]['url'], 'documentos': docs,
                'enlaces_no_documentales': group['links'],
                'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
                'descripcion': 'Instrumento y documentos publicados en el inventario municipal de planeamiento. '
                               'La inclusión no acredita vigencia ni aprobación definitiva.',
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'geometry_status': 'No verified instrument geometry extracted',
            })
        return rows

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.get(SOURCE, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-l-escala/1.0')
        }) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ValueError('Planning inventory exceeds reviewed response size')
                chunks.append(chunk)
            html = b''.join(chunks).decode('utf-8')
        rows = self.parse_projects(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'planejament-live.html').write_text(html, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'coverage': 'partial'}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        tmp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
