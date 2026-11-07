"""Bermeo's municipal planning document inventory (not a licence register)."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.bermeo.eus/1453.html'


def _text(node):
    return node.get_text(' ', strip=True)


def _group(url):
    """Reviewed document families; unknown additions require review, never disappear."""
    path = unquote(urlparse(url).path)
    name = path.rsplit('/', 1)[-1]
    if '/2025_PLAN_BEREZIA/' in path or name == 'II-552_eus.pdf':
        return 'casco-antiguo'
    if name in {'21Memoria_plan_orokorra_eusk.pdf', 'OrdenanzasBermeoApDefinitiva.pdf',
                'estudio_economico_Bermeo.pdf', '813.html', '1429.html'}:
        return 'pgou'
    if name in {'II-1623_eus.pdf', '4-_iragarkia.pdf', '3-_egikaritze-laburpena.pdf',
                '2-_kokalekuaren_planoa.pdf', '11plan_berezia.pdf'}:
        return 'area-21-2-parcelas-6-9'
    if name in {'EGIKARITZE_LABURPENA.pdf', 'II-5559_eus.pdf'}:
        return 'area-6-1-2'
    if name == 'II-991_eus.pdf':
        return 'catalogo-pgou'
    if name.startswith('U-') and name.endswith('.pdf'):
        return 'olalde'
    if name.startswith('04-23') and name.endswith('.pdf'):
        return 'area-21-2-parcelas-8-11'
    if name == 'II-3866_eus.pdf':
        return 'subestacion'
    raise ValueError(f'Unclassified planning document: {url}')


class BermeoAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='bermeo', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.bermeo.eus')

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('#seccioncontenido')
        if content is None:
            raise ValueError('Municipal planning content missing (possibly homepage redirect)')
        for a in content.select('a[href]'):
            label = _text(a).casefold()
            if (set(a.get('rel', [])) & {'next', 'prev'} or
                    label in {'next', 'siguiente', 'hurrengoa', 'hurrengo', '»', '›'}):
                raise ValueError('Pagination detected; traversal requires review')
        if content.select('.pagination, .pagebrowser, .tx-pagebrowse, [data-page]'):
            raise ValueError('Pagination detected; traversal requires review')

        groups = {}
        for a in content.select('a[href]'):
            url = urljoin(SOURCE, a['href'])
            if urlparse(url).hostname != 'www.bermeo.eus':
                raise ValueError(f'Unexpected external inventory link: {url}')
            key = _group(url)
            groups.setdefault(key, {})[url] = {
                'titulo': _text(a), 'url': url, 'source_url': SOURCE,
                'tipo': 'indice_documentos' if urlparse(url).path.endswith('.html') else 'documento',
            }
        # Titles are read from the inventory, not inferred from filenames.
        strongs = [_text(s) for s in content.select('strong')]
        old = next((s for s in strongs if 'ALDE ZAHARREKO PLAN BEREZIAREN' in s), None)
        if not old or 'BEHIN BETIKOAK' not in strongs:
            raise ValueError('Planning section headings changed')
        labels = [_text(a) for a in content.select('a[href]')]
        def label_with(fragment):
            found = [s for s in labels if fragment in s]
            if not found:
                raise ValueError(f'Missing instrument title: {fragment}')
            return found[0]
        def list_title(fragment):
            for li in content.select('li'):
                direct = ' '.join(str(t).strip() for t in li.find_all(string=True, recursive=False)).strip()
                if fragment in direct:
                    return direct
            raise ValueError(f'Missing instrument heading: {fragment}')
        titles = {
            'casco-antiguo': old,
            'pgou': 'Plan orokorra — BEHIN BETIKOAK',
            'area-21-2-parcelas-6-9': label_with('Iragarkia: 21.2'),
            'area-6-1-2': label_with('6.1.2 Esku-hartze Areako Hiri Antolamendurako Plan Berezia'),
            'catalogo-pgou': label_with('HAPOaren katalogoaren'),
            'olalde': list_title('Olalde'),
            'area-21-2-parcelas-8-11': list_title('21.2, 8 eta 11'),
            'subestacion': label_with('transformazio azpiestazioa'),
        }
        if set(groups) != set(titles):
            raise ValueError('Reviewed instrument families missing from inventory')
        rows = []
        for key, docs in groups.items():
            publication = None
            for doc in docs.values():
                # Only explicitly dated BAO labels; never generic page/calendar dates.
                match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', doc['titulo'])
                if match and 'BAO' in doc['titulo']:
                    publication = date.fromisoformat(match[1]).isoformat()
            narrative = ' '.join(d['titulo'] for d in docs.values()).casefold()
            if key == 'casco-antiguo':
                narrative += ' ' + old.casefold()
            phase = None
            if key == 'pgou' or 'behin betiko onarpena' in narrative:
                phase = 'aprobación definitiva'
            elif any(word in narrative for word in ('hasieraz', 'hasierako')):
                phase = 'aprobación inicial'
            rows.append({
                'id': 'bermeo-proy-' + key, 'municipio': 'Bermeo', 'codigo_ine': '48017',
                'provincia': 'Bizkaia', 'titulo': titles[key],
                'tipo': 'planeamiento_urbanistico', 'fase': phase,
                'fecha_publicacion': publication, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
                'documentos': list(docs.values()),
                'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                'publication_ready': False,
            })
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=35, headers={
            'User-Agent': 'municipio-bermeo/1.0 (public planning inventory)'})
        response.raise_for_status()
        rows = self.parse_inventory(response.content)
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir']) / 'inventory-live.html'
            capture.parent.mkdir(parents=True, exist_ok=True)
            capture.write_bytes(response.content)
        result = self._write(out_jsonl, rows)
        return {**result, 'source_urls': [SOURCE], 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        """Full refresh of the current inventory; state is not a date watermark."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
