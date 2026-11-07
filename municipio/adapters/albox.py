"""Albox's municipal planning document inventory, hosted by Diputación de Almería."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = ('https://www.dipalme.org/Servicios/cmsdipro/index.nsf/informacion.xsp'
          '?documentId=31F247FAB5E8FCD7C1257846004AB10E&p=Albox')
LIMITATIONS = [
    'Partial coverage: the municipal Urbanismo document inventory only; not all municipal projects or historical planning.',
    'No granted licence register extracted; forms, procurement and general news excluded.',
    'Dates and administrative phase are not inferred from filenames or document upload identifiers. PDF contents are linked, not parsed.',
    'No verified instrument geometry or coordinates; publication_ready is false.',
    'The separate ayuntamientodealbox.com homepage and BOP page returned HTTP 403 during research.',
]


def _group(filename, label):
    """Reviewed inventory families; an unfamiliar attachment requires review."""
    name = filename.upper()
    if ('SECTOR' in name and re.search(r'7.*8', name)) or name == 'FICHA_JUSTIFICATIVA_DECRETO_293_2009.PDF':
        return 'estudio-sectores-7-8', 'Estudio de detalle: alineaciones y rasantes sectores 7 y 8 de Albox'
    if 'LEPANTO' in name:
        return 'estudio-avda-lepanto', 'Estudio de detalle: alineaciones en Avda. Lepanto de Albox'
    if name.startswith(('ALINEACIONES ', 'ALTURAS ')):
        return 'pgou-alineaciones', 'PGOU de Albox: alineaciones y alturas'
    if name == 'BOP._APROB. DEFINI. MODIF_PGOU_PLAZA MAYOR.PDF':
        return 'modificacion-plaza-mayor', label
    if name == 'MOD-NORMAS_AP-DEFINITIVA.PDF':
        return 'modificacion-normas', 'Modificación puntual de las normas de planeamiento y generales de la edificación del PGOU de Albox'
    if name == 'ORDENANZA_DEFINITIVA_NO URBANIZABLE.PDF':
        return 'modificacion-suelo-no-urbanizable', 'Modificación puntual del PGOU de Albox: artículo III.4, suelo no urbanizable'
    if name in {'01_VIGENTE-TERMINO-MUNICIPAL.PDF', '03_ORDENACION-TERMINO-MUNICIPAL.PDF',
                '04_ORDENACION-NUCLEOS-URBANOS.PDF', '05_ORDENACION-USOS-GLOBALES.PDF', 'MEMORIA_APL_PGOU_08.PDF'}:
        return 'pgou-adaptacion-loua', 'PGOU de Albox: adaptación a la LOUA'
    raise ValueError(f'Unreviewed municipal attachment: {filename}')


class AlboxAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('#content')
        if not content or not content.select_one('h1') or content.select_one('h1').get_text(strip=True) != 'Urbanismo':
            raise ValueError('Missing municipal Urbanismo inventory')
        # This inventory is a single document, not a search-results listing.
        # Refuse newly introduced pagination rather than silently taking page one.
        for a in soup.select('a[href]'):
            label = a.get_text(' ', strip=True).casefold()
            if (set(a.get('rel', [])) & {'next', 'prev'} or
                    re.search(r'siguiente|anterior|next|previous|página\s*\d', label) or
                    re.search(r'[?&](?:page|start|offset|pageno)=', a['href'], re.I)):
                raise ValueError('Pagination detected; review traversal before extraction')
        groups = {}
        for a in content.select('a[href]'):
            original = urljoin(SOURCE, a['href'])
            parts = urlsplit(original)
            path = unquote(parts.path)
            if '$file/' not in path.lower():
                if a.find_parent(class_='limpiar_fondo'):
                    raise ValueError(f'Unreviewed inventory link: {original}')
                continue
            if parts.hostname not in {'www.dipalme.org', 'www.albox.es'} or not path.lower().endswith('.pdf'):
                raise ValueError(f'Unexpected document source: {original}')
            label = ' '.join(a.get_text(' ', strip=True).split()).lstrip('- ')
            key, title = _group(path.rsplit('/', 1)[-1], label)
            row = groups.setdefault(key, {
                'id': 'albox-proy-' + key, 'municipio': 'Albox', 'codigo_ine': '04006',
                'provincia': 'Almería', 'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_urbanismo',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'fase': None, 'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'cobertura': 'Inventario documental municipal parcial; documentos PDF sin extracción de texto.',
                'documentos': [],
            })
            # The inventory contains repeated links, and legacy HTTP URLs work via HTTPS.
            canonical = urlunsplit(('https', parts.netloc, parts.path, parts.query, ''))
            if not any(d['url'] == canonical for d in row['documentos']):
                row['documentos'].append({'titulo': label, 'url': canonical,
                                          'url_en_inventario': original, 'source_url': SOURCE})
        if not groups:
            raise ValueError('No planning documents found; refusing empty success')
        return list(groups.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=45, headers={'User-Agent': 'municipio-albox/1.0'})
        response.raise_for_status()
        response.encoding = 'utf-8'
        rows = self.parse_inventory(response.text)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'urbanismo.html').write_bytes(response.content)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh of the one-page inventory, without date-based filtering.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
