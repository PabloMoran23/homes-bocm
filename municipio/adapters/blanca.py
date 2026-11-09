"""Blanca's public transparency planning folders; one record per populated plan."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://sede.blanca.regiondemurcia.es'


def folder_url(identifier):
    token = base64.b64encode(f'Ayuntamiento de Blanca@@@{identifier}'.encode()).decode()
    return f'{BASE}/web/transparencia/{token}/30011'


SOURCE = folder_url(34)


def document_url(identifier):
    return BASE + '/web/transparencia.do?' + urlencode({
        'opcion': 6, 'idDoc': identifier, 'entidad': '30011', 'idioma': 1})


def parse_folder(html):
    """Read only the server-generated string literals, never execute website JS."""
    if '7.1. PLANEAMIENTO URBANÍSTICO' not in html or 'formTransparencia' not in html:
        raise ValueError('Missing Blanca planning inventory (or login/challenge response)')
    strings = re.findall(r'html_epigrafes\s*\+=\s*("(?:[^"\\]|\\.)*")\s*;', html)
    appends = re.findall(
        r'jQuery\("#tablaDocumentosEnlaces > tbody"\)\.append\(("(?:[^"\\]|\\.)*")\);', html)
    fragment = ''.join(json.loads(s) for s in strings + appends)
    soup = BeautifulSoup(fragment, 'html.parser')
    # There is no pagination in this folder UI. Fail if it gains controls;
    # child badge counts are also checked against the complete fetched contents.
    for a in BeautifulSoup(html + fragment, 'html.parser').select('a[href]'):
        if (re.search(r'\b(siguiente|next)\b', a.get_text(' ', strip=True), re.I)
                or 'next' in a.get('rel', [])
                or re.search(r'[?&](?:page|pagina|offset)=', a['href'], re.I)):
            raise ValueError('Unreviewed inventory pagination')
    folders, documents = [], {}
    for a in soup.select('a[onclick]'):
        action = a['onclick']
        child = re.fullmatch(r'pulsaEpigrafe\((\d+)\)', action)
        doc = re.fullmatch(r'verDoc\((\d+)\)', action)
        if child:
            title = a.select_one('[title]')
            count = a.select_one('.badge')
            if title is None or count is None:
                raise ValueError('Folder lacks title/count')
            folders.append({'id': child[1], 'titulo': title['title'],
                            'count': int(count.get_text(strip=True))})
        elif doc:
            documents[doc[1]] = {'id_documento': doc[1],
                                'titulo': a.get_text(' ', strip=True),
                                'url': document_url(doc[1])}
        else:
            raise ValueError('Unknown inventory action')
    if len(appends) != len(documents):
        raise ValueError('Unparsed or duplicated inventory document')
    if len(re.findall(r'pulsaEpigrafe\(', fragment)) != len(folders):
        raise ValueError('Unparsed inventory folders')
    return folders, list(documents.values())


class BlancaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        response = session.get(url, timeout=35)
        response.raise_for_status()
        if response.url != url:
            raise ValueError('Unexpected source redirect')
        if self.config.get('capture_dir'):
            directory = Path(self.config['capture_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = 'inventory' if url == SOURCE else url.split('/')[-2]
            (directory / f'{name}.html').write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        sources, rows, empty = [SOURCE], [], []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-blanca/1.0 (public planning inventory)'
            folders, summaries = parse_folder(self._fetch(session, SOURCE))
            if not folders:
                raise ValueError('No planning folders discovered')
            for folder in folders:
                url = folder_url(folder['id'])
                sources.append(url)
                children, docs = parse_folder(self._fetch(session, url))
                if len(children) + len(docs) != folder['count']:
                    raise ValueError('Folder count mismatch; inventory may be truncated')
                if children:
                    raise ValueError('New nested planning folders require grouping review')
                if not docs:
                    empty.append(url)
                    continue
                title = folder['titulo']
                if title.casefold() == 'planeamiento general':
                    title = 'Plan General Municipal de Ordenación de Blanca (PGMO)'
                elif not re.search(r'\bPLAN PARCIAL\b', title, re.I):
                    raise ValueError('New populated folder needs instrument review')
                rows.append({
                    'id': 'blanca-plan-' + folder['id'], 'municipio': 'Blanca',
                    'codigo_ine': '30011', 'provincia': 'Murcia', 'titulo': title,
                    'tipo': 'planeamiento_urbanistico', 'url': url,
                    'inventory_url': SOURCE, 'source': 'ayuntamiento',
                    'origen': 'sede_transparencia_planeamiento', 'documentos': docs,
                    'documentos_contexto_inventario': summaries,
                    'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'lat': None, 'lon': None, 'geometry': None,
                    'geometry_status': 'unavailable', 'publication_ready': False,
                    'coverage': 'Populated municipal planning folders; PDF dates and legal status not parsed',
                })
        if not rows:
            raise ValueError('No documented planning instruments available')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources,
                'empty_folders': empty, 'coverage': 'partial_document_inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
