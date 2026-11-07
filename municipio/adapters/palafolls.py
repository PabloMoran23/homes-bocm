"""Palafolls' published general-plan document inventory (partial coverage)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/palafolls/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme')
TITLE = "Pla General d'Ordenació Territorial i Urbana i planejament urbanístic municipal de Palafolls."
LIMITATIONS = [
    'Partial coverage: only the general-plan documents in the municipal normative inventory; not all RPUC dossiers or public works.',
    'The linked legacy municipal plan-map page returned HTTP 404 during research.',
    'The 2005 consolidated text is explicitly marked no-vigent in its source URL; retained only as historical documentation.',
    'No granted-licence inventory or verified project geometry; coordinates remain null.',
    'Publication dates describe document publication; page-update timestamps are not approval dates.',
]


def _date(text):
    if not text.strip():
        return None
    return datetime.strptime(text.strip(), '%d-%m-%Y').date().isoformat()


def parse_projects(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    tables = [t for t in soup.select('table') if
              [h.get_text(' ', strip=True) for h in t.select('th')][:2]
              == ['Normativa', 'Data de publicació']]
    if len(tables) != 1:
        raise ValueError('Expected one Palafolls normative inventory')
    table = tables[0]
    # DataTables paginates this complete HTML table in the browser. Read all
    # tbody rows, including those after its default first ten. Fail if the
    # source changes to remote pagination rather than silently taking page one.
    if re.search(r'["\']?(?:serverSide|bServerSide|ajax|sAjaxSource)["\']?\s*:', html, re.I):
        raise ValueError('Remote table loading requires a reviewed pagination implementation')
    for a in soup.select('a[href], link[href]'):
        if ('next' in a.get('rel', []) or
                a.get_text(' ', strip=True).casefold() in {'next', 'següent', 'siguiente'}):
            if a['href'] not in {'', '#'} and 'disabled' not in a.get('class', []):
                raise ValueError('Unexpected server pagination')
    docs = {}
    agreement = None
    narrative = None
    for tr in table.select('tbody tr'):
        # The official HTML omits closing </tr> tags; bs4 nests the rows.
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 5:
            raise ValueError('Changed normative row structure')
        title = cells[0].get_text(' ', strip=True)
        if not (title.startswith(TITLE) or title.startswith('Plànols normatius de la revisió del pla general')):
            continue  # regional legislation and generic map/register links
        links = cells[2].select('a[href]') + cells[3].select('a[href]')
        if not links:
            raise ValueError('Plan document has no source link')
        publication = _date(cells[1].get_text(' ', strip=True))
        info = cells[4].get_text(' ', strip=True)
        match = re.search(r"segons acord .*? del (\d{1,2}) d[´’']abril del (\d{4})", info)
        if match:
            value = datetime(int(match[2]), 4, int(match[1])).date().isoformat()
            if agreement and agreement != value:
                raise ValueError('Conflicting plan agreement dates')
            agreement, narrative = value, info
        for a in links:
            url = urljoin(SOURCE, a['href'])
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname not in {'seu-e.cat', 'www.palafolls.cat'}:
                raise ValueError('Unexpected plan document provenance')
            if parsed.hostname == 'seu-e.cat' and not parsed.path.startswith('/documents/14304757/'):
                raise ValueError('Document is outside the Palafolls repository')
            doc = {'titulo': title, 'url': url, 'source_url': SOURCE,
                   'fecha_publicacion': publication, 'descripcion': info or None,
                   'historico': 'no-vigent' in url,
                   'tipo': 'documento' if '/documents/' in parsed.path else 'pagina_enlazada'}
            if url in docs and docs[url] != doc:
                raise ValueError('Conflicting duplicate document metadata')
            docs[url] = doc
    # Require actual normative volumes, rather than navigation or licence forms.
    if not any('(VOL. 1)' in d['titulo'] and d['tipo'] == 'documento' for d in docs.values()):
        raise ValueError('No general-plan normative volume found')
    dates = {d['fecha_publicacion'] for d in docs.values() if not d['historico'] and d['fecha_publicacion']}
    return [{
        'id': 'palafolls-proy-pla-general', 'municipio': 'Palafolls',
        'codigo_ine': '08155', 'provincia': 'Barcelona', 'titulo': TITLE.rstrip('.'),
        'tipo': 'planeamiento_urbanistico', 'source': 'ayuntamiento',
        'origen': 'inventario_normativa_urbanistica', 'url': SOURCE,
        'fecha': None, 'fecha_publicacion': next(iter(dates)) if len(dates) == 1 else None,
        'fecha_acuerdo': agreement, 'fecha_aprob': None,
        'fase': 'aprobado de oficio' if agreement else None,
        'descripcion': narrative, 'documentos': sorted(docs.values(), key=lambda d: d['url']),
        'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        'limitations': LIMITATIONS,
    }]


class PalafollsAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='palafolls', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.palafolls.cat')

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.get(SOURCE, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-palafolls/1.0')
        }) as response:
            response.raise_for_status()
            if response.url != SOURCE or 'html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Unexpected inventory response')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Inventory exceeds bounded response size')
                chunks.append(chunk)
            body = b''.join(chunks)
        rows = parse_projects(body.decode('utf-8'))
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'normativa-live.html').write_bytes(body)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot refresh; no date cutoff that loses older documents.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
