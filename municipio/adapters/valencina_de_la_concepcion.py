"""Current official PGOM document inventory; one instrument, many documents."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.valencinadelaconcepcion.es/es/pgom/documentacion/index.html'
HOST = 'www.valencinadelaconcepcion.es'
LIMITATIONS = [
    'Partial municipal coverage: only the current PGOM documentation inventory.',
    'Document sections are source labels, not evidence of approval or legal validity.',
    'No verified agreement/publication dates or project geometry extracted.',
    'No granted licence register; forms, procurement and news excluded.',
    'Document links retained; PDF contents are not parsed by this adapter.',
]


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    if not re.search(r'Documentación disponible asociada al PGOM de Valencina de la Concepción', text):
        raise ValueError('Missing official Valencina PGOM inventory identity')
    # This source is a single complete document page. Fail if it becomes paged;
    # never quietly ingest only the first batch of a changed inventory.
    if soup.select('[rel~=next], .pagination, .pager, [class*=pagin]') or any(
        re.fullmatch(r'siguiente|next|»|›', a.get_text(' ', strip=True), re.I)
        for a in soup.select('a[href]')
    ):
        raise ValueError('Pagination detected; review crawler before extracting')
    docs = {}
    sections = []
    for block in soup.select('.download-block'):
        heading = block.select_one('.title')
        section = heading.get_text(' ', strip=True) if heading else ''
        if not section or not block.select('table a[href]'):
            raise ValueError('Document section is empty or changed')
        sections.append(section)
        for a in block.select('table a[href]'):
            url = urljoin(source_url, a['href'])
            parsed = urlparse(url)
            title = a.get_text(' ', strip=True)
            if (parsed.scheme != 'https' or parsed.hostname != HOST
                    or not parsed.path.startswith('/export/sites/valencina/')
                    or not parsed.path.lower().endswith('.pdf') or not title):
                raise ValueError('Unexpected document link in PGOM inventory')
            doc = docs.setdefault(url, {'titulo': title, 'url': url,
                                        'secciones': [], 'source_url': source_url})
            if section not in doc['secciones']:
                doc['secciones'].append(section)
    # Require actual planning documentation, not merely a consultation/form page.
    if not docs or not any(re.search(r'AVANCE.*MEMORIA', d['titulo'], re.I) for d in docs.values()):
        raise ValueError('No substantive PGOM advance documentation found')
    return [{
        'id': 'valencina-de-la-concepcion-pgom',
        'municipio': 'Valencina de la Concepción', 'codigo_ine': '41096',
        'provincia': 'Sevilla',
        'titulo': 'Plan General de Ordenación Municipal (PGOM) de Valencina de la Concepción',
        'tipo': 'planeamiento_urbanistico', 'url': source_url,
        'source': 'ayuntamiento', 'origen': 'inventario_documental_pgom',
        'descripcion': 'Documentación municipal del PGOM agrupada por instrumento. '
                       'Secciones publicadas: ' + '; '.join(dict.fromkeys(sections)),
        'documentos': list(docs.values()),
        'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
        'geometry': None, 'lat': None, 'lon': None,
        'geometry_status': 'unavailable', 'publication_ready': False,
        'limitations': list(LIMITATIONS),
    }]


class ValencinaDeLaConcepcionAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(output)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'municipio-valencina-inventory/1.0',
        })
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Unexpected inventory redirect')
        response.encoding = 'utf-8'
        rows = parse_inventory(response.text, response.url)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'documentacion-live.html').write_text(response.text, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'count': len(rows), 'written': len(rows),
                'documents': len(rows[0]['documentos']), 'source_urls': [response.url],
                'coverage': 'current_pgom_document_inventory', 'limitations': list(LIMITATIONS)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Refresh the entire current inventory; no incremental cutoff is applied.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified granted licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
