"""Carral's municipal PXOM document inventory (one instrument, many documents)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE_URL = 'https://carral.es/pxom-carral/'


def parse_inventory(html: str, source_url: str = SOURCE_URL) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('article .entry-content')
    if content is None:
        raise ValueError('Missing municipal PXOM inventory content')
    # This is a single document index, not a news archive. Refuse newly split
    # inventories until their traversal has been reviewed, never emit page one.
    if soup.select('a[rel~=next], .pagination, .page-links, .avia_pagination'):
        raise ValueError('Paginated inventory requires reviewed traversal')
    for a in content.select('a[href]'):
        if re.search(r'^(seguinte|siguiente|next|[»›])$', a.get_text(' ', strip=True), re.I):
            raise ValueError('Paginated inventory requires reviewed traversal')
    text = content.get_text(' ', strip=True)
    title = re.search(
        r'plan xeral de ordenación municipal \(PXOM\) do Concello de Carral', text, re.I
    )
    index = content.find('ol', recursive=False)
    if not title or index is None or 'aprobado inicialmente' not in text.lower():
        raise ValueError('Unrecognized Carral initial-approval document inventory')
    documents = {}
    for a in content.select('a[href]'):
        label = a.get_text(' ', strip=True)
        # An allegation template is not part of the instrument or a licence.
        if re.search(r'instancia|modelo|alegaci[oó]ns', label, re.I):
            continue
        url = urljoin(source_url, a['href'])
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in {'carral.es', 'www.carral.es'}:
            continue
        if not parsed.path.lower().endswith('.pdf'):
            continue
        documents.setdefault(url, {
            'titulo': label,
            'url': url,
            'inventory_url': source_url,
            'tipo': 'documento_plan' if index in a.parents else 'anuncio_tramitacion',
        })
    plan_docs = [d for d in documents.values() if d['tipo'] == 'documento_plan']
    if not any('MEMO' in d['titulo'].upper() for d in plan_docs) or not any(
        'NORM' in d['titulo'].upper() for d in plan_docs
    ):
        raise ValueError('Missing core memory or normative documents')
    return [{
        'id': 'carral-pxom-aprobacion-inicial',
        'municipio': 'Carral', 'codigo_ine': '15021', 'provincia': 'A Coruña',
        'titulo': title.group(0), 'tipo': 'planeamiento_urbanistico',
        'url': source_url, 'inventory_url': source_url,
        'source': 'ayuntamiento', 'origen': 'inventario_documental_pxom',
        'documentos': list(documents.values()),
        'estado_documentado': 'aprobacion_inicial',
        'descripcion': 'Documentación de la versión de aprobación inicial publicada por el Concello. '
                       'No acredita la fase actual ni aprobación definitiva. La página indica que '
                       'prevalece la copia en papel diligenciada sobre la documentación digital.',
        'coverage': 'Solo el inventario documental municipal PXOM; no todo el planeamiento ni obras.',
        'publication_ready': False, 'geometry_status': 'unavailable',
    }]


class CarralAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE_URL, timeout=45, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'
        })
        response.raise_for_status()
        if urlparse(response.url).hostname not in {'carral.es', 'www.carral.es'} or urlparse(response.url).path != '/pxom-carral/':
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'pxom.html').write_text(response.text, encoding='utf-8')
        return {**self._write(out_jsonl, rows), 'source_urls': [response.url],
                'coverage': 'municipal_pxom_document_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Re-fetch the entire unpaginated index to catch added/removed documents.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
