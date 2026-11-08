"""Partial inventory of Tineo planning instruments, not a licence register."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.tineo.es/instrumentos-urbanisticos-en-tramitacion'
LIMITATIONS = [
    'Only the municipal instrumentos en tramitación page; not a complete historical or current planning register.',
    'Stages describe the municipal inventory wording; later agreements may exist elsewhere.',
    'No publication or agreement dates exposed in this inventory; document dates and URL timestamps are not publication dates.',
    'No verified instrument geometry; coordinates are absent. No granted licences extracted.',
]


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


class TineoAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='tineo', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.tineo.es')

    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.select('a[href]'):
            label = _text(a).casefold()
            if a['href'] not in ('', '#') and (
                'next' in a.get('rel', []) or
                label in {'siguiente', 'next', 'siguiente página', '»', '›'} or
                re.search(r'[?&](?:cur|page|start|delta)=', a['href'], re.I)
            ):
                raise ValueError('Pagination detected; review and implement traversal before extraction')
        articles = [a for a in soup.select('.journal-content-article')
                    if a.select_one('.titulo h2') and
                    _text(a.select_one('.titulo h2')).casefold() == 'instrumentos urbanísticos en tramitación']
        if len(articles) != 1:
            raise ValueError('Missing or ambiguous municipal inventory')
        content = articles[0].select_one('.detalle')
        if content is None:
            raise ValueError('Missing inventory content')
        groups = []
        current = None
        for block in content.find_all(recursive=False):
            if not _text(block):
                continue
            if block.name == 'p' and not block.select('a'):
                title = _text(block)
                upper = title.upper()
                if 'UNIDAD DE ACTUACIÓN' in upper:
                    kind = 'delimitacion_unidad_actuacion'
                elif 'MODIFICACIÓN DEL PLAN GENERAL' in upper:
                    kind = 'modificacion_pgou'
                else:
                    raise ValueError('Unreviewed inventory heading: ' + title)
                current = {'titulo': title, 'tipo': kind, 'documentos': []}
                groups.append(current)
            elif block.name == 'ul' and current is not None:
                for a in block.select('a[href]'):
                    title = _text(a)
                    url = urljoin(SOURCE, a['href'])
                    parsed = urlsplit(url)
                    if parsed.hostname != 'www.tineo.es' or not parsed.path.startswith('/documents/') or not title:
                        raise ValueError('Unexpected inventory document link')
                    doc = {'titulo': title, 'url': url, 'origen_url': SOURCE}
                    # The site nests this separate PGOU modification in ALISEDA's
                    # UL. Its PDF cover verifies the independent instrument.
                    if title.upper().startswith('DOCUMENTO DE APROBACIÓN INICIAL. VENTA QUILDÁN'):
                        standalone = next((g for g in groups if g['titulo'] == title), None)
                        if standalone is None:
                            standalone = {'titulo': title, 'tipo': 'modificacion_pgou', 'documentos': []}
                            groups.append(standalone)
                        standalone['documentos'].append(doc)
                    else:
                        current['documentos'].append(doc)
            else:
                raise ValueError('Unreviewed inventory structure')

        rows = []
        used = set()
        for group in groups:
            documents = {}
            for doc in group['documentos']:
                key = doc['url'].split('?')[0]
                documents.setdefault(key, doc)
            if not documents:
                raise ValueError('Instrument without documents')
            keys = set(documents)
            if used & keys:
                raise ValueError('Document assigned to multiple instruments')
            used.update(keys)
            group['documentos'] = list(documents.values())
            narrative = ' '.join([group['titulo']] + [d['titulo'] for d in group['documentos']])
            phase = 'aprobación inicial' if re.search(r'aprobación inicial|aprueba inicialmente', narrative, re.I) else None
            if group['titulo'].upper().startswith('DOCUMENTO DE APROBACIÓN INICIAL.'):
                phase = 'documento de aprobación inicial'
            # The notice is the first document; ignore volatile Liferay timestamps.
            identity = next(iter(documents))
            rows.append({
                **group,
                'id': 'tineo-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
                'municipio': 'Tineo', 'codigo_ine': '33073', 'provincia': 'Asturias',
                'url': SOURCE, 'url_documento': identity,
                'source': 'ayuntamiento', 'origen': 'inventario_instrumentos_en_tramitacion',
                'fase': phase, 'fase_fuente': 'Texto del inventario municipal; no verifica la última fase administrativa',
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                'publication_ready': False, 'cobertura': 'parcial',
            })
        if not rows:
            raise ValueError('Empty inventory requires review')
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=40, headers={'User-Agent': 'municipio-tineo/1.0'})
        response.raise_for_status()
        if urlsplit(response.url).hostname != 'www.tineo.es':
            raise ValueError('Inventory redirected off municipal host')
        rows = self.parse_inventory(response.text)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'live-inventory.html').write_text(response.text, encoding='utf-8')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of the scoped static inventory; no incremental cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
