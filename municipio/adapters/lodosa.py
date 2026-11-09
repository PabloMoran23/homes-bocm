"""Municipal European-project inventory, one record per project section."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.lodosa.es/ayuntamiento/ayudas-europeas/'


def clean(text):
    return ' '.join(text.split())


class LodosaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('#content')
        if not content or 'Proyectos Europeos' not in content.get_text(' ', strip=True):
            raise ValueError('Municipal European project inventory missing')
        if content.select('a[rel~=next], .pagination a[href], a.page-numbers[href]'):
            raise ValueError('Pagination discovered; review traversal before accepting output')
        for a in content.select('a[href]'):
            if clean(a.text).lower() in {'siguiente', 'next', '»'} and a['href'] not in {'', '#'}:
                raise ValueError('Pagination discovered')
        headings = [h for h in content.select('h3') if re.match(r'^PROYECTO\s+\d+\s*/', clean(h.text))]
        if not headings:
            raise ValueError('No project sections found')
        rows = {}
        for h in headings:
            block = h.find_parent('div', class_='vc_row')
            if block is None or len([x for x in block.select('h3') if re.match(r'^PROYECTO\s+\d+\s*/', clean(x.text))]) != 1:
                raise ValueError('Ambiguous project section boundaries')
            title = clean(h.text).split('/', 1)[1].strip()
            if not re.search(r'RESTAURACI[ÓO]N|ENERG[IÍ]A LIMPIA|REFORMAS|MEJORAS', title, re.I):
                raise ValueError('New project type requires semantic review')
            beneficiary = [clean(p.get_text(' ', strip=True)) for p in block.select('p, li') if clean(p.get_text(' ', strip=True)).startswith('Beneficiario:')]
            if beneficiary != ['Beneficiario: AYUNTAMIENTO DE LODOSA']:
                raise ValueError('Municipal beneficiary missing or ambiguous')
            table = block.select_one('table')
            if table is None:
                raise ValueError('Project identification table missing')
            metadata = {}
            for tr in table.select('tbody tr'):
                cells = [clean(td.text) for td in tr.select('td')]
                if len(cells) >= 2:
                    if cells[0] in metadata:
                        raise ValueError('Duplicate identification field')
                    metadata[cells[0]] = ' | '.join(cells[1:])
            if not metadata.get('Subproyecto'):
                raise ValueError('Project identification missing')
            docs = {}
            for a in block.select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                if urlparse(url).path.lower().endswith('.pdf'):
                    if urlparse(url).hostname != 'www.lodosa.es':
                        raise ValueError('Unreviewed document host')
                    docs[url] = {'titulo': clean(a.text), 'url': url, 'source_url': SOURCE}
            key = hashlib.sha256(title.casefold().encode()).hexdigest()[:20]
            if key in rows:
                raise ValueError('Duplicate project section')
            # No unfiltered page text: only public project identification and
            # financial labels, excluding unrelated widgets and access information.
            finance = [clean(p.get_text(' ', strip=True)) for p in block.select('p, li') if clean(p.get_text(' ', strip=True)).startswith(('Inversión total:', 'Importe de la ayuda:'))]
            rows[key] = {
                'id': 'lodosa-proy-' + key, 'municipio': 'Lodosa', 'codigo_ine': '31157',
                'provincia': 'Navarra', 'titulo': title, 'tipo': 'obra_publica',
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_proyectos_europeos',
                'descripcion': '\n'.join(beneficiary + finance), 'identificacion_fuente': metadata,
                'documentos': list(docs.values()), 'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': None, 'fecha_aprob': None, 'fase': None,
                'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                'publication_ready': False,
            }
        return list(rows.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-lodosa/1.0 (public project inventory)'
            response = session.get(SOURCE, timeout=30)
            response.raise_for_status()
            rows = self.parse_inventory(response.content)
            # Complete parse before replacing the snapshot. This source is a
            # single inventory page; any new pagination fails explicitly.
            self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'coverage': 'municipal European projects only'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
