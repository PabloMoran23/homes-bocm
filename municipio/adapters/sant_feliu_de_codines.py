"""Planning instruments from Diputació de Barcelona's official CIDO inventory.

This is a partial publication history, not a register of all plans in force.
Environmental decisions retain their own provenance and never set plan phase.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://cido.diba.cat/normativa_local/6873748/'
          'planejament-urbanistic-ajuntament-de-sant-feliu-de-codines')
MUNICIPIO = 'Sant Feliu de Codines'
LIMITATIONS = [
    'Partial CIDO planning-publication history, not a complete inventory of plans in force or physical works.',
    'Urban-management agreements and court notices are excluded; no granted licences extracted.',
    'Dates are bulletin publication dates; agreement and approval dates are unknown.',
    'Linked bulletin documents retained as published; their contents are not parsed for dates or geometry.',
    'No verified coordinates or geometry; publication_ready is false.',
]
GRANGES_PLAN = "Pla especial urbanístic de millora rural a l'àmbit del sector Granges"
GRANGES_NORMS = "Normes subsidiàries de planejament a l'àmbit del sector Granges"
COMBINED = ('Normes subsidiàries de planejament del sector Granges, clau 8a, '
            'i el Pla especial per a la millora rural a la zona de Granges, clau 8a')


def _key(title: str) -> str:
    # The inventory spells the same road location both ', km 3' and ' Km 3'.
    return re.sub(r'[,\s]+', ' ', title.casefold()).strip()


def _titles(description: str) -> tuple[list[str], bool]:
    title = description.split(' / Anunci emès pel Departament de Territori', 1)[0]
    environmental = title.endswith(', informe ambiental estratègic')
    if environmental:
        title = title.removesuffix(', informe ambiental estratègic')
    if title == COMBINED:
        return [GRANGES_NORMS, GRANGES_PLAN], environmental
    if title == 'Normes subsidiàries de planejament del sector Granges':
        title = GRANGES_NORMS
    return [title], environmental


class SantFeliuDeCodinesAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug: str, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.santfeliudecodines.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        heading = soup.select_one('h2')
        if (not soup.title or f'| Ajuntament de {MUNICIPIO} |' not in soup.title.get_text()
                or not heading or heading.get_text(strip=True) != 'Planejament urbanístic'):
            raise ValueError('CIDO municipality or planning inventory identity changed')
        # Reviewed inventory is unpaginated. Fail closed if pagination appears,
        # including numbered controls, rather than quietly returning page one.
        if soup.select('[class*=pagin], a[rel~=next], link[rel~=next]'):
            raise ValueError('CIDO pagination detected: extend traversal before extraction')
        table = soup.select_one('table.adjunts')
        if not table or 'Data de publicació' not in table.get_text(' ', strip=True):
            raise ValueError('Missing CIDO publication table')
        groups: dict[str, dict[str, Any]] = {}
        for tr in table.select('tbody tr'):
            cells = tr.find_all('td', recursive=False)
            if len(cells) != 6 or not cells[0].select_one('time[datetime]'):
                raise ValueError('Malformed CIDO publication row')
            published = date.fromisoformat(cells[0].select_one('time')['datetime']).isoformat()
            parts = list(cells[3].stripped_strings)
            if len(parts) != 2:
                raise ValueError('Missing publication action or instrument description')
            action, description = parts
            if description.startswith(('Conveni urbanístic ', 'Sentència sobre ')):
                continue
            if not description.startswith(('Normes subsidiàries de planejament ', 'Pla especial urbanístic ')):
                raise ValueError('Unreviewed instrument category: ' + description)
            if action not in {'Aprovació inicial', 'Aprovació inicial de modificació',
                              'Aprovació definitiva', 'Aprovació definitiva de modificació'}:
                raise ValueError('Unreviewed planning publication action: ' + action)
            links = []
            for a in cells[4].select('a[href]'):
                url = a['href']
                # Ignore CIDO's malformed relative auxiliary links. Retain exact
                # official absolute URLs, including legacy bulletin query strings.
                if (urlparse(url).scheme in {'http', 'https'} and urlparse(url).hostname in
                        {'bop.diba.cat', 'portaldogc.gencat.cat', 'dogc.gencat.cat'}):
                    if url not in links:
                        links.append(url)
            if not links:
                raise ValueError('Planning publication lacks an official bulletin link')
            titles, environmental = _titles(description)
            for title in titles:
                key = _key(title)
                if key not in groups:
                    groups[key] = {
                        'id': 'sant-feliu-de-codines-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                        'municipio': MUNICIPIO, 'codigo_ine': '08210', 'provincia': 'Barcelona',
                        'titulo': title,
                        'tipo': 'modificacion_planeamiento' if title.startswith('Normes') else 'plan_especial',
                        'fase': None, 'fecha': None, 'fecha_publicacion': None,
                        'fecha_acuerdo': None, 'fecha_aprob': None,
                        'url': SOURCE, 'source': 'cido_diba', 'origen': 'inventario_oficial_planeamiento',
                        'documentos': [], 'lat': None, 'lon': None, 'geometry': None,
                        'publication_ready': False, 'cobertura': 'parcial',
                    }
                row = groups[key]
                document = {
                    'titulo': description, 'accion_publicada': action,
                    'fecha_publicacion': published, 'boletin': cells[1].get_text(strip=True),
                    'numero_boletin': cells[2].get_text(strip=True),
                    'url': links[0], 'enlaces': links, 'url_fuente': SOURCE,
                    'tipo_documento': 'informe_ambiental' if environmental else 'anuncio_planeamiento',
                    'relacion': 'publicacion_conjunta' if len(titles) > 1 else 'publicacion_del_instrumento',
                }
                if document not in row['documentos']:
                    row['documentos'].append(document)
        if not groups:
            raise ValueError('No genuine planning instruments in CIDO inventory')
        for row in groups.values():
            row['documentos'].sort(key=lambda d: (d['fecha_publicacion'], d['url']))
            notices = [d for d in row['documentos'] if d['tipo_documento'] == 'anuncio_planeamiento']
            if not notices:
                raise ValueError('Environmental decision alone is not a verified plan record')
            latest = notices[-1]
            row['fase'] = latest['accion_publicada']
            row['fecha_publicacion'] = latest['fecha_publicacion']
            row['url_documento'] = latest['url']
        return sorted(groups.values(), key=lambda row: row['id'])

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=(10, 40), stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-sant-feliu-de-codines/1.0'),
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'cido.diba.cat':
                raise ValueError('Unexpected CIDO redirect')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 3_000_000:
                    raise ValueError('CIDO response exceeds reviewed size; refusing partial extraction')
            html = bytes(body).decode('utf-8')
        rows = self.parse_projects(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'cido-live.html').write_bytes(body)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temp = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'publication_ready': False, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Refresh the complete unpaginated inventory; no date cutoff loses documents.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
