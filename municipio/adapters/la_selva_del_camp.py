"""Municipal planning catalogue snapshot; RPUC dossiers are provenance links."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://seu-e.cat/ca/web/laselvadelcamp/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/planejament-urbanistic')
RPUC = re.compile(r'https://dtes\.gencat\.cat/rpucportal/#/consulta/detallExpedient/(\d+)')
LIMITATIONS = [
    'Partial municipal coverage: only the municipal planning catalogue, not public-works notices or the full RPUC register.',
    'The catalogue mixes approved and provisional instruments; individual approval/publication dates and phases are not established.',
    'RPUC links identify dossiers, not municipal expediente numbers; their document inventories are not crawled.',
    'No verified coordinates or vector geometry; publication_ready is false.',
    'No granted-licence register extracted; licence collection and scheduling disabled.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _kind(title):
    if title.startswith('Text Refós normes urbanístiques'):
        return 'normas_subsidiarias'
    if re.match(r'^(?:MPNSP|MPSNP)\s+\d+|^Modificació Normes Subsidiàries', title):
        return 'modificacion_planeamiento'
    if title.startswith('Modificació pla parcial'):
        return 'modificacion_plan_parcial'
    if title.startswith('Pla parcial'):
        return 'plan_parcial'
    if title.startswith('Pla especial'):
        return 'plan_especial'
    if title.startswith('Delimitació de la TUC'):
        return 'delimitacion_trama_urbana'
    return None


class LaSelvaDelCampAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://seu-e.cat/ca/web/laselvadelcamp')

    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        articles = [a for a in soup.select('.journal-content-article')
                    if 'PLANEJAMENT URBANÍSTIC VIGENT: LES NORMES SUBSIDIÀRIES DE LA SELVA DEL CAMP' in _text(a)]
        if len(articles) != 1:
            raise ValueError('Missing or ambiguous municipal planning catalogue')
        article = articles[0]
        # The observed paginacio_footer is a last-update label, not pagination.
        # Any actual paging control fails closed rather than truncating output.
        for a in soup.select('a[href]'):
            if ('next' in a.get('rel', []) or
                _text(a).casefold() in {'següent', 'següents', 'siguiente', 'next', '»', '›'} or
                a.find_parent(class_=re.compile(r'^(?:pagination|lfr-pagination|pager)$'))):
                if a['href'] not in {'', '#'} and a.get('aria-disabled') != 'true':
                    raise ValueError('Catalogue pagination detected; crawler must be extended')
        rows = {}
        base_id = None
        for li in article.select('li'):
            anchors = li.select('a[href]')
            if not anchors:
                if _text(li) == 'Plànols del planejament general':
                    continue
                raise ValueError('Unlinked catalogue item requires review')
            for anchor in anchors:
                title = _text(anchor)
                match = RPUC.fullmatch(anchor['href'])
                if not match:
                    raise ValueError('Unexpected catalogue dossier URL')
                # Regional plans are linked context, not municipal instruments.
                if title == 'Pla territorial general':
                    continue
                kind = _kind(title)
                if kind is None:
                    raise ValueError('Unknown planning instrument: ' + title)
                key = match[1]
                document = {'titulo': title, 'url': anchor['href'],
                            'tipo': 'expediente_rpuc', 'source_url': SOURCE}
                if key not in rows:
                    rows[key] = {
                        'id': 'la-selva-del-camp-proy-rpuc-' + key,
                        'municipio': 'La Selva del Camp', 'codigo_ine': '43145',
                        'provincia': 'Tarragona', 'titulo': _text(li), 'tipo': kind,
                        'descripcion': _text(li), 'fase': None, 'fecha': None,
                        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                        'url': SOURCE, 'url_documento': anchor['href'], 'rpuc_id': key,
                        # Namespaced register dossier grouping, not an invented municipal expte.
                        'expediente_grupo': 'RPUC ' + key,
                        'categoria': 'planeamiento urbanístico',
                        'source': 'ayuntamiento', 'origen': 'catalogo_planeamiento_municipal',
                        'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                        'publication_ready': False, 'limitations': LIMITATIONS,
                    }
                if document not in rows[key]['documentos']:
                    rows[key]['documentos'].append(document)
                if kind == 'normas_subsidiarias':
                    if base_id is not None and base_id != key:
                        raise ValueError('Ambiguous consolidated general plan')
                    base_id = key
        if not rows or base_id is None:
            raise ValueError('Empty catalogue or missing consolidated general plan')
        # General-plan sheets are siblings of the consolidated text's list, not
        # independent projects. Preserve all sheets under that same instrument.
        sheets = []
        for anchor in article.select('a[href]'):
            title = _text(anchor)
            if not title.startswith('PLÀNOL-'):
                continue
            url = urljoin(SOURCE, anchor['href'])
            if not url.startswith('https://seu-e.cat/documents/'):
                raise ValueError('Unexpected general-plan document URL')
            doc = {'titulo': title, 'url': url, 'tipo': 'plano', 'source_url': SOURCE}
            if doc not in sheets:
                sheets.append(doc)
        if not sheets:
            raise ValueError('General-plan sheets missing')
        rows[base_id]['documentos'].extend(sheets)
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=(10, 45), stream=True,
                          headers={'User-Agent': self.config.get('user_agent', 'municipio-la-selva-del-camp/1.0')}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 5_000_000:
                    raise ValueError('Catalogue response exceeds 5 MB; no partial output written')
                chunks.append(chunk)
            body = b''.join(chunks)
        rows = self.parse_projects(body.decode('utf-8'))
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'planejament-live.html').write_bytes(body)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'publication_ready': False, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full catalogue replacement: no date cutoff, append-only duplicates or
        # inferred removals from a silently incomplete crawl.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
