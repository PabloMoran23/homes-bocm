"""Alagón's public planning folders, including Wicket 'Mostrar más' pages."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://alagon.es/areas/urbanismo/'
HOST = 'alagon.sedelectronica.es'


def official(url):
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != HOST:
        raise ValueError('Unexpected planning source URL')
    return url


def action_url(element, base):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing Wicket navigation action')
    return official(urljoin(base, match[1]))


def parse_page(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('#content') or soup
    docs = {}
    for a in content.select('a[href*="/preview-document/"]'):
        target = official(urljoin(url, a['href']))
        docs[target] = {'titulo': a.get_text(' ', strip=True), 'url': target,
                        'inventory_url': url}
    folders = {}
    for a in content.select('a.exp[onclick]'):
        text = a.get_text(' ', strip=True)
        count = re.search(r'\(\s*(\d+)\s*\)\s*$', text)
        if not count:
            raise ValueError('Folder lacks document count')
        folders[action_url(a, url)] = (text[:count.start()].strip(), int(count[1]))
    more = content.select('.more_results button[onclick]')
    if len(more) > 1:
        raise ValueError('Ambiguous pagination')
    return list(docs.values()), folders, action_url(more[0], url) if more else None


def ajax_html(xml):
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response' or root.find('redirect') is not None:
        raise ValueError('Unexpected AJAX response')
    components = root.findall('component')
    if not components:
        raise ValueError('Pagination returned no components')
    return ''.join(c.text or '' for c in components)


def make_record(title, url, docs):
    if title.startswith('TEXTO REFUNDIDO PGOU ALAGÓN'):
        kind = 'plan_general_ordenacion_urbana'
    elif title.startswith('ESTUDIO DE DETALLE '):
        kind = 'estudio_de_detalle'
    elif re.match(r'APROBACI[OÓ]N INICIAL MODIFICACIÓN AISLADA', title):
        kind = 'modificacion_plan_general'
    else:
        raise ValueError('Unreviewed instrument folder: ' + title)
    if not docs:
        raise ValueError('Instrument has no documents')
    row = {'id': 'alagon-plan-' + urlparse(url).path.strip('/').split('/')[-1],
           'municipio': 'Alagón', 'provincia': 'Zaragoza', 'codigo_ine': '50008',
           'titulo': title, 'tipo': kind, 'url': url, 'inventory_url': url,
           'source': 'ayuntamiento', 'origen': 'inventario_planeamiento',
           'documentos': docs, 'geometry_status': 'unavailable',
           'publication_ready': False}
    agreement = re.search(r'aprobado por Acuerdo CPUZ de (\d{2}/\d{2}/\d{4})', title)
    if agreement:
        row['fecha_acuerdo'] = datetime.strptime(agreement[1], '%d/%m/%Y').date().isoformat()
        row['fecha_acuerdo_fuente'] = {'url': url, 'texto': agreement[0]}
    if re.match(r'APROBACI[OÓ]N INICIAL ', title):
        row['fase'] = 'aprobacion_inicial'
    return row


class AlagonAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl):
        captures = self.config.get('evidence_dir')
        sources, seen_folders, rows, unassigned = [], set(), [], []
        calls = 0
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-alagon/1.0 (public planning inventory)'

            def fetch(url, ajax=False):
                nonlocal calls
                calls += 1
                if calls > 300:
                    raise ValueError('Inventory traversal exceeded safety limit; output not written')
                response = session.get(url, timeout=40,
                                       headers={'Wicket-Ajax': 'true'} if ajax else {})
                response.raise_for_status()
                if url != SOURCE:
                    official(response.url)
                if captures:
                    path = Path(captures)
                    path.mkdir(parents=True, exist_ok=True)
                    (path / f'live-{calls:03d}.{ "xml" if ajax else "html"}').write_text(
                        response.text, encoding='utf-8')
                return response

            def walk(url, title=None, expected=None):
                response = fetch(url)
                canonical = response.url
                if not urlparse(canonical).path.startswith('/transparency/'):
                    raise ValueError('Folder did not resolve to public transparency page')
                if canonical in seen_folders:
                    raise ValueError('Duplicate folder or navigation cycle')
                seen_folders.add(canonical)
                sources.append(canonical)
                docs, folders, more = parse_page(response.text, canonical)
                docs = {d['url']: d for d in docs}
                while more:
                    batch, children, more = parse_page(ajax_html(fetch(more, True).text), canonical)
                    before = (len(docs), len(folders))
                    docs.update({d['url']: d for d in batch})
                    folders.update(children)
                    if before == (len(docs), len(folders)):
                        raise ValueError('Pagination made no progress')
                total = len(docs)
                for child, (label, count) in folders.items():
                    total += walk(child, label, count)
                if expected is not None and total != expected:
                    raise ValueError(f'Incomplete folder {title}: expected {expected}, got {total}')
                if title and (title.startswith('TEXTO REFUNDIDO PGOU ALAGÓN') or
                              title.startswith('ESTUDIO DE DETALLE ') or
                              re.match(r'APROBACI[OÓ]N INICIAL MODIFICACIÓN AISLADA', title)):
                    if folders:
                        raise ValueError('Instrument grouping changed; review nested folders')
                    rows.append(make_record(title, canonical, list(docs.values())))
                elif docs:
                    unassigned.extend(docs.values())
                return total

            landing = fetch(SOURCE)
            soup = BeautifulSoup(landing.text, 'html.parser')
            links = [a['href'] for a in soup.select('a[href]')
                     if a.get_text(' ', strip=True) == 'ACCESO AL PLAN GENERAL DE ORDENACIÓN URBANA']
            if len(set(links)) != 1:
                raise ValueError('Municipal planning entry link missing or ambiguous')
            root = fetch(official(links[0]))
            sources.extend([SOURCE, root.url])
            _, folders, more = parse_page(root.text, root.url)
            if more:
                raise ValueError('Urbanism root pagination changed; review entry discovery')
            planning = [(u, t, n) for u, (t, n) in folders.items() if t.startswith('7.1. PLANEAMIENTO')]
            if len(planning) != 1:
                raise ValueError('Planning inventory missing or ambiguous')
            total = walk(*planning[0])
        if not rows:
            raise ValueError('No supported planning instruments')
        # Unknown substantive folders must not silently disappear from the extraction.
        if any(d['titulo'] != '1.5 Catálogo' for d in unassigned):
            raise ValueError('Ungrouped planning documents require review')
        self._write(out_jsonl, rows)
        return {'live_records': len(rows), 'count': len(rows), 'documents_enumerated': total,
                'documents_retained': sum(len(r['documentos']) for r in rows),
                'source_urls': list(dict.fromkeys(sources)), 'unassigned_documents': unassigned,
                'coverage': 'current_public_planning_inventory', 'publication_ready': False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'count': 0, 'disabled': True, 'reason': 'No verified public granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
