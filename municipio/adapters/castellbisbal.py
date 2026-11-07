"""Castellbisbal's official urban-planning document inventory, grouped by instrument."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/castellbisbal/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme')
HEADERS = ['Normativa', 'Data de publicació', 'Enllaç', 'Documents', 'Més informació']
LIMITATIONS = [
    'Partial coverage: only instruments in the municipal Normativa d’urbanisme table; '
    'not the full RPUC, public-works inventory or a granted-licence register.',
    'Publication dates are the table’s dates, not agreement, approval or effective dates. '
    'Different publication dates remain on each document; no single date is chosen for the POUM.',
    'Document language and instrument identity follow municipal labels; PDF contents '
    'are not parsed or independently reconciled with RPUC.',
    'No verified coordinates or geometry; publication_ready is false.',
]


def parse_projects(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    heading = any(h.get_text(" ", strip=True) == "Normativa d'urbanisme"
                  for h in soup.find_all(["h1", "h2"]))
    tables = [t for t in soup.select('table')
              if [h.get_text(' ', strip=True) for h in t.select('thead th')] == HEADERS]
    if not heading or len(tables) != 1:
        raise ValueError('Official planning heading/table missing or ambiguous')
    table = tables[0]
    scope = table.find_parent(class_='portlet-body') or table.parent
    for a in scope.select('a[href]'):
        label = ' '.join([a.get_text(' ', strip=True), a.get('aria-label', '')]).lower()
        if ('next' in a.get('rel', []) or
                re.search(r'següent|siguiente|next|última pàgina', label) or
                a.find_parent(class_=re.compile(r'pagination|pager'))):
            if a['href'] not in ('', '#'):
                raise ValueError('Server pagination detected; review inventory before extracting')
    for script in soup.select('script'):
        text = script.get_text()
        if table.get('id', 'NO_TABLE_ID') in text and re.search(r'DataTable\s*\(', text):
            if re.search(r'["\x27]?(?:serverSide|bServerSide|ajax|sAjaxSource)["\x27]?\s*:', text):
                raise ValueError('Remote DataTable detected; HTML may be incomplete')
    groups = {}
    tbody = table.find('tbody')
    if tbody is None:
        raise ValueError('Planning table has no body')
    for tr in tbody.find_all('tr'):
        # The official HTML omits </tr>; html.parser nests the rows. Never use
        # recursive cell selection, which would swallow subsequent documents.
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 5:
            raise ValueError('Unexpected planning table row')
        title = cells[0].get_text(' ', strip=True)
        canonical = re.sub(r'^Versió en castellà\.\s*', '', title)
        match = re.fullmatch(r'Modificació puntual número (\d+) del POUM', canonical)
        if match:
            key = 'poum-modificacio-' + str(int(match[1]))
            instrument = canonical
        elif (canonical in ("Pla d'Ordenació Urbanística Municipal (POUM)",
                            'Plan de Ordenación Urbanística Municipal (POUM)') or
              re.fullmatch(r'Resolució sobre el POUM de (febrer|setembre) de 2009', canonical)):
            key, instrument = 'poum', "Pla d'Ordenació Urbanística Municipal (POUM)"
        else:
            raise ValueError(f'Unreviewed planning instrument: {title}')
        raw_date = cells[1].get_text(' ', strip=True)
        published = datetime.strptime(raw_date, '%d-%m-%Y').date().isoformat() if raw_date else None
        documents = []
        for a in cells[3].select('a[href]'):
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname not in {'seu-e.cat', 'www.seu-e.cat'} or not parsed.path.startswith('/documents/'):
                raise ValueError('Unexpected official document URL')
            documents.append({'titulo': a.get_text(' ', strip=True), 'url': url,
                              'titulo_fila': title, 'fecha_publicacion': published,
                              'idioma': 'es' if title.startswith('Versió en castellà.') else 'ca',
                              'source_url': SOURCE})
        if not documents:
            raise ValueError(f'Instrument lacks supporting documents: {title}')
        row = groups.setdefault(key, {
            'id': 'castellbisbal-' + key, 'municipio': 'Castellbisbal',
            'codigo_ine': '08054', 'provincia': 'Barcelona', 'titulo': instrument,
            'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'normativa_urbanisme',
            'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False,
        })
        for doc in documents:
            if doc not in row['documentos']:
                row['documentos'].append(doc)
    if not groups:
        raise ValueError('No usable planning instruments in official table')
    for row in groups.values():
        dates = {d['fecha_publicacion'] for d in row['documentos']}
        row['fecha_publicacion'] = next(iter(dates)) if len(dates) == 1 else None
        row['url_documento'] = row['documentos'][0]['url']
    return [groups[key] for key in sorted(groups)]


class CastellbisbalAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.castellbisbal.cat')

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=(15, 60), stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-castellbisbal/1.0')
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).path.rstrip('/') != urlparse(SOURCE).path:
                raise ValueError('Planning source redirected to a different page')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Planning inventory exceeds response size limit')
                chunks.append(chunk)
            content = b''.join(chunks)
        html = content.decode('utf-8')
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            folder = Path(capture_dir)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'normativa-live.html').write_bytes(content)
        rows = parse_projects(html)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temporary = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full replacement snapshot: no date cutoff can lose older table entries.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
