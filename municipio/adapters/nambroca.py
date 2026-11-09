"""Snapshot of Nambroca's official public planning-document inventory."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://nambroca.sedelectronica.es/transparency/ac16ea95-0567-44b0-9da3-97b969d422bf/'
HOST = 'nambroca.sedelectronica.es'


def _norm(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if not unicodedata.combining(c))


class NambrocaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, 'html.parser')
        if '7.1. PLANEAMIENTO URBANÍSTICO' not in soup.get_text(' ', strip=True):
            raise ValueError('Missing public planning inventory heading')
        table = soup.select_one('table.TransparencyListPanel')
        if table is None:
            raise ValueError('Missing planning document table')
        for a in soup.select('a, button, input'):
            text = _norm(a.get_text(' ', strip=True) + ' ' + str(a.get('value', '')))
            rel = a.get('rel', [])
            if ('next' in rel or any(w in text for w in ('mostrar mas', 'siguiente', 'next'))):
                raise ValueError('Pagination detected; review crawler before extracting')
        groups = {
            'pau-8b-8c': ('PAU con Plan Parcial y Proyecto de Urbanización del sector 8B–8C', 'programa_actuacion_urbanizadora'),
            'reparcelacion-8b-8c': ('Proyecto de reparcelación del sector 8B–8C, revisión 2', 'reparcelacion'),
            'nnss': ('Normas Subsidiarias y modificaciones de Nambroca', 'planeamiento_urbanistico'),
            'modificacion-sector-20': ('Modificación puntual de las NNSS para la creación del sector 20', 'planeamiento_urbanistico'),
        }
        docs = {key: {} for key in groups}
        for tr in table.select('tbody tr'):
            if not tr.get_text(strip=True):
                continue
            links = tr.select('a[href*="/preview-document/"]')
            if len(links) != 1:
                raise ValueError('Unrecognized inventory row; refuse partial coverage')
            a = links[0]
            title = a.get_text(' ', strip=True)
            text = _norm(title)
            url = urljoin(SOURCE, a['href'])
            if urlparse(url).hostname != HOST or not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(url).path):
                raise ValueError('Unexpected document provenance')
            publication = None
            if text == 'planos nnss' or text == 'texto nnss y modificaciones nambroca':
                key = 'nnss'
            elif text.startswith('p reparcelacion sct8b-8c'):
                key = 'reparcelacion-8b-8c'
            elif text == 'bop anuncio contenido normativo sector 20':
                key = 'modificacion-sector-20'
            elif text == 'anuncio contenido normativo sector 8b 8c nnss nambroca bop 07.09.2023':
                key, publication = 'pau-8b-8c', '2023-09-07'
            elif text == 'publicacion docm 2 de mayo de 2023 aprobacion pau sect 8b y 8c nnss nambroca':
                key, publication = 'pau-8b-8c', '2023-05-02'
            else:
                raise ValueError('Unclassified planning document: ' + title)
            docs[key][url] = {'titulo': title, 'url': url, 'url_origen': SOURCE,
                              'fecha_publicacion': publication}
        rows = []
        for key, (title, kind) in groups.items():
            if not docs[key]:
                raise ValueError('Reviewed instrument absent: ' + key)
            rows.append({
                'id': 'nambroca-proy-' + key, 'municipio': 'Nambroca',
                'provincia': 'Toledo', 'codigo_ine': '45107', 'titulo': title,
                'tipo': kind, 'fase': None, 'fecha': None,
                'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
                'documentos': sorted(docs[key].values(), key=lambda d: d['url']),
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'limitaciones': 'Inventario documental parcial; no se extraen fechas de acuerdos ni geometría de los PDF. No acredita vigencia ni ejecución actual.',
            })
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows), 'source': SOURCE, 'publication_ready': False}

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=45, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-nambroca/1.0')}, stream=True)
        with response:
            response.raise_for_status()
            if urlparse(response.url).hostname != HOST:
                raise ValueError('Unexpected inventory redirect')
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 2_000_000:
                    raise ValueError('Inventory exceeds response size limit')
            html = content.decode('utf-8')
        rows = self.parse_inventory(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'planeamiento-live.html').write_text(html, encoding='utf-8')
        return self._write(out_jsonl, rows)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
