"""Anonymous official transparency inventory, grouped by planning instrument."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://loscorralesdebuelna.sedelectronica.es'
SOURCE = BASE + '/transparency/'


def official(url):
    if urlparse(url).scheme != 'https' or urlparse(url).netloc != urlparse(BASE).netloc:
        raise ValueError('Unexpected external inventory URL')
    return url


def callback(element, page_url):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing public Wicket navigation callback')
    return official(urljoin(page_url, match[1]))


def parse_inventory(html, page_url):
    soup = BeautifulSoup(html, 'html.parser')
    entries = []
    for a in soup.select('td.class_name a.gIconLink'):
        title = a.get_text(' ', strip=True)
        count = a.select_one('.linkExtraInfo')
        if count:
            match = re.fullmatch(r'\s*\(\s*(\d+)\s*\)\s*', count.text)
            if not match:
                raise ValueError('Unrecognized folder document count')
            title = title[:title.rfind(count.get_text(' ', strip=True))].strip()
            entries.append({'titulo': title, 'count': int(match[1]), 'callback': callback(a, page_url)})
        elif '/preview-document/' in a.get('href', ''):
            entries.append({'titulo': title, 'url': official(urljoin(page_url, a['href']))})
        else:
            raise ValueError('Unrecognized transparency inventory entry')
    more = [e for e in soup.select('button, a') if e.get_text(' ', strip=True).lower() in {'mostrar más', 'siguiente'}]
    if len(more) > 1:
        raise ValueError('Ambiguous pagination')
    return entries, callback(more[0], page_url) if more else None


def ajax_html(xml):
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response' or root.find('redirect') is not None:
        raise ValueError('Unexpected Wicket pagination response')
    components = root.findall('component')
    if not components:
        raise ValueError('Pagination returned no components')
    return ''.join(e.text or '' for e in components)


def group_projects(entries, pgou_url, pgou_docs):
    """Environmental documents attest instruments, not their final approval."""
    rows = []
    for entry in entries:
        if 'count' in entry:
            if not re.fullmatch(r'PUBLICACION EN EL BOC APROBACION DEFINITIVA PGOU 2015', entry['titulo']):
                raise ValueError('New urbanismo folder needs semantic review')
            title = 'Plan General de Ordenación Urbana de Los Corrales de Buelna (PGOU 2015)'
            key, phase, url, docs = 'pgou-2015', 'aprobación definitiva', pgou_url, pgou_docs
        elif 'Informe Ambiental' in entry['titulo'] or 'informe Ambiental' in entry['titulo']:
            if 'Modificación Puntual Número 1 del PGOU' not in entry['titulo']:
                raise ValueError('Unrecognized planning instrument')
            title = 'Modificación Puntual Número 1 del PGOU de Los Corrales de Buelna'
            key, phase, url, docs = 'pgou-mp1', 'informe ambiental estratégico', entry['url'], [entry]
        elif 'Plan Parcial del sector de suelo urbano no consolidado nº 10' in entry['titulo']:
            title = 'Plan Parcial del sector de suelo urbano no consolidado nº 10 del PGOU de Los Corrales de Buelna'
            key, phase, url, docs = 'plan-parcial-sunc-10', 'documento de alcance del estudio ambiental estratégico', entry['url'], [entry]
        else:
            raise ValueError('New urbanismo document needs semantic review')
        if not docs or any('url' not in d for d in docs):
            raise ValueError('Missing instrument documents')
        rows.append({
            'id': 'los-corrales-de-buelna-proy-' + key,
            'municipio': 'Los Corrales de Buelna', 'codigo_ine': '39025',
            'provincia': 'Cantabria', 'titulo': title,
            'tipo': 'planeamiento_urbanistico', 'fase': phase,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': url, 'source': 'ayuntamiento', 'origen': 'portal_transparencia_urbanismo',
            'documentos': [{'titulo': d['titulo'], 'url': d['url']} for d in docs],
            'descripcion': 'Instrumento identificado en la carpeta municipal 9. URBANISMO. ' +
                           'Fase documentada: ' + phase + '. Cobertura parcial del portal de transparencia.',
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
        })
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Multiple documents for an instrument require grouping review')
    return rows


class LosCorralesDeBuelnaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, url, ajax=False):
        official(url)
        headers = {'Wicket-Ajax': 'true', 'Referer': SOURCE} if ajax else {}
        response = self.session.get(url, timeout=40, headers=headers)
        response.raise_for_status()
        official(response.url)
        if len(response.content) > 5_000_000:
            raise ValueError('Inventory exceeds response limit')
        self.source_urls.add(response.url)
        if self.config.get('capture_dir'):
            path = Path(self.config['capture_dir'])
            path.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(response.url.encode()).hexdigest()[:20]
            (path / (name + ('.xml' if ajax else '.html'))).write_bytes(response.content)
        return response

    def _folder(self, entry, page_url):
        response = self._get(entry['callback'], ajax=True)
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Folder navigation lacks Ajax-Location')
        target = official(urljoin(page_url, location))
        if not re.fullmatch(r'/transparency/[0-9a-f-]{36}/', urlparse(target).path):
            raise ValueError('Unexpected folder destination')
        return target

    def _inventory(self, url):
        html = self._get(url).text
        entries, more = parse_inventory(html, url)
        seen = set()
        for _ in range(100):
            if not more:
                break
            if more in seen:
                raise ValueError('Pagination loop')
            seen.add(more)
            response = self._get(more, ajax=True)
            extra, more = parse_inventory(ajax_html(response.text), url)
            if not extra:
                raise ValueError('Pagination made no progress')
            entries.extend(extra)
        else:
            raise ValueError('Pagination safety limit reached; no partial output written')
        identities = [e.get('url') or e['callback'] for e in entries]
        if len(identities) != len(set(identities)):
            raise ValueError('Duplicate inventory entries')
        if not entries:
            raise ValueError('Empty inventory or changed markup')
        return entries

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = set()
        with requests.Session() as self.session:
            self.session.headers['User-Agent'] = 'municipio-los-corrales-de-buelna/1.0'
            root = self._inventory(SOURCE)
            folders = [e for e in root if e['titulo'] == '9. URBANISMO' and 'count' in e]
            if len(folders) != 1:
                raise ValueError('Missing unique municipal Urbanismo inventory')
            urban_url = self._folder(folders[0], SOURCE)
            entries = self._inventory(urban_url)
            pgou = [e for e in entries if 'count' in e]
            if len(pgou) != 1:
                raise ValueError('Changed planning folder structure')
            pgou_url = self._folder(pgou[0], urban_url)
            docs = self._inventory(pgou_url)
            if any('count' in d for d in docs) or len(docs) != pgou[0]['count']:
                raise ValueError('Incomplete PGOU document inventory')
            if len(docs) + len(entries) - 1 != folders[0]['count']:
                raise ValueError('Urbanismo total count mismatch')
            rows = group_projects(entries, pgou_url, docs)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(self.source_urls),
                'documents': sum(len(r['documentos']) for r in rows), 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
