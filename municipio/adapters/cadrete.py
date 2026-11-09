"""Cadrete's public transparency planning folders, grouped by instrument."""
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

BASE = 'https://cadrete.sedelectronica.es'
SOURCE = BASE + '/transparency/4f82e54f-53f4-4420-91aa-c85715af55f2/'
LIMITATIONS = [
    'Partial coverage: only named Plan General, Plan Parcial and Plan Especial folders in section 7.1; excludes detail-study collection, agreements, public works and other sections.',
    'Document inventory metadata only; PDF contents are not parsed. Presence in transparency does not establish approval or current legal validity.',
    'No verified publication/agreement/approval dates or project geometry; dates and coordinates remain null.',
]


def action_url(tag, base):
    match = re.search(r"wicketAjaxGet\('([^']+)'", tag.get('onclick', ''))
    if not match:
        raise ValueError('Missing public navigation action')
    url = urljoin(base, match[1])
    if urlparse(url).hostname != 'cadrete.sedelectronica.es':
        raise ValueError('Unexpected navigation host')
    return url


def fragment(text):
    if text.lstrip().startswith('<?xml'):
        root = ET.fromstring(text)
        if root.tag != 'ajax-response' or root.find('redirect') is not None:
            raise ValueError('Unexpected AJAX response')
        text = '\n'.join(c.text or '' for c in root.findall('component'))
    if not text.strip():
        raise ValueError('Empty inventory response')
    return BeautifulSoup(text, 'html.parser')


def entries(soup, base):
    result = []
    for a in soup.select('a.gIconLink'):
        if not a.find_parent('td', class_='class_name'):
            continue
        title = a.get_text(' ', strip=True)
        count = a.select_one('.linkExtraInfo')
        if 'exp' in a.get('class', []):
            if not count or not re.fullmatch(r'\s*\(\s*\d+\s*\)\s*', count.get_text()):
                raise ValueError('Folder lacks document count')
            result.append({'titulo': re.sub(r'\s*\(\s*\d+\s*\)\s*$', '', title),
                           'count': int(re.search(r'\d+', count.get_text())[0]),
                           'action': action_url(a, base)})
        else:
            url = urljoin(base, a.get('href', ''))
            if not re.fullmatch(re.escape(BASE) + r'/preview-document/[0-9a-f-]{36}', url):
                raise ValueError('Unexpected document link')
            result.append({'titulo': title, 'url': url})
    return result


class CadreteAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)
        self.source_urls = []
        self._captures = 0

    def _fetch(self, session, url):
        response = session.get(url, timeout=(10, 35))
        response.raise_for_status()
        if urlparse(response.url).hostname != 'cadrete.sedelectronica.es':
            raise ValueError('Unexpected source redirect')
        if len(response.content) > 4_000_000:
            raise ValueError('Oversized inventory response')
        # Save public captures only; no session cookies or request headers.
        self.source_urls.append(response.url)
        capture = self.config.get('evidence_dir')
        if capture:
            folder = Path(capture); folder.mkdir(parents=True, exist_ok=True)
            (folder / f'capture-{self._captures:03}.html').write_text(response.text, encoding='utf-8')
            self._captures += 1
        return response

    def _inventory(self, session, url):
        response = self._fetch(session, url)
        canonical = response.url
        if not re.fullmatch(re.escape(BASE) + r'/transparency/[0-9a-f-]{36}/', canonical):
            raise ValueError('Missing stable transparency folder URL')
        soup = fragment(response.text)
        rows = entries(soup, response.url)
        for _ in range(100):
            more = [b for b in soup.select('button[onclick]') if b.get_text(' ', strip=True) == 'Mostrar más']
            if not more:
                break
            if len(more) != 1:
                raise ValueError('Ambiguous pagination')
            response = self._fetch(session, action_url(more[0], response.url))
            soup = fragment(response.text)
            added = entries(soup, response.url)
            if not added and not soup.select_one('div[style="display:none"]'):
                raise ValueError('Pagination made no progress')
            rows.extend(added)
        else:
            raise ValueError('Pagination limit reached; refusing partial output')
        keys = [r.get('url', r.get('action')) for r in rows]
        if len(set(keys)) != len(keys) or not rows:
            raise ValueError('Empty or repeated inventory')
        return canonical, rows

    def _documents(self, session, folder, path=(), depth=0):
        if depth > 8:
            raise ValueError('Unexpected folder depth')
        canonical, rows = self._inventory(session, folder['action'])
        docs = []
        for row in rows:
            if 'action' in row:
                docs.extend(self._documents(session, row, path + (row['titulo'],), depth + 1)[1])
            else:
                docs.append({**row, 'carpeta': list(path), 'source_url': canonical})
        if len(docs) != folder['count'] or len({d['url'] for d in docs}) != len(docs):
            raise ValueError('Document count differs from advertised inventory; refusing partial output')
        return canonical, docs

    @staticmethod
    def record(title, url, docs):
        if not re.match(r'^Plan (General|Parcial|Especial)\b', title) or not docs:
            raise ValueError('Unsupported instrument or missing documents')
        return {
            'id': 'cadrete-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'municipio': 'Cadrete', 'provincia': 'Zaragoza', 'codigo_ine': '50066',
            'titulo': title, 'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': url, 'source': 'ayuntamiento', 'origen': 'portal_transparencia_planeamiento',
            'documentos': docs, 'lat': None, 'lon': None, 'geometry': None,
            'publication_ready': False, 'limitations': LIMITATIONS,
        }

    @staticmethod
    def _write(path, rows):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-cadrete/1.0'
            _, inventory = self._inventory(session, SOURCE)
            plans = [r for r in inventory if 'action' in r and re.match(r'^Plan (General|Parcial|Especial)\b', r['titulo'])]
            if not plans:
                raise ValueError('No supported planning instruments')
            rows = []
            for plan in plans:
                url, docs = self._documents(session, plan)
                rows.append(self.record(plan['titulo'], url, docs))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': list(dict.fromkeys(self.source_urls)),
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
