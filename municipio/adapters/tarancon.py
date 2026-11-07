"""Public Tarancón planning inventory; no licence or current-validity inference."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://tarancon.sedelectronica.es/transparency/b2c2d540-4140-4c21-adfa-3e98cbf24323/'
HOST = 'tarancon.sedelectronica.es'


def _norm(value):
    return ' '.join(unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower().split())


def _page(html):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content')
    if content is None or 'NORMATIVA URBANÍSTICA' not in content.get_text(' ', strip=True):
        raise ValueError('Missing Tarancón urban-planning inventory')
    # The verified inventory has no pager. Fail explicitly if that changes;
    # the advertised child counts are checked separately below.
    if content.select('[rel~=next], .pagination, .paginator, .paginador'):
        raise ValueError('Unexpected pagination: inventory coverage requires review')
    return content


def _folders(content):
    folders = {}
    for a in content.select('a.exp'):
        label = a.get_text(' ', strip=True)
        match = re.fullmatch(r'(.+?)\s*\(\s*(\d+)\s*\)', label)
        callback = re.search(r"wicketAjaxGet\('([^']+)'", a.get('onclick', ''))
        if not match or not callback:
            raise ValueError('Unrecognized inventory folder/count/callback')
        name = match[1].strip()
        if name in folders:
            raise ValueError('Duplicate inventory folder')
        folders[name] = (int(match[2]), callback[1])
    return folders


def _documents(content):
    docs = {}
    for a in content.select('a[href*="/preview-document/"]'):
        target = urljoin(SOURCE, a['href'])
        if urlparse(target).hostname != HOST:
            raise ValueError('Unexpected document host')
        docs[target] = {'titulo': a.get_text(' ', strip=True), 'url': target,
                        'descripcion_fuente': a.get('title') or None}
    return list(docs.values())


def _publication(title):
    match = re.search(r'\b(BOP|DOCM)\s+(\d{4})(\d{2})(\d{2})\b', title)
    if not match:
        return None
    return date(int(match[2]), int(match[3]), int(match[4])).isoformat()


def parse_inventory(root_html: str, folder_pages: dict[str, str]):
    """Parse a complete snapshot, including every advertised child document."""
    root = _page(root_html)
    folders = _folders(root)
    if set(folders) != {'Modificaciones Puntuales a las Normas Subsidiarias', 'Estudios de Detalle'}:
        raise ValueError('Planning inventory folder structure changed')
    if set(folders) != set(folder_pages):
        raise ValueError('Incomplete inventory folders')
    groups = {}
    for section, content in [('root', root)] + [(name, _page(html)) for name, html in folder_pages.items()]:
        documents = _documents(content)
        if section != 'root':
            if _folders(content):
                raise ValueError('Unexpected nested folders; coverage requires review')
            if len(documents) != folders[section][0]:
                raise ValueError('Advertised folder document count does not match extraction')
        for doc in documents:
            title = doc['titulo']
            if re.fullmatch(r'Tomo\s+[IVX]+:\s*NORMAS SUBSIDIARIAS DE TARANCÓN', title, re.I):
                instrument = 'Normas Subsidiarias de Tarancón'
                kind = 'Normas Subsidiarias'
            elif re.match(r'^URB (MP|ED)\b', title):
                instrument = re.sub(r'\s+(?:(?:BOP|DOCM)\s+\d{8}|memoria|planos)\s*$', '', title, flags=re.I)
                kind = 'Modificación puntual' if title.startswith('URB MP') else 'Estudio de detalle'
            elif section == 'root':
                # Heritage guide and archaeological inventory are not plans.
                continue
            else:
                raise ValueError('Unrecognized document in planning folder')
            doc['fecha_publicacion'] = _publication(title)
            doc['fecha_publicacion_procedencia'] = 'Etiqueta del inventario (BOP/DOCM)' if doc['fecha_publicacion'] else None
            approval = re.search(r'Acuerdo del Pleno, de fecha (\d{2})/(\d{2})/(\d{4}), por el que se aprueba definitivamente', doc['descripcion_fuente'] or '')
            doc['fecha_acuerdo'] = date(int(approval[3]), int(approval[2]), int(approval[1])).isoformat() if approval else None
            doc['inventory_url'] = SOURCE
            doc['seccion'] = section
            key = _norm(instrument)
            group = groups.setdefault(key, {'titulo': instrument, 'tipo': kind, 'documentos': []})
            if not any(d['url'] == doc['url'] for d in group['documentos']):
                group['documentos'].append(doc)
    if not groups or not any(g['tipo'] == 'Normas Subsidiarias' for g in groups.values()):
        raise ValueError('Missing named planning instruments')
    rows = []
    for key, group in sorted(groups.items()):
        publications = {d['fecha_publicacion'] for d in group['documentos'] if d['fecha_publicacion']}
        agreements = {d['fecha_acuerdo'] for d in group['documentos'] if d['fecha_acuerdo']}
        agreement = next(iter(agreements)) if len(agreements) == 1 else None
        rows.append({
            'id': 'tarancon-plan-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Tarancón', 'provincia': 'Cuenca', 'codigo_ine': '16203',
            **group, 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
            'source_entity_type': 'documento',
            'url': SOURCE, 'url_documento': group['documentos'][0]['url'],
            'fecha': None,
            'fecha_publicacion': next(iter(publications)) if len(publications) == 1 else None,
            'fecha_acuerdo': agreement, 'fecha_aprob': agreement,
            'fase': 'aprobación definitiva' if agreement else None,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
            'coverage': 'Inventario documental parcial; no acredita vigencia actual ni ejecución',
        })
    return rows


class TaranconAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, session, url, capture):
        if urlparse(url).hostname != HOST:
            raise ValueError('Unexpected source host')
        response = session.get(url, timeout=45)
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError('Unexpected source redirect')
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir'])
            path.mkdir(parents=True, exist_ok=True)
            (path / capture).write_text(response.text, encoding='utf-8')
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-tarancon/1.0 (public planning inventory)'
            # A cache-busting public GET creates a fresh anonymous Wicket session;
            # cached callback tokens from a different session return empty pages.
            def root(capture):
                return self._get(session, SOURCE + '?snapshot=' + uuid.uuid4().hex, capture)

            html = root('inventory-root.html')
            folders = _folders(_page(html))
            pages = {}
            for index, name in enumerate(folders):
                fresh = _folders(_page(root(f'inventory-root-{index}.html')))
                if {k: v[0] for k, v in fresh.items()} != {k: v[0] for k, v in folders.items()}:
                    raise ValueError('Inventory changed during extraction')
                # The public folder callback also serves a full HTML page without
                # AJAX headers. Never persist its ephemeral URL as document identity.
                pages[name] = self._get(session, urljoin(SOURCE, fresh[name][1]), f'inventory-folder-{index}.html')
            rows = parse_inventory(html, pages)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'documents': sum(len(r['documentos']) for r in rows), 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
