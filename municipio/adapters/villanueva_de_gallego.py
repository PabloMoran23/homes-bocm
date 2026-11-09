"""Municipal PGOU document inventory; no licence or news inference."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.villanuevadegallego.org/ayuntamiento/urbanismo/'
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def _norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


class VillanuevaDeGallegoAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('#main')
        if main is None:
            raise ValueError('Missing municipal main content')
        # This is a single static document inventory. Fail if it gains pages.
        if main.select('[rel~=next], .pagination, .page-numbers') or any(
            _norm(a.get_text(' ', strip=True)) in {'siguiente', 'next', 'ver mas', 'cargar mas'}
            for a in main.select('a[href]')
        ):
            raise ValueError('Pagination requires review; refusing partial inventory')
        inventories = main.select('nav[aria-label="PGOU"]')
        if len(inventories) != 1:
            raise ValueError('Expected one PGOU inventory')
        texts = [p.get_text(' ', strip=True) for p in main.select('p')]
        narrative = next((p for p in texts if 'Texto refundido' in p and 'Pleno Municipal' in p), None)
        if not narrative:
            raise ValueError('Missing PGOU provenance narrative')
        match = re.search(r'Pleno Municipal de fecha (\d{1,2}) de (\w+) de ([\d.]+)', narrative, re.I)
        agreement = None
        if match:
            agreement = date(int(match[3].replace('.', '')), MONTHS.index(_norm(match[2])) + 1, int(match[1])).isoformat()
        groups = {'pgou': []}
        seen = {}
        related = []
        anchors = list(inventories[0].select('a[href]'))
        anchors += [a for a in main.select('a[href]') if 'normas urbanisticas texto consolidado' in _norm(a.get_text(' ', strip=True))]
        for a in anchors:
            label = a.get_text(' ', strip=True)
            parts = urlsplit(urljoin(SOURCE, a['href']))
            if parts.hostname == 'idearagon.aragon.es' and parts.path == '/archivoSIUa/':
                related.append({'titulo': label, 'url': urljoin(SOURCE, a['href'])})
                continue
            if (parts.scheme != 'https' or parts.hostname != 'www.villanuevadegallego.org'
                    or not parts.path.startswith('/wp-content/uploads/')
                    or not parts.path.lower().endswith(('.pdf', '.rar', '.zip'))):
                raise ValueError(f'Unreviewed inventory link: {label}')
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))
            modified = re.search(r'modificacion(?: aislada)?\s+n(?:um\.?|[º°])?\.?\s*(\d+)', _norm(label))
            # Consolidated norms belong to the PGOU, not a new modification.
            key = 'modificacion-' + modified[1] if modified else 'pgou'
            if url in seen:
                if seen[url] != key:
                    raise ValueError('Document assigned to conflicting instruments')
                continue
            seen[url] = key
            groups.setdefault(key, []).append({'titulo': label, 'url': url, 'url_origen': SOURCE,
                                              'formato': parts.path.rsplit('.', 1)[1].lower()})
        if not groups['pgou'] or not any('memoria' in _norm(d['titulo']) for d in groups['pgou']):
            raise ValueError('Missing PGOU documents')
        rows = []
        for key, documents in groups.items():
            base = key == 'pgou'
            title = ('Plan General de Ordenación Urbana de Villanueva de Gállego — texto refundido enero de 2009'
                     if base else 'Modificación núm. ' + key.split('-')[1] + ' del PGOU de Villanueva de Gállego')
            rows.append({
                'id': 'villanueva-de-gallego-proy-' + key,
                'municipio': 'Villanueva de Gállego', 'codigo_ine': '50288', 'provincia': 'Zaragoza',
                'titulo': title, 'tipo': 'planeamiento_urbanistico',
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_pgou',
                'fecha': None, 'fecha_publicacion': None,
                'fecha_acuerdo': agreement if base else None,
                'fecha_aprob': None, 'fase': None,
                'descripcion': narrative if base else 'Instrumento identificado por el rótulo del inventario municipal; sin fecha ni fase verificadas.',
                'documentos': documents, 'enlaces_relacionados': related if base else [],
                'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                'cobertura': 'Inventario municipal de PGOU; no es el archivo completo de planeamiento del SIUA. Los planos no se han vectorizado.',
            })
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE]}

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=40, headers={'User-Agent': 'municipio-villanueva-de-gallego/1.0'})
        response.raise_for_status()
        if urlsplit(response.url).hostname != urlsplit(SOURCE).hostname:
            raise ValueError('Unexpected source redirect')
        rows = self.parse_inventory(response.text)
        if self.config.get('evidence_dir'):
            captures = Path(self.config['evidence_dir'])
            captures.mkdir(parents=True, exist_ok=True)
            (captures / 'urbanismo.html').write_text(response.text, encoding='utf-8')
        return self._write(out_jsonl, rows)

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh of the static inventory; state is not an incremental cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return self._write(out_jsonl, [])

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
