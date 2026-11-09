"""San Cibrao das Viñas: municipal-filtered Xunta planning register snapshots."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

REGISTER = ('https://territorioeurbanismo.xunta.gal/es/territorio-y-urbanismo/'
            'registro-de-ordenacion-del-territorio-y-urbanismo/buscador')
SOURCE = REGISTER + '?provincia=32&concello=677'
HEADERS = ['Instrumento', 'Tipo', 'Título', 'Fecha inscripción', 'Núm. Registro',
           'Provincia', 'Competencia de aprobación', 'Fecha de aprobación',
           'Fecha publicación DOGA', 'Fecha publicación BOP', 'Observaciones', 'Documento']
LIMITATIONS = [
    'Only instruments returned by the Xunta register municipal filter; not a complete municipal history or current consolidated plan.',
    'Document archive links retained as published; archive contents require CAPTCHA and are not extracted.',
    'Register dates may be inconsistent; values are preserved with chronology warnings, not corrected or inferred from filenames.',
    'No granted licences, project geometry or coordinates extracted.',
]


def page_url(page: int) -> str:
    return REGISTER + '?' + urlencode({'provincia': '32', 'concello': '677', **({'page': page} if page else {})})


def parse_page(html: str, source_url: str) -> tuple[list[dict], set[int]]:
    soup = BeautifulSoup(html, 'html.parser')
    for field, value in [('provincia', '32'), ('concello', '677')]:
        selected = soup.select_one(f'select[name="{field}"] option[selected]')
        if selected is None or selected.get('value') != value:
            raise ValueError('Register municipality/province filter not applied')
        if field == 'concello' and selected.get_text(' ', strip=True) != 'San Cibrao das Viñas':
            raise ValueError('Register municipality identifier changed')
    table = soup.select_one('#edit-table')
    if table is None or [h.get_text(' ', strip=True) for h in table.select('thead th')] != HEADERS:
        raise ValueError('Planning register table schema changed')
    rows = []
    for tr in table.select('tbody tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != len(HEADERS):
            raise ValueError('Unexpected or empty register row')
        values = [c.get_text(' ', strip=True) for c in cells]
        instrument, change, title, inscription, reference, province, authority, approval, doga, bop, notes, _ = values
        if province != 'Ourense' or not re.fullmatch(r'(?:ROTPG/(?:P|OT)/\d+/\d{4}|RPG/\d+/\d{4})', reference):
            raise ValueError('Invalid province or registration reference')
        if not instrument or not title:
            raise ValueError('Missing planning identity')
        def date_value(value):
            return None if value in {'', '---'} else datetime.strptime(value, '%d/%m/%Y').date().isoformat()
        dates = dict(zip(('fecha_inscripcion', 'fecha_aprob', 'fecha_publicacion_doga', 'fecha_publicacion_bop'),
                         map(date_value, (inscription, approval, doga, bop))))
        docs = {}
        for a in cells[11].select('a[href]'):
            url = urljoin(source_url, a['href'])
            if urlsplit(url).scheme not in {'http', 'https'}:
                raise ValueError('Unexpected archive URL')
            docs[url] = {'titulo': a.get_text(' ', strip=True), 'url': url,
                         'origen': 'Xunta ROTPG, columna Documento',
                         'contenido_extraido': False}
        if not docs:
            raise ValueError('Planning instrument missing document provenance')
        warnings = []
        if dates['fecha_aprob']:
            for field in ('fecha_inscripcion', 'fecha_publicacion_doga', 'fecha_publicacion_bop'):
                if dates[field] and dates[field] < dates['fecha_aprob']:
                    warnings.append(field + ' anterior a fecha_aprob en la fuente')
        rows.append({
            'id': 'san-cibrao-das-vinas-proy-' + reference.lower().replace('/', '-'),
            'municipio': 'San Cibrao das Viñas', 'codigo_ine': '32075', 'provincia': province,
            'titulo': title, 'tipo': 'planeamiento urbanístico', 'instrumento_original': instrument,
            'tipo_asiento_original': change, 'expediente': reference,
            'competencia_aprobacion': authority, **dates,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
            'fechas_originales': dict(zip(('inscripcion', 'aprobacion', 'publicacion_doga', 'publicacion_bop'),
                                         (inscription, approval, doga, bop))),
            'advertencias_fechas': warnings, 'observaciones': notes,
            'source': 'xunta', 'origen': 'registro_ordenacion_territorio_planeamiento_urbanistico',
            'url': source_url, 'source_dataset': SOURCE, 'source_urls': [source_url],
            'documentos': list(docs.values()), 'geometry': None, 'lat': None, 'lon': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        })
    pages = set()
    for a in soup.select('.pagination a[href], .pager a[href], a[rel="next"]'):
        url = urlsplit(urljoin(source_url, a['href']))
        query = parse_qs(url.query)
        if (url.netloc != urlsplit(REGISTER).netloc or url.path != urlsplit(REGISTER).path
                or query.get('provincia') != ['32'] or query.get('concello') != ['677']
                or not re.fullmatch(r'\d+', query.get('page', [''])[0])):
            raise ValueError('Pagination lost municipal scope or changed format')
        pages.add(int(query['page'][0]))
    return rows, pages


def merge_rows(target: dict, rows: list[dict]) -> None:
    """One registered instrument per reference; retain all its document links."""
    for row in rows:
        prior = target.get(row['id'])
        if prior is None:
            target[row['id']] = row
            continue
        volatile = {'url', 'source_urls', 'documentos'}
        if {k: v for k, v in prior.items() if k not in volatile} != {k: v for k, v in row.items() if k not in volatile}:
            raise ValueError('Conflicting metadata for one registered instrument')
        prior['source_urls'] = sorted(set(prior['source_urls'] + row['source_urls']))
        prior['documentos'] = list({d['url']: d for d in prior['documentos'] + row['documentos']}.values())


class SanCibraoDasVinasAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        pending, visited, records, source_urls = {0}, set(), {}, []
        capture_dir = Path(self.config['capture_dir']) if self.config.get('capture_dir') else None
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-san-cibrao-das-vinas/1.0'
            while pending:
                page = min(pending)
                pending.remove(page)
                url = page_url(page)
                response = session.get(url, timeout=40)
                response.raise_for_status()
                if urlsplit(response.url).path != urlsplit(REGISTER).path:
                    raise ValueError('Register redirected away from inventory')
                response.encoding = 'utf-8'
                if capture_dir:
                    (capture_dir / f'registro-live-{page}.html').write_bytes(response.content)
                rows, linked_pages = parse_page(response.text, url)
                if not rows:
                    raise ValueError('Empty inventory requires review')
                # A server ignoring page=N must not silently return just page zero.
                if visited and all(row['id'] in records for row in rows):
                    raise ValueError('Repeated register page without new instruments')
                merge_rows(records, rows)
                visited.add(page)
                source_urls.append(url)
                pending.update(linked_pages - visited)
        if visited != set(range(max(visited) + 1)):
            raise ValueError('Non-contiguous pagination requires review')
        self._write(out_jsonl, list(records.values()))
        return {'status': 'ok', 'rows': len(records), 'pages': len(visited),
                'source_urls': source_urls, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
