"""Municipal PGO document inventory; no claim of approval or complete coverage."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://transparencia.vallegranrey.es/ordenacion-del-territorio/plan-de-ordenacion/'
DOCUMENT_PATH = '/media/r/ordenacion-del-territorio/plan-de-ordenacion/'
LIMITATIONS = [
    'Cobertura parcial: documentos del nuevo PGO en el inventario municipal, no todos los proyectos u obras.',
    'Se excluyen documentos insulares, planos sin atribución municipal, obras públicas y hojas de obras mayores.',
    'Última actualización es metadato del documento; no acredita publicación inicial ni aprobación del PGO.',
    'Sin geometría verificada, sin licencias y sin afirmación de vigencia o fase actual del plan.',
]


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('main')
    if main is None:
        raise ValueError('Missing municipal inventory main container')
    # No reviewed pagination exists. Fail closed if the portal adds it.
    for a in main.select('a[href]'):
        if (a.get('rel') and 'next' in a['rel']) or re.search(
            r'^(siguiente|next|[»›])$', a.get_text(' ', strip=True), re.I
        ) or re.search(r'[?&](page|pagina|offset)=', a['href'], re.I):
            raise ValueError('Inventory pagination detected; crawler review required')
    if main.select('.pagination, .paginator, nav[aria-label*="agin"]'):
        raise ValueError('Inventory pagination detected; crawler review required')
    documents = {}
    for tr in main.select('table tbody tr'):
        cells = tr.find_all('td', recursive=False)
        if not cells:
            continue
        title = cells[0].get_text(' ', strip=True)
        if not re.search(r'\bPGO\b|Plan General de Ordenaci[oó]n', title, re.I):
            continue
        if re.search(r'licencia|solicitud de licencia|modelo|formulario', title, re.I):
            continue
        if len(cells) != 3:
            raise ValueError('PGO document table schema changed')
        formats = {}
        for a in cells[1].select('a[href]'):
            target = urljoin(url, a['href'])
            parsed = urlparse(target)
            extension = Path(parsed.path).suffix.lower().lstrip('.')
            if (parsed.scheme != 'https' or parsed.hostname != urlparse(SOURCE).hostname
                    or not parsed.path.startswith(DOCUMENT_PATH) or extension not in {'pdf', 'txt'}):
                raise ValueError('Unexpected PGO document target')
            formats[target] = {'formato': extension, 'url': target}
        if not any(item['formato'] == 'pdf' for item in formats.values()):
            raise ValueError('PGO document lacks its source PDF')
        key = next(item['url'] for item in formats.values() if item['formato'] == 'pdf')
        documents[key] = {
            'titulo': title,
            'formatos': list(formats.values()),
            'ultima_actualizacion_texto': cells[2].get_text(' ', strip=True),
            'inventory_url': url,
        }
    if not documents:
        raise ValueError('No municipal PGO source documents found')
    return [{
        'id': 'valle-gran-rey-pgo',
        'municipio': 'Valle Gran Rey',
        'codigo_ine': '38049',
        'provincia': 'Santa Cruz de Tenerife',
        'titulo': 'Plan General de Ordenación de Valle Gran Rey',
        'tipo': 'planeamiento_urbanistico',
        'url': url,
        'source': 'ayuntamiento',
        'origen': 'inventario_documental_pgo',
        'documentos': list(documents.values()),
        'publication_ready': False,
        'geometry_status': 'unavailable',
        'limitaciones': LIMITATIONS,
    }]


class ValleGranReyAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={
            'User-Agent': 'municipio-inventory/1.0',
        })
        response.raise_for_status()
        if response.url.rstrip('/') != SOURCE.rstrip('/'):
            raise ValueError('Unexpected municipal inventory redirect')
        response.encoding = 'utf-8'
        rows = parse_inventory(response.text, response.url)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(output)
        return {'count': len(rows), 'written': len(rows), 'source_urls': [response.url],
                'coverage': 'municipal_pgo_document_inventory', 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full current snapshot; state does not imply historical coverage.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        raise NotImplementedError('Licencias disabled: no granted-licence extraction implemented')

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
