"""Iniesta's public planning folders; one instrument per documented folder."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = 'iniesta.sedelectronica.es'
INVENTORY = f'https://{HOST}/transparency/bef8cbc5-581e-4c0b-8163-aaa156086a1c/'
INSTRUMENT = re.compile(r'^(?:PLAN DE ORDENACIÓN MUNICIPAL|MODIFICACIÓN PUNTUAL|PLAN PARCIAL|PLAN ESPECIAL|ESTUDIO DE DETALLE)\b', re.I)


def official_url(url: str, prefix: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != HOST or not parsed.path.startswith(prefix):
        raise ValueError(f'Unexpected official source URL: {url}')
    return url


def parse_listing(html: str) -> list[dict]:
    """Read only the transparency table, never navigation or unrelated notices.

    Fail closed on pagination: a newly paginated inventory needs crawler review,
    rather than silently exporting its first page.
    """
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.select_one('table.TransparencyListPanel')
    if table is None:
        raise ValueError('Missing transparency inventory table')
    for a in soup.select('a, button, input'):
        label = ' '.join([a.get_text(' ', strip=True), a.get('value', ''), a.get('title', '')]).lower()
        disabled = a.has_attr('disabled') or 'disabled' in a.get('class', []) or a.get('aria-disabled') == 'true'
        if not disabled and (a.get('href') or a.get('onclick')) and (
            any(t in label for t in ('mostrar más', 'mostrar mas', 'siguiente', 'next'))
            or 'next' in a.get('rel', [])
        ):
            raise ValueError('Pagination detected; refusing partial inventory')
    entries = []
    for a in table.select('td.class_name a.gIconLink'):
        label = a.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            count = re.search(r'\(\s*(\d+)\s*\)\s*$', label)
            if not count:
                raise ValueError('Folder lacks advertised document count')
            action = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
            if not action:
                raise ValueError('Folder lacks navigation action')
            entries.append({'kind': 'folder', 'titulo': label[:count.start()].strip(),
                            'count': int(count.group(1)), 'action': action.group(1)})
        else:
            target = official_url(a.get('href', ''), '/preview-document/')
            entries.append({'kind': 'document', 'titulo': label, 'url': target})
    if not entries and 'No se han encontrado elementos' not in soup.get_text(' ', strip=True):
        raise ValueError('Unrecognized empty inventory')
    return entries


def instrument_record(title: str, url: str, documents: list[dict]) -> dict:
    if not INSTRUMENT.match(title) or not documents:
        raise ValueError('Instrument requires a supported title and source documents')
    return {
        'id': 'iniesta-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Iniesta', 'codigo_ine': '16113', 'provincia': 'Cuenca',
        'titulo': title, 'tipo': 'planeamiento_urbanistico',
        'url': url, 'inventory_url': INVENTORY, 'source': 'ayuntamiento',
        'origen': 'portal_transparencia_planeamiento',
        'documentos': [{'titulo': d['titulo'], 'url': d['url'], 'inventory_url': url}
                       for d in documents],
        'descripcion': 'Instrumento documental publicado en el portal de transparencia; no acredita aprobación definitiva ni vigencia.',
        'publication_ready': False, 'geometry_status': 'unavailable',
    }


class IniestaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, session, url, **kwargs):
        official_url(url, '/')
        response = session.get(url, timeout=40, **kwargs)
        response.raise_for_status()
        official_url(response.url, '/')
        self._source_urls.append(url)
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20]
            (directory / (name + '.html')).write_bytes(response.content)
            (directory / (name + '.json')).write_text(json.dumps({
                'url': url, 'response_url': response.url, 'status': response.status_code,
                'ajax_location': response.headers.get('Ajax-Location'),
            }, ensure_ascii=False), encoding='utf-8')
        return response

    def backfill_proyectos(self, out_jsonl: Path):
        self._source_urls = []
        rows, skipped = [], []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; IniestaPlanningInventory/1.0)'
            entries = parse_listing(self._get(session, INVENTORY).text)
            if not entries:
                raise ValueError('Planning inventory is empty')
            for entry in entries:
                if entry['kind'] != 'folder' or not INSTRUMENT.match(entry['titulo']):
                    raise ValueError('Unreviewed planning inventory entry')
                action_url = official_url(urljoin(INVENTORY, entry['action']), '/')
                response = self._get(session, action_url, headers={'Wicket-Ajax': 'true', 'Referer': INVENTORY})
                location = response.headers.get('Ajax-Location')
                if not location:
                    raise ValueError('Missing Wicket folder redirect')
                folder_url = official_url(urljoin(action_url, location), '/transparency/')
                contents = parse_listing(self._get(session, folder_url).text)
                if any(d['kind'] != 'document' for d in contents):
                    raise ValueError('Nested instrument folder requires review')
                docs = {d['url']: d for d in contents}
                if len(docs) != entry['count']:
                    raise ValueError('Advertised document count differs from extracted count')
                if not docs:
                    skipped.append({'titulo': entry['titulo'], 'url': folder_url, 'reason': 'empty_folder'})
                    continue
                rows.append(instrument_record(entry['titulo'], folder_url, list(docs.values())))
        if not rows:
            raise ValueError('No documented planning instruments')
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(output)
        return {'count': len(rows), 'written': len(rows), 'source_urls': list(dict.fromkeys(self._source_urls)),
                'skipped': skipped, 'coverage': 'current_planning_transparency_folders',
                'limitations': ['Only section 7.1 planning; not a complete project or licence register.',
                                'No approval dates, current legal validity or coordinates inferred.',
                                'Document links retained; PDF contents are not automatically parsed.',
                                'Pagination or nested folders cause failure rather than partial output.']}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        raise NotImplementedError('Licences disabled: no verified public grants inventory')

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
