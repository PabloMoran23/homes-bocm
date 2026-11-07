"""Municipal RPUC planning inventory, linked by the official transparency portal."""
from __future__ import annotations

import gzip
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import requests

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPIO = 'Santa Coloma de Farners'
INE = '17180'
PORTAL = ('https://seu-e.cat/ca/web/santacolomadefarners/govern-obert-i-transparencia/'
          'accio-de-govern-i-normativa/urbanisme/planejament-urbanistic')
HOST = 'https://planejamenturbanisme.territori.gencat.cat'
API = HOST + '/RPUC-portal/rest/consulta/'
VIEWER = HOST + '/rpucportal/index.html#/consulta/detallExpedient/'
LIMITATIONS = [
    'Partial coverage: municipal planning dossiers returned by the public RPUC basic search only; '
    'not a complete inventory of works, pending instruments or granted licences.',
    'Supramunicipal dossiers whose primary municipality is elsewhere are excluded.',
    'The municipal land/housing inventory is excluded: it is not a project or planning instrument.',
    'Document links and register metadata retained; PDF contents and vector geometry not extracted.',
    'Register approval dates are not independently interpreted as a specific approval phase; '
    'generic listing data is retained separately without assuming date semantics.',
    'No verified project coordinates; publication_ready is false.',
]


def _identifier(value: Any) -> str:
    text = str(value)
    if not re.fullmatch(r'[1-9][0-9]*', text):
        raise ValueError('Invalid RPUC identifier')
    return text


def _date(value: Any) -> str | None:
    if value is None or value == '':
        return None
    # Detail fields are explicitly dated ISO strings, unlike listing `data`.
    return date.fromisoformat(value).isoformat()


class SantaColomaDeFarnersAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.scf.cat')

    def _fetch(self, endpoint: str, params: dict) -> Any:
        with requests.get(API + endpoint, params=params, timeout=(10, 45), stream=True,
                          headers={'User-Agent': 'municipio-santa-coloma-de-farners/1.0'}) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 8_000_000:
                    raise ValueError('RPUC response exceeds 8 MB; no partial output written')
                chunks.append(chunk)
            raw = b''.join(chunks)
            payload = json.loads(raw)
            capture = self.config.get('capture_dir')
            if capture:
                folder = Path(capture)
                folder.mkdir(parents=True, exist_ok=True)
                key = params.get('codiExpedient', params.get('firstRecord', 0))
                (folder / f'{endpoint}-{key}.json.gz').write_bytes(gzip.compress(raw))
            self._source_urls.append(response.url)
            return payload

    def _inventory(self) -> tuple[list[dict], int]:
        entries, seen, total, offset, page_number = [], set(), None, 0, 1
        while total is None or offset < total:
            payload = self._fetch('basica', {
                'municipi': INE, 'idioma': 'ca', 'firstRecord': page_number,
                'rpp': 20, 'sortDirection': 'asc',
            })
            count, page = payload.get('totals'), payload.get('llistat')
            if type(count) is not int or count < 0 or not isinstance(page, list):
                raise ValueError('Unexpected RPUC pagination schema')
            if total is not None and total != count:
                raise ValueError('RPUC inventory changed during pagination; retry snapshot')
            total = count
            if total > 10000:
                raise ValueError('RPUC inventory exceeds reviewed bound')
            if not page and offset < total:
                raise ValueError('RPUC pagination ended before advertised total')
            for entry in page:
                key = _identifier(entry.get('codi'))
                if key in seen:
                    raise ValueError('Repeated RPUC dossier during pagination')
                seen.add(key)
                if entry.get('municipi') == MUNICIPIO:
                    entries.append(entry)
            offset += len(page)
            # Despite its name, firstRecord is a one-based page number in RPUC.
            page_number += 1
            if offset > total:
                raise ValueError('RPUC page exceeds advertised total')
        return entries, total

    @staticmethod
    def parse_project(entry: dict, detail: dict) -> dict:
        key = _identifier(entry.get('codi'))
        if (_identifier(detail.get('codintExp')) != key or
                entry.get('municipi') != MUNICIPIO or detail.get('municipi') != MUNICIPIO):
            raise ValueError('RPUC dossier identity or municipality mismatch')
        if not detail.get('tema') or not detail.get('tipologiaCA') or not detail.get('numComplet'):
            raise ValueError('Missing planning instrument metadata')
        docs = {}
        for doc in detail.get('documents') or []:
            doc_id = _identifier(doc.get('idDocument'))
            docs[doc_id] = {
                'id': doc_id, 'titulo': doc.get('nomDocument'),
                'url': API + f'documents?documentId={doc_id}&downloadType=attachment&idioma=ca',
                'source': 'RPUC',
            }
        return {
            'id': 'santa-coloma-de-farners-rpuc-' + key,
            'municipio': MUNICIPIO, 'codigo_ine': INE, 'provincia': 'Girona',
            'titulo': detail['tema'], 'tipo': detail['tipologiaCA'].strip(),
            'categoria': 'gestion urbanistica' if detail['tipologiaCA'] == 'Conveni urbanístic' else 'planeamiento urbanistico',
            'expediente': detail['numComplet'], 'rpuc_id': key,
            'fase': None, 'fecha': None, 'fecha_acuerdo': None,
            'fecha_aprob': _date(detail.get('dataAprovacio')),
            'fecha_publicacion': _date(detail.get('dataPublicacio')),
            'url': VIEWER + key, 'source': 'ayuntamiento', 'origen': 'RPUC',
            'source_inventory': PORTAL,
            'url_fuente_datos': API + f'detall?codiExpedient={key}&idioma=ca&cercaPublic=false',
            'documentos': list(docs.values()),
            'registro': {'vigencia': entry.get('vigencia'), 'registrat': entry.get('registrat'),
                         'data_listado_sin_semantica': entry.get('data'),
                         'assentaments': detail.get('assentaments'),
                         'referenciaButlletins': detail.get('referenciaButlletins')},
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        }

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        self._source_urls = [PORTAL]
        inventory, total = self._inventory()
        if not inventory:
            raise ValueError('No municipal planning dossiers found; review source')
        rows, excluded_resources = [], []
        for entry in inventory:
            if entry.get('instrumentca', '').strip() == 'Inventari municipal sòl i habitatge':
                excluded_resources.append({'rpuc_id': entry['codi'], 'titulo': entry.get('tema'),
                                           'reason': 'Land/housing inventory, not a planning instrument or project'})
                continue
            detail = self._fetch('detall', {'codiExpedient': entry['codi'],
                                         'idioma': 'ca', 'cercaPublic': 'false'})
            rows.append(self.parse_project(entry, detail))
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temporary = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                             encoding='utf-8')
        temporary.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'inventory_total': total,
                'excluded_supramunicipal': total - len(inventory),
                'excluded_non_projects': excluded_resources,
                'source_urls': self._source_urls, 'limitations': LIMITATIONS,
                'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Refresh all pages: modifications can affect historical dossiers.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
