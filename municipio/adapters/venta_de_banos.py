"""Inventario público de planeamiento de Venta de Baños (Gestiona/Wicket)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://ventadebanos.sedelectronica.es'
SOURCE = BASE + '/transparency'


def normalized(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def ajax_html(xml):
    """Read returned components as data; never execute Wicket JavaScript."""
    root = ET.fromstring(xml)
    if root.tag != 'ajax-response' or root.find('redirect') is not None:
        raise ValueError('Unexpected Wicket response')
    components = root.findall('component')
    if not components:
        raise ValueError('Pagination returned no components')
    for component in components:
        if component.get('encoding') not in (None, 'wicket1'):
            raise ValueError('Unsupported Wicket encoding')
    # wicket1 escapes ] as ]^, in addition to the CDATA XML envelope.
    return ''.join((c.text or '').replace(']^', ']') if c.get('encoding') == 'wicket1'
                   else (c.text or '') for c in components)


def parse_entries(html, initial=True):
    soup = BeautifulSoup(html, 'html.parser')
    container = soup.select_one('.TransparencyListPanel') if initial else soup
    if container is None:
        raise ValueError('Missing municipal inventory table')
    entries = []
    for a in container.select('a.gIconLink'):
        count = a.select_one('.linkExtraInfo')
        label = a.get_text(' ', strip=True)
        if 'exp' in a.get('class', []):
            match = re.fullmatch(r'\s*\(\s*(\d+)\s*\)\s*', count.get_text() if count else '')
            if not match:
                raise ValueError('Folder lacks document count')
            title = label[:label.rfind('(')].strip()
            entries.append({'titulo': title, 'count': int(match[1]), 'action': a.get('onclick', '')})
        else:
            url = urljoin(BASE, a.get('href', ''))
            if urlparse(url).netloc != urlparse(BASE).netloc or not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(url).path):
                raise ValueError('Unexpected document link')
            entries.append({'titulo': label, 'url': url, 'descripcion_fuente': a.get('title')})
    buttons = soup.select('.more_results button[onclick]')
    if len(buttons) > 1:
        raise ValueError('Ambiguous pagination')
    return entries, buttons[0]['onclick'] if buttons else None


def instrument_key(title):
    key = normalized(title)
    key = re.sub(r'\bdiligenciado\b', '', key)
    key = re.sub(r'[^a-z0-9]+', ' ', key).strip()
    if 'sur se 07' in key:
        return 'plan-parcial-sur-se-07'
    return re.sub(r'\s+', ' ', key)


def build_records(inventory_url, groups, loose):
    """Folder is the instrument boundary; merge explicit duplicate plan versions."""
    merged = {}
    for title, url, docs in groups:
        if not docs:
            continue
        if not re.match(r'^(modificacion|aprobacion modificacion|estudio de detalle|plan parcial|proyecto)', normalized(title)):
            raise ValueError('Unreviewed instrument category: ' + title)
        key = instrument_key(title)
        item = merged.setdefault(key, {'titulo': title, 'urls': [], 'docs': {}})
        item['urls'].append(url)
        for doc in docs:
            item['docs'].setdefault(doc['url'], doc)
    for doc in loose:
        title = normalized(doc['titulo'])
        if 'plan parcial sur-se 07' in title:
            key = 'plan-parcial-sur-se-07'
        elif title.startswith('aprobacion definitiva estudio de detalle calle casado del alisal, 14'):
            key = 'estudio-detalle-casado-del-alisal-14'
            merged.setdefault(key, {'titulo': doc['titulo'], 'urls': [inventory_url], 'docs': {}})
        else:
            raise ValueError('Ungrouped root document: ' + doc['titulo'])
        if key not in merged:
            raise ValueError('Plans lack parent instrument')
        merged[key]['docs'][doc['url']] = doc
    rows = []
    for key, item in merged.items():
        title = item['titulo']
        reference = re.search(r'EXP(?:TE|T)\.\s*(\d+/\d{4})', title, re.I)
        docs = list(item['docs'].values())
        # Dates in file names and report titles are not project approval dates.
        rows.append({
            'id': 'venta-de-banos-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
            'municipio': 'Venta de Baños', 'provincia': 'Palencia', 'codigo_ine': '34023',
            'titulo': title, 'tipo': 'urbanizacion' if 'urbanizaci' in normalized(title) else 'planeamiento_urbanistico',
            'expediente': reference[1] if reference else None,
            'fase': 'aprobación definitiva' if 'aprobacion definitiva' in normalized(title) or
                    any('aprobada definitivamente' in normalized(d['titulo']) for d in docs) else None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': item['urls'][0], 'source': 'ayuntamiento', 'origen': 'inventario_planeamiento_municipal',
            'source_inventory': inventory_url, 'urls_instrumento': sorted(set(item['urls'])),
            'documentos': docs, 'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'geometry_status': 'unavailable',
            'cobertura': 'Inventario de transparencia; fechas y geometría no extraídas del contenido PDF.',
        })
    if not rows:
        raise ValueError('No verified planning instruments')
    return sorted(rows, key=lambda r: r['id'])


class VentaDeBanosAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, url, ajax=False):
        if urlparse(url).netloc != urlparse(BASE).netloc:
            raise ValueError('Off-site municipal request')
        headers = {'User-Agent': 'municipio-venta-de-banos/1.0'}
        if ajax:
            headers.update({'Wicket-Ajax': 'true', 'Referer': SOURCE})
        r = self.session.get(url, headers=headers, timeout=40)
        r.raise_for_status()
        if len(r.content) > 8_000_000:
            raise ValueError('Inventory response too large')
        self.source_urls.add(url if not ajax else url.split('?')[0])
        if self.config.get('evidence_dir'):
            directory = Path(self.config['evidence_dir'])
            directory.mkdir(parents=True, exist_ok=True)
            name = f'{self.capture_index:04d}-' + hashlib.sha256(url.encode()).hexdigest()[:20]
            self.capture_index += 1
            (directory / (name + ('.xml' if ajax else '.html'))).write_bytes(r.content)
        return r

    def _action(self, page_url, action):
        match = re.search(r"wicketAjaxGet\('([^']+)'", action)
        if not match:
            raise ValueError('Missing Wicket action')
        return self._get(urljoin(page_url, match[1]), ajax=True)

    def _folder_url(self, page_url, entry):
        r = self._action(page_url, entry['action'])
        location = r.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Folder action lacks canonical URL')
        return urljoin(page_url, location)

    def _listing(self, url):
        html = self._get(url).text
        result, action = parse_entries(html)
        pages = 0
        while action:
            if pages >= 100:
                raise ValueError('Pagination stalled or exceeds reviewed bound')
            pages += 1
            more, action = parse_entries(ajax_html(self._action(url, action).text), initial=False)
            existing = {e.get('url') or e['titulo'] for e in result}
            if not more or any((e.get('url') or e['titulo']) in existing for e in more):
                raise ValueError('Pagination produced no new entries')
            result.extend(more)
        identities = [e.get('url') or e['titulo'] for e in result]
        if len(identities) != len(set(identities)):
            raise ValueError('Duplicate inventory entries across pagination')
        return result

    def _documents(self, url, expected, visited):
        if url in visited or len(visited) >= 100:
            raise ValueError('Cyclic or excessive folder traversal')
        visited.add(url)
        docs = []
        for entry in self._listing(url):
            if 'url' in entry:
                docs.append({**entry, 'source_page': url})
            else:
                child = self._folder_url(url, entry)
                docs.extend(self._documents(child, entry['count'], visited))
        if len(docs) != expected:
            raise ValueError(f'Document count mismatch at {url}: {len(docs)} != {expected}')
        return docs

    def backfill_proyectos(self, out_jsonl):
        self.session = requests.Session()
        self.source_urls = set()
        self.capture_index = 0
        try:
            url = SOURCE
            for prefix in ('7. URBANISMO,', '7.1. PLANEAMIENTO'):
                entries = self._listing(url)
                matches = [e for e in entries if e['titulo'].startswith(prefix)]
                if len(matches) != 1:
                    raise ValueError('Missing/ambiguous planning category')
                category = matches[0]
                url = self._folder_url(url, category)
            groups, loose, visited = [], [], set()
            for entry in self._listing(url):
                if 'url' in entry:
                    loose.append({**entry, 'source_page': url})
                else:
                    folder_url = self._folder_url(url, entry)
                    groups.append((entry['titulo'], folder_url,
                                   self._documents(folder_url, entry['count'], visited)))
            total = len(loose) + sum(len(g[2]) for g in groups)
            if total != category['count']:
                raise ValueError(f'Planning inventory incomplete: {total} != {category["count"]}')
            rows = build_records(url, groups, loose)
            self._write(out_jsonl, rows)
            return {'status': 'ok', 'rows': len(rows), 'documents': total,
                    'source_urls': sorted(self.source_urls), 'publication_ready': False}
        finally:
            self.session.close()

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
