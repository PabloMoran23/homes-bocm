"""Official current planning inventory, without inferred dates or geometry."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from municipio.adapters.portal import AyuntamientoAdapter

SETTINGS = {'slug': 'chipiona', 'nombre': 'Chipiona', 'ine': '11016', 'province': 'Cádiz', 'region': 'andalucia', 'cls': 'ChipionaAyuntamientoAdapter', 'url': 'https://www.aytochipiona.com/delegaciones/urbanismo/', 'mode': 'links'}


def parse_inventory(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    records = {}
    for a in soup.select('h3.package-title a[href]'):
        title = a.get_text(' ', strip=True)
        target = urljoin(url, a['href'])
        if urlparse(target).hostname != 'www.aytochipiona.com' or not urlparse(target).path.startswith('/download/'):
            continue
        if not re.match(r'^(Plan General|Modificaci[oó]n|Rectificaci[oó]n|Correcci[oó]n|Plan Especial|Estudio de Detalle|Proyecto de)\b', title, re.I):
            continue
        key = 'chipiona-plan-' + hashlib.sha256(target.encode()).hexdigest()[:16]
        records[key] = {'id': key, 'municipio': 'Chipiona', 'codigo_ine': '11016', 'titulo': title,
                        'tipo': 'instrumento o proyecto urbanístico', 'url': target, 'inventory_url': url,
                        'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
                        'publication_ready': False, 'geometry_status': 'unavailable'}
    if not records:
        raise ValueError('No named planning/project packages found')
    return list(records.values())


class ChipionaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        response = requests.get(SETTINGS['url'], timeout=30, headers={'User-Agent': 'Mozilla/5.0 (compatible; municipal-inventory/1.0)'})
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(SETTINGS['url']).hostname:
            raise ValueError('Unexpected inventory redirect')
        rows = parse_inventory(response.text, response.url)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        return {'count': len(rows), 'written': len(rows), 'publication_ready': False, 'coverage': 'current_document_inventory'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'count': 0, 'disabled': True, 'reason': 'No verified public licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
