"""Named planning instruments in the official municipal document inventory."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://casarrubiosdelmonte.es/ayuntamiento/normativa-urbanistica/'
HOSTS = {'casarrubiosdelmonte.es', 'www.casarrubiosdelmonte.es'}


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                   if unicodedata.category(c) != 'Mn')


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.select('.wpr-accordion-item-wrap'):
        raise ValueError('Municipal planning accordion missing')
    for a in soup.select('a[href]'):
        label = normalize(a.get_text(' ', strip=True))
        if ('next' in a.get('rel', []) or label in {'siguiente', 'next', '»', '›'}
                or re.search(r'/(?:page|pagina)/\d|[?&](?:paged|page)=\d', a['href'])):
            raise ValueError('Pagination detected; inventory must be reviewed before extraction')
    # Only explicitly identified instruments. Unattributed general maps and
    # standalone building ordinances are outside this deliberately narrow scope.
    groups = {}
    for block in soup.select('.wpr-accordion-item-wrap'):
        for a in block.select('a[href]'):
            target = urljoin(url, a['href'])
            parsed = urlparse(target)
            path = normalize(unquote(parsed.path))
            if parsed.scheme != 'https' or parsed.hostname not in HOSTS or not path.endswith('.pdf'):
                continue
            title = a.get_text(' ', strip=True)
            label = normalize(title)
            key = None
            if '/documentos/monteboyal/' in path and 'modificacion' in path and 'art-63' in path:
                key, heading = 'monte-boyal-art63', title
            elif '/documentos/urbanismo/' in path:
                if 'monte' in path and 'boyal' in path:
                    key, heading = 'monte-boyal', 'Plan Parcial Polígono Industrial Monte Boyal'
                elif 'calypo' in path or ('calypo' in label and 'fado' in label):
                    key, heading = 'calypo-fado', 'Plan Parcial Urbanización Calypo-Fado'
                elif 'guindales' in path or 'guindales' in label or Path(path).name in {'024.pdf', '026.pdf'}:
                    key, heading = 'los-guindales', 'Plan Parcial Urbanización Los Guindales'
                elif 'normas_subsidiarias_de_planeamiento' in path:
                    key, heading = 'normas-subsidiarias', 'Normas Subsidiarias de Planeamiento'
            if key is None:
                continue
            if key not in groups:
                groups[key] = {
                    'id': 'casarrubios-del-monte-plan-' + key,
                    'municipio': 'Casarrubios del Monte', 'codigo_ine': '45041',
                    'provincia': 'Toledo', 'titulo': heading,
                    'tipo': 'modificacion_planeamiento' if key.endswith('art63') else 'planeamiento_urbanistico',
                    'url': target, 'inventory_url': url, 'source': 'ayuntamiento',
                    'origen': 'inventario_documental_planeamiento',
                    'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                    'documentos': [],
                }
            docs = groups[key]['documentos']
            if target not in {d['url'] for d in docs}:
                docs.append({'titulo': title, 'url': target, 'inventory_url': url})
    if not groups:
        raise ValueError('No named planning documents found in municipal inventory')
    return list(groups.values())


class CasarrubiosDelMonteAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)
        return {'count': len(rows), 'written': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=40, headers={'User-Agent': 'municipal-planning-inventory/1.0'})
        response.raise_for_status()
        if urlparse(response.url).hostname not in HOSTS:
            raise ValueError('Unexpected source redirect')
        rows = parse_inventory(response.text, response.url)
        return {**self._write(out_jsonl, rows), 'source_urls': [response.url],
                'coverage': 'named_planning_document_inventory', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'disabled': True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
