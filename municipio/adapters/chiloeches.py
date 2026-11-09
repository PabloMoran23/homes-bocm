"""Municipal POM document inventory; one record per planning instrument."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://chiloeches.es/urbanismo/'


def _normal(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.upper())
                   if not unicodedata.combining(c)).strip()


class ChiloechesAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.select('a[href]'):
            if ('next' in a.get('rel', []) or
                    _normal(a.get_text(' ', strip=True)) in {'SIGUIENTE', 'NEXT', '»', '›'} or
                    re.search(r'/page/\d+|[?&](?:paged|page)=\d+', a['href'])):
                raise ValueError('Paginated source: traversal must be reviewed before extraction')
        headings = [h for h in soup.select('h3') if _normal(h.get_text(' ', strip=True)) == 'POM']
        if len(headings) != 1:
            raise ValueError('Expected one municipal POM inventory')
        section = headings[0].find_parent('section')
        if section is None:
            raise ValueError('Missing planning inventory section')
        groups = {'pom': {'titulo': 'Plan de Ordenación Municipal de Chiloeches (POM)', 'docs': {}}}
        current, subsection = 'pom', 'POM'
        for node in section.select('h3,h4,a[href]'):
            title = node.get_text(' ', strip=True)
            if node.name in {'h3', 'h4'}:
                label = _normal(title)
                match = re.fullmatch(r'MODIFICACION PUNTUAL N[º°O.]?\s*(\d+)', label)
                if match:
                    current = 'mp-' + match[1]
                    groups.setdefault(current, {'titulo': f'Modificación puntual nº {match[1]} del POM de Chiloeches', 'docs': {}})
                elif label in {'POM', 'PLANOS INFORMACION', 'PLANOS DE ORDENACION'}:
                    current = 'pom'
                else:
                    raise ValueError(f'Unreviewed inventory heading: {title}')
                subsection = title
                continue
            url = urljoin(SOURCE, node['href'])
            parts = urlsplit(url)
            if not parts.path.lower().endswith('.pdf'):
                continue
            if parts.scheme != 'https' or parts.netloc != 'chiloeches.es' or not parts.path.startswith('/wp-content/uploads/'):
                raise ValueError(f'Unreviewed document provenance: {url}')
            doc = groups[current]['docs'].setdefault(url, {
                'titulo': title, 'url': url, 'url_indice': SOURCE,
                'seccion': subsection, 'titulos_en_indice': [],
            })
            if title not in doc['titulos_en_indice']:
                doc['titulos_en_indice'].append(title)
        rows = []
        for key, group in groups.items():
            if not group['docs']:
                raise ValueError(f'Instrument without documents: {key}')
            rows.append({
                'id': 'chiloeches-proy-' + key, 'municipio': 'Chiloeches',
                'codigo_ine': '19105', 'provincia': 'Guadalajara',
                'titulo': group['titulo'], 'tipo': 'planeamiento_urbanistico',
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_pom',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                'fecha_aprob': None, 'fase': None,
                'documentos': list(group['docs'].values()),
                'descripcion': 'Instrumento documentado en el índice municipal de Urbanismo. '
                               'La página no indica fecha ni fase de tramitación; '
                               'los nombres de archivo no acreditan su vigencia o aprobación.',
                'lat': None, 'lon': None, 'geometry': None,
                'geometry_status': 'unavailable', 'publication_ready': False,
            })
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=40, headers={'User-Agent': 'municipio-chiloeches/1.0'})
        response.raise_for_status()
        if urlsplit(response.url).netloc != 'chiloeches.es':
            raise ValueError('Inventory redirected outside municipal website')
        rows = self.parse_inventory(response.text)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            directory = Path(capture_dir)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / 'urbanismo.html').write_text(response.text, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'coverage': 'Municipal POM inventory only', 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full current inventory refresh; no date-based cutoff or pagination cap.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
