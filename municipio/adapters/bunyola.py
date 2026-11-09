"""Public planning document inventory for Bunyola's town centre (not licences)."""
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

SOURCE = 'https://bunyola.sedelectronica.es/transparency/528cc9cb-49b8-4d43-88bb-01277f60bbc5/'
HOST = 'bunyola.sedelectronica.es'
LIMITATIONS = [
    'Only the Normativa urbanística vigent / Nucli de Bunyola inventory; other settlements and pending projects are outside coverage.',
    'Document inventory, not a complete municipal works or granted-licence register.',
    'No publication or agreement dates are exposed in the listing; years in titles are not dates.',
    'PGOU record groups the general-plan document collection, including its published-modifications compilation; no consolidated legal text is inferred.',
    'No verified instrument geometry; no coordinates inferred from maps or municipality centre.',
]


def checked_url(base, target):
    url = urljoin(base, target)
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != HOST:
        raise ValueError('Unexpected source host or scheme')
    return url


def callback(element, base):
    match = re.search(r"wicketAjaxGet\('([^']+)'", element.get('onclick', ''))
    if not match:
        raise ValueError('Missing public Wicket navigation callback')
    return checked_url(base, match[1])


def ajax_html(text):
    root = ET.fromstring(text)
    if root.tag != 'ajax-response' or root.find('redirect') is not None:
        raise ValueError('Unexpected AJAX response')
    components = root.findall('component')
    if not components:
        raise ValueError('No inventory components in pagination response')
    return '\n'.join(c.text or '' for c in components)


def parse_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    entries = []
    for a in soup.select('a.gIconLink'):
        title = a.get_text(' ', strip=True)
        if not title:
            continue
        if 'exp' in a.get('class', []):
            count = re.search(r'\(\s*(\d+)\s*\)\s*$', title)
            if not count:
                raise ValueError('Folder has no document count')
            entries.append({'title': title[:count.start()].strip(), 'count': int(count[1]), 'element': a})
        else:
            url = checked_url(SOURCE, a.get('href', ''))
            if not re.fullmatch(r'/preview-document/[0-9a-f-]{36}', urlparse(url).path):
                raise ValueError('Unrecognized document link')
            entries.append({'title': title, 'url': url})
    more = [b for b in soup.select('button') if re.search(r"Veure.n més|Ver más", b.get_text(' ', strip=True), re.I)]
    if len(more) > 1:
        raise ValueError('Ambiguous pagination')
    # Fail on alternative pagination instead of accepting a partial snapshot.
    if soup.select('a[rel=next]') or re.search(r'\b(Siguiente|Següent)\b', soup.get_text(' ', strip=True)):
        raise ValueError('Unsupported pagination')
    return entries, more[0] if more else None


def make_record(title, url, docs):
    unique = {d['url']: d for d in docs}
    if not unique:
        raise ValueError('Instrument has no source documents')
    return {
        'id': 'bunyola-plan-' + hashlib.sha256(url.encode()).hexdigest()[:16],
        'municipio': 'Bunyola', 'codigo_ine': '07010', 'provincia': 'Illes Balears',
        'titulo': title, 'tipo': 'planeamiento_urbanistico', 'url': url,
        'inventory_url': SOURCE, 'source': 'ayuntamiento', 'origen': 'normativa_urbanistica_vigent_nucli',
        'documentos': list(unique.values()), 'fecha_publicacion': None, 'fecha_acuerdo': None,
        'fecha_aprob': None, 'geometry': None, 'geometry_status': 'unavailable',
        'publication_ready': False,
    }


class BunyolaAyuntamientoAdapter(AyuntamientoAdapter):
    def _get(self, url, ajax=False, referer=SOURCE):
        headers = {'User-Agent': 'municipio-bunyola/1.0'}
        if ajax:
            headers.update({'Wicket-Ajax': 'true', 'Referer': referer})
        response = self.session.get(url, headers=headers, timeout=40)
        response.raise_for_status()
        checked_url(url, response.url)
        if len(response.content) > 5_000_000:
            raise ValueError('Unexpected response size')
        evidence = self.config.get('evidence_dir')
        if evidence:
            directory = Path(evidence)
            directory.mkdir(parents=True, exist_ok=True)
            name = f'source-{len(self.captures):03d}.{"xml" if ajax else "html"}'
            (directory / name).write_bytes(response.content)
            self.captures.append({'url': url, 'capture': name, 'status': response.status_code})
        self.source_urls.add(response.url)
        return response

    def _inventory(self, url):
        html = self._get(url).text
        if 'NORMATIVA URBANÍSTICA VIGENT' not in BeautifulSoup(html, 'html.parser').get_text(' ', strip=True):
            raise ValueError('Wrong inventory or source structure changed')
        all_entries, seen = [], set()
        for _ in range(100):
            entries, more = parse_page(html)
            for entry in entries:
                key = entry.get('url') or entry['title']
                if key in seen:
                    raise ValueError('Repeated inventory entry/page')
                seen.add(key)
                all_entries.append(entry)
            if more is None:
                return all_entries
            if not entries:
                raise ValueError('Pagination made no progress')
            response = self._get(callback(more, url), ajax=True, referer=url)
            html = ajax_html(response.text)
        raise ValueError('Pagination exceeds safety limit; no partial output written')

    def _folder(self, entry):
        response = self._get(callback(entry['element'], SOURCE), ajax=True)
        location = response.headers.get('Ajax-Location')
        if not location:
            raise ValueError('Folder callback did not expose canonical location')
        url = checked_url(SOURCE, location)
        if not re.fullmatch(r'/transparency/[0-9a-f-]{36}/', urlparse(url).path):
            raise ValueError('Unexpected folder location')
        docs = self._inventory(url)
        if any('element' in d for d in docs) or len(docs) != entry['count']:
            raise ValueError('Folder count mismatch or nested folder; review before extraction')
        return url, [{'titulo': d['title'], 'url': d['url'], 'inventory_url': url} for d in docs]

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.session = requests.Session()
        self.source_urls, self.captures = set(), []
        try:
            entries = self._inventory(SOURCE)
            rows, general = [], []
            for entry in entries:
                title = entry['title']
                if 'element' in entry:
                    url, docs = self._folder(entry)
                    if title == 'PGOU de 1982 i modificacions publicades al BOIB':
                        general.extend(docs)
                    elif re.match(r'(Modificació puntual|modificació estudi de detall|estudi de detall)', title, re.I):
                        rows.append(make_record(title, url, docs))
                    else:
                        raise ValueError('Unreviewed instrument folder: ' + title)
                else:
                    doc = {'titulo': title, 'url': entry['url'], 'inventory_url': SOURCE}
                    if re.match(r'modificació puntual', title, re.I):
                        rows.append(make_record(title, entry['url'], [doc]))
                    else:
                        general.append(doc)
            if not any('Normes Urbanístiques PGOU' in d['titulo'] for d in general):
                raise ValueError('Missing general-plan norms')
            rows.insert(0, make_record('PGOU de Bunyola — documentació del nucli i recopilació de modificacions', SOURCE, general))
            self._write(out_jsonl, rows)
            return {'status': 'ok', 'live_records': len(rows), 'source_urls': sorted(self.source_urls),
                    'limitations': LIMITATIONS, 'captures': self.captures, 'publication_ready': False}
        finally:
            self.session.close()

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
