"""Municipal POUM amendment inventory, not a register of granted licences."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.rodadeter.cat'
SOURCE = BASE + '/ajuntament-seu-electronica/informacio-oficial/16-urbanisme/planejament-urbanistic/modificacions-del-poum'
LIMITATIONS = [
    'Partial coverage: only the municipal Modificacions del POUM inventory; not the base POUM, TUC, public works, news or a complete RPUC inventory.',
    'Stages describe the linked municipal documents, not necessarily the latest legal status. RPUC dossiers are retained as references, not crawled.',
    'No explicit publication or agreement dates in inventory rows; page modification timestamp is not an approval date.',
    'No verified project geometry; coordinates remain null and publication_ready is false.',
    'No verified granted-licence register; licence extraction and scheduling are disabled.',
]


def parse_projects(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#contingut section')
    if content is None or not content.h1 or content.h1.get_text(' ', strip=True) != 'Modificacions del POUM':
        raise ValueError('Municipal amendment inventory missing or changed')
    for a in soup.select('a[href], link[href]'):
        label = a.get_text(' ', strip=True).casefold()
        href = a['href']
        if ('next' in a.get('rel', []) or label in {'següent', 'siguiente', 'next', '›', '»'}
                or re.search(r'[?&](?:page|pagina|pag|offset|start)=', href, re.I)):
            raise ValueError('Pagination detected; review crawler before emitting a partial snapshot')
    if content.select('.pagination, .paginacio, .paginacion, [data-next-page]'):
        raise ValueError('Pagination controls detected')
    tables = content.select('table')
    if len(tables) != 1 or [x.get_text(' ', strip=True) for x in tables[0].select('thead th')] != ['Títol', 'Document', 'Url']:
        raise ValueError('Amendment table schema changed')
    references = {}
    for a in content.select('article a[href]'):
        if re.fullmatch(r'https://dtes\.gencat\.cat/rpucportal/#/consulta/detallExpedient/\d+', a['href']):
            number = a.get_text(strip=True)
            if not number.isdigit():
                raise ValueError('Unattributed RPUC reference')
            if number in references and references[number] != a['href']:
                raise ValueError('Conflicting RPUC references')
            references[number] = a['href']
    grouped = {}
    for tr in tables[0].select('tbody tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 3:
            raise ValueError('Unexpected amendment row')
        title = cells[0].get_text(' ', strip=True)
        match = re.match(r'^Modificació puntual n\.\s*(\d+) del POUM\b', title)
        if not match:
            raise ValueError('Unrecognized instrument in amendment inventory')
        number = str(int(match[1]))
        documents = {}
        for a in tr.select('a[href]'):
            url = urljoin(SOURCE, a['href'])
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or parsed.hostname != 'www.rodadeter.cat' or not parsed.path.startswith('/media/repository/') or not parsed.path.lower().endswith('.pdf'):
                raise ValueError('Unexpected municipal document URL')
            documents.setdefault(url, {'titulo': title, 'url': url, 'source_url': SOURCE})
        if not documents:
            raise ValueError('Instrument lacks technical documents')
        phase = 'aprobación inicial' if '(aprovació inicial)' in title.casefold() else None
        row = grouped.setdefault(number, {
            'id': 'roda-de-ter-poum-mod-' + number,
            'municipio': 'Roda de Ter', 'codigo_ine': '08183', 'provincia': 'Barcelona',
            'titulo': title, 'tipo': 'modificacion_planeamiento', 'fase': phase,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_modificaciones_poum',
            'numero_modificacion': number, 'documentos': [],
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'No verified geometry in municipal inventory',
            'stage_scope': 'Linked municipal document; latest legal status not verified',
        })
        # One instrument can have several documents; conflicting stages must be reviewed.
        if row['fase'] != phase:
            raise ValueError('Conflicting document stages for one instrument')
        known = {doc['url'] for doc in row['documentos']}
        row['documentos'].extend(doc for url, doc in documents.items() if url not in known)
    if not grouped:
        raise ValueError('No usable municipal planning instruments')
    if set(references) - set(grouped):
        raise ValueError('RPUC reference has no corresponding inventory instrument')
    for number, row in grouped.items():
        row['url_documento'] = row['documentos'][0]['url']
        if number in references:
            row['rpuc_url'] = references[number]
            row['rpuc_id'] = references[number].rsplit('/', 1)[-1]
            row['documentos'].append({'titulo': 'Expedient RPUC — modificació ' + number,
                                      'url': references[number], 'source_url': SOURCE})
    return sorted(grouped.values(), key=lambda row: int(row['numero_modificacion']))


class RodaDeTerAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=(10, 40), stream=True,
                          headers={'User-Agent': self.config.get('user_agent', 'municipio-roda-de-ter/1.0')}) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname != 'www.rodadeter.cat':
                raise ValueError('Unexpected inventory redirect')
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 3_000_000:
                    raise ValueError('Inventory exceeds response limit')
            html = body.decode('utf-8')
        rows = parse_projects(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'modificacions-live.html').write_bytes(body)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'limitations': LIMITATIONS, 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Finite unpaginated inventory, refreshed completely; no date-based filtering.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': LIMITATIONS[-1]}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
