"""Partial, document-backed Benahavís planning snapshot from the public sede.

Enumerates the entire urbanism inventory, but emits only reviewed instrument
families. A document's creation timestamp is never a planning approval date.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://benahavis.sedelectronica.es'
SOURCE = BASE + '/transparency/480bb655-bfb0-4b16-9411-328164095310/'
LIMITATIONS = [
    'Partial semantic coverage: only Proindiviso A RLQ, Tajos Blancos/La Zagaleta, '
    'El Madroñal parcels 3, 4 and 5, and PPO La Fuente are classified.',
    'All urbanism inventory pages are enumerated. Historical PGOU sheets, RIU '
    'register files, ambiguous documents and street maps are excluded, not projects.',
    'The inventory mixes historical and newer files; current legal validity is not established.',
    'No granted-licence register, verified geometry or coordinates; publication_ready=false.',
    'Document creation dates are retained as metadata only. Publication and agreement '
    'dates are not extracted from the PDF bodies and remain null.',
    'Preview pages are checked live; large PDF bodies are not downloaded by the adapter.',
    'The shared entity policy may leave these unnumbered instruments pending; no dossier '
    'references are invented to force activity eligibility.',
]


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, 'html.parser')


def official(url: str) -> str:
    p = urlparse(url)
    if p.scheme != 'https' or p.netloc != 'benahavis.sedelectronica.es':
        raise ValueError('Unexpected source host: ' + url)
    return url


def callback(page_url: str, element) -> str:
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Unsupported Wicket callback')
    return official(urljoin(page_url, match[1]))


def documents(markup: str, inventory_url: str) -> list[dict[str, Any]]:
    result = {}
    for a in soup(markup).select('a.gIconLink[href]'):
        url = urljoin(inventory_url, a['href'])
        if '/preview-document/' not in url:
            continue
        official(url)
        if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(url).path):
            raise ValueError('Unrecognized document identity')
        title = a.get_text(' ', strip=True)
        if not title:
            raise ValueError('Document without title')
        result[url] = {'titulo': title, 'url': url,
                       'titulo_enlace': a.get('title'), 'inventarios': [inventory_url]}
    return list(result.values())


def folders(markup: str) -> list[tuple[str, int]]:
    result = []
    for a in soup(markup).select('a.gIconLink.exp'):
        text = a.get_text(' ', strip=True)
        if not text:
            continue
        m = re.fullmatch(r'(.+?)\s*\(\s*(\d+)\s*\)', text)
        if not m:
            raise ValueError('Folder without inventory count: ' + text)
        result.append((m[1].strip(), int(m[2])))
    return result


def ajax_components(xml: str) -> dict[str, str]:
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response':
        raise ValueError('Expected Wicket AJAX response')
    result = {}
    for c in root.findall('component'):
        encoding = c.get('encoding')
        if encoding not in (None, '', 'wicket1'):
            raise ValueError('Unknown Wicket component encoding')
        text = c.text or ''
        result[c.attrib['id']] = text.replace(']^', ']') if encoding == 'wicket1' else text
    if not result:
        raise ValueError('AJAX response lacks document components')
    return result


def family(title: str) -> tuple[str, str, str] | None:
    """Reviewed title families; no inference that every uploaded file is a project."""
    t = title.upper()
    if 'ANULADO' in t:
        return None
    if re.fullmatch(r'PROYECTO URBANIZACION PROINDIVISO A RLQ - \d+', t):
        return ('rlq-proindiviso-a', 'Proyecto de urbanización del Proindiviso A, sector El Real de la Quinta', 'proyecto_urbanizacion')
    if t == 'ZAGALETA_ESTUDIODEDETALLE':
        return ('zagaleta-tajos-blancos', 'Estudio de detalle de parcelas hoteleras de Tajos Blancos (La Zagaleta)', 'estudio_detalle')
    if t in {'EDICTO INICIAL MODIFICACION ED MADROÑAL',
             '101_MEM_MEMORIA_ESTUDIO DETALLE _EL MADRONAL 3-4 Y 5_F_SIGNED',
             '201_PL_ESTUDIO DETALLE _EL MADRONAL 3-4 Y 5_F_SIGNED'}:
        return ('madronal-3-4-5', 'Modificación del estudio de detalle de El Madroñal, parcelas 3, 4 y 5', 'estudio_detalle')
    if t == 'EDICTO APROBACION INICIAL PPO LA FUENTE':
        return ('ppo-la-fuente', 'Plan parcial de ordenación del sector La Fuente', 'plan_parcial')
    return None


def group_projects(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = {}
    for doc in docs:
        f = family(doc['titulo'])
        if not f:
            continue
        key, title, kind = f
        if key not in groups:
            groups[key] = {
                'id': 'benahavis-proy-' + key, 'municipio': 'Benahavís',
                'provincia': 'Málaga', 'codigo_ine': '29023', 'titulo': title,
                'tipo': kind, 'fase': None, 'fecha': None,
                'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'source': 'ayuntamiento', 'origen': 'inventario_urbanismo_sede',
                'url': SOURCE, 'documentos': [], 'lat': None, 'lon': None,
                'geometry': None, 'publication_ready': False,
                'geometry_status': 'Sin geometría verificada del instrumento',
                'vigencia': 'no verificada', 'cobertura': 'parcial',
            }
        groups[key]['documentos'].append(doc)
        if doc['titulo'] in {'EDICTO INICIAL MODIFICACION ED MADROÑAL',
                             'EDICTO APROBACION INICIAL PPO LA FUENTE'}:
            groups[key]['fase'] = 'aprobación inicial (según título del edicto)'
    if not groups:
        raise ValueError('No reviewed planning instruments in live inventory')
    for row in groups.values():
        row['documentos'].sort(key=lambda d: (d['titulo'], d['url']))
        row['url_documento'] = row['documentos'][0]['url']
        row['descripcion'] = 'Documentación publicada en el inventario municipal: ' + '; '.join(
            sorted({d['titulo'] for d in row['documentos']}))
    return sorted(groups.values(), key=lambda row: row['id'])


def preview_metadata(html: str, expected_title: str) -> dict[str, Any]:
    p = soup(html)
    fields = {}
    for dt in p.select('dt'):
        dd = dt.find_next_sibling('dd')
        if dd:
            fields[dt.get_text(' ', strip=True)] = dd.get_text(' ', strip=True)
    if fields.get('Documento') != expected_title or fields.get('Formato') != 'PDF':
        raise ValueError('Document preview title/format mismatch')
    frame = p.select_one('iframe[src]')
    if not frame or not urlparse(official(urljoin(BASE, frame['src']))).path.startswith('/preview/pdf/'):
        raise ValueError('Preview lacks an official PDF')
    integrity = fields.get('Verificación de integridad', '')
    if not re.fullmatch(r'[0-9a-f]{128}', integrity):
        raise ValueError('Preview lacks document integrity hash')
    return {'fecha_creacion_documento_texto': fields.get('Fecha de creación'),
            'csv': fields.get('Código CSV') or None, 'hash_integridad': integrity}


class BenahavisAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.inventory_counts = {}
        self.source_urls = set()
        self.fetch_count = 0

    def _get(self, session, url, ajax=False):
        official(url)
        headers = {'Wicket-Ajax': 'true', 'Referer': SOURCE} if ajax else {}
        with session.get(url, headers=headers, timeout=40, stream=True) as r:
            if r.status_code != 200:
                raise ValueError(f'Unexpected HTTP status {r.status_code} for source')
            official(r.url)
            data = bytearray()
            for chunk in r.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError('Source response exceeds 4 MB')
            text = data.decode(r.encoding or 'utf-8')
            redirect = r.headers.get('Ajax-Location')
        self.fetch_count += 1
        capture = self.config.get('capture_dir')
        if capture:
            folder = Path(capture)
            folder.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(url.split('?')[0].encode()).hexdigest()[:12]
            (folder / f'{self.fetch_count:04d}-{digest}.{"xml" if ajax else "html"}').write_text(text, encoding='utf-8')
        if not ajax:
            self.source_urls.add(url)
        return text, redirect

    def _crawl(self, session, url, expected=None, visited=None):
        visited = visited if visited is not None else set()
        if url in visited or len(visited) >= 20:
            raise ValueError('Cyclic or unexpectedly large folder tree')
        visited.add(url)
        html, _ = self._get(session, url)
        if 'Portal de transparencia' not in html:
            raise ValueError('Missing municipal inventory')
        children = folders(html)
        direct = {d['url']: d for d in documents(html, url)}
        p = soup(html)
        buttons = [b for b in p.select('button[onclick]') if 'Mostrar más' in b.get_text()]
        if len(buttons) > 1:
            raise ValueError('Ambiguous pagination controls')
        if buttons:
            button = buttons[0]
            container = button.find_parent(class_='more_results')
            if not container or not container.get('id'):
                raise ValueError('Unknown pagination container')
            more_url = callback(url, button)
            for _ in range(100):
                xml, redirect = self._get(session, more_url, ajax=True)
                if redirect:
                    raise ValueError('Pagination redirected; session may have expired')
                components = ajax_components(xml)
                markup = ''.join(components.values())
                new = documents(markup, url)
                before = len(direct)
                direct.update({d['url']: d for d in new})
                replacement = soup(components.get(container['id'], '')).find(id=container['id'])
                ended = replacement and 'display:none' in replacement.get('style', '').replace(' ', '')
                if ended:
                    break
                if len(direct) == before:
                    raise ValueError('Pagination made no progress without explicit end')
            else:
                raise ValueError('Pagination exceeds 100 pages; no partial output written')
        total = len(direct) + sum(n for _, n in children)
        if expected is not None and total != expected:
            raise ValueError(f'Inventory count mismatch: expected {expected}, found {total}')
        self.inventory_counts[url] = {'direct_documents': len(direct), 'total_documents': total}
        result = list(direct.values())
        for label, count in children:
            if not count:
                continue
            # Refresh callbacks before following a sibling folder.
            html, _ = self._get(session, url)
            matches = [a for a in soup(html).select('a.gIconLink.exp')
                       if a.get_text(' ', strip=True).startswith(label + ' ')]
            if len(matches) != 1:
                raise ValueError('Folder disappeared or became ambiguous')
            action = callback(url, matches[0])
            _, location = self._get(session, action, ajax=True)
            if not location:
                raise ValueError('Folder callback lacks Ajax-Location')
            child_url = official(urljoin(action, location))
            if not urlparse(child_url).path.startswith('/transparency/'):
                raise ValueError('Unexpected folder redirect')
            result.extend(self._crawl(session, child_url, count, visited))
        return result

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.inventory_counts, self.source_urls, self.fetch_count = {}, set(), 0
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-benahavis/1.0 (public planning inventory)'
            index, _ = self._get(session, BASE + '/transparency')
            counts = [count for label, count in folders(index)
                      if label == '7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE']
            if len(counts) != 1 or not counts[0]:
                raise ValueError('Missing or empty urbanism category in municipal index')
            docs = self._crawl(session, SOURCE, expected=counts[0])
            # Same document can be linked from several inventory folders.
            merged = {}
            for d in docs:
                if d['url'] in merged:
                    merged[d['url']]['inventarios'] = sorted(set(merged[d['url']]['inventarios'] + d['inventarios']))
                else:
                    merged[d['url']] = d
            rows = group_projects(list(merged.values()))
            for row in rows:
                for doc in row['documentos']:
                    html, _ = self._get(session, doc['url'])
                    doc.update(preview_metadata(html, doc['titulo']))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(self.source_urls),
                'inventory_counts': self.inventory_counts, 'inventory_documents': len(docs),
                'selected_documents': sum(len(r['documentos']) for r in rows),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete snapshot: an update must not skip old documents or later pages.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
