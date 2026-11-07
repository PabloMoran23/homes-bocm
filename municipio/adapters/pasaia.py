"""Pasaia's municipal planning catalogue, including its nested document folders."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.pasaia.eus'
SOURCE = BASE + '/es/ordenanzas-urbanismo'


def canonical(url):
    p = urlsplit(url)
    path = p.path
    if not path.startswith('/documents/') and not path.startswith('/es/'):
        path = '/es' + path
    query = parse_qs(p.query)
    # Only the folder identifies content; Liferay timestamps are cache parameters.
    return BASE + path + ('?' + urlencode({'folder': query['folder'][0]}) if 'folder' in query else '')


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.select_one('#main-content')
    if main is None:
        raise ValueError('Missing municipal main-content')
    return main


def require_unpaginated(block):
    # Check the inventory itself, not the unrelated latest-news widget.
    for a in block.select('a[href]'):
        href = a['href']
        if (a.get_text(' ', strip=True).lower() in {'siguiente', 'next', 'hurrengoa'}
                and href and not href.startswith(('javascript:', '#'))):
            raise ValueError('Unsupported active pagination in planning catalogue')
        if any(k.endswith(('_cur', '_page', '_start')) for k in parse_qs(urlsplit(href).query)):
            raise ValueError('Unexpected pagination in planning catalogue')


def parse_inventory(html):
    main = content(html)
    heading = next((h for h in main.select('h1,h2,h3,h4')
                    if h.get_text(' ', strip=True).upper() == 'PLANEAMIENTO'), None)
    # The heading is embedded in a journal article in the live catalogue.
    if heading is None:
        raise ValueError('Planning inventory heading missing')
    block = heading.find_parent(class_='journal-content-article')
    if block is None:
        raise ValueError('Planning inventory structure changed')
    require_unpaginated(block)
    rows = {}
    for a in block.select('a[href]'):
        title = a.get_text(' ', strip=True)
        if not title:
            continue  # image duplicates, not separate instruments
        u = urljoin(SOURCE, a['href'])
        if urlsplit(u).hostname != 'www.pasaia.eus':
            raise ValueError('Unexpected external instrument')
        if not re.match(r'^(Normas subsidiarias|Plan especial)', title, re.I):
            raise ValueError('Unreviewed inventory entry: ' + title)
        rows[canonical(u)] = title
    if not rows:
        raise ValueError('Empty planning catalogue')
    return rows


def parse_page(html, url):
    main = content(html)
    require_unpaginated(main)
    docs, children = {}, set()
    root = urlsplit(url).path
    for a in main.select('a[href]'):
        u = urljoin(url, a['href'])
        p = urlsplit(u)
        if p.hostname != 'www.pasaia.eus':
            continue
        if p.path.startswith('/documents/'):
            doc_url = canonical(u)
            container = a.find_parent(class_='documento')
            label = container.select_one('.titulo') if container else None
            title = label.get_text(' ', strip=True) if label else a.get_text(' ', strip=True)
            docs.setdefault(doc_url, {'titulo': title, 'url': doc_url, 'source_urls': []})
            if url not in docs[doc_url]['source_urls']:
                docs[doc_url]['source_urls'].append(url)
        elif (p.path == root and 'folder' in parse_qs(p.query)) or (
                root == '/es/nnss' and re.fullmatch(r'/(es/)?nnss-[abc]', p.path)):
            children.add(canonical(u))
    if not docs and not children:
        raise ValueError('Instrument page has no documents or folders: ' + url)
    return docs, sorted(children), main


def agreement_date(text):
    months = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
    m = re.search(r'(\d{1,2}) de (' + '|'.join(months) + r') de (\d{4})', text, re.I)
    return date(int(m[3]), months.index(m[2].lower()) + 1, int(m[1])).isoformat() if m else None


class PasaiaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='pasaia', config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, url):
        r = requests.get(url, timeout=35, headers={'User-Agent': 'municipio-pasaia/1.0'})
        r.raise_for_status()
        if urlsplit(r.url).hostname != 'www.pasaia.eus' or len(r.content) > 5_000_000:
            raise ValueError('Unexpected redirect or oversized municipal page')
        capture = self.config.get('capture_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_text(r.text, encoding='utf-8')
        return r.text

    @staticmethod
    def _record(url, title, tipo='planeamiento_urbanistico'):
        return {'id': 'pasaia-proy-' + hashlib.sha256(url.encode()).hexdigest()[:16],
                'municipio': 'Pasaia', 'codigo_ine': '20064', 'provincia': 'Gipuzkoa',
                'titulo': title, 'tipo': tipo, 'url': url, 'source': 'ayuntamiento',
                'origen': 'inventario_municipal_planeamiento', 'fecha': None,
                'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
                'publication_ready': False, 'documentos': [], 'source_urls': []}

    def backfill_proyectos(self, out_jsonl):
        inventory = parse_inventory(self._fetch(SOURCE))
        records = []
        sources = [SOURCE]
        for root, title in inventory.items():
            row = self._record(root, title)
            pending, seen = [root], set()
            assigned = {root: '__root__'}
            groups = {'__root__': row}
            documents = {'__root__': {}}
            separate_urls = set()
            while pending:
                url = pending.pop(0)
                if url in seen:
                    continue
                if len(seen) >= 200:
                    raise ValueError('Folder traversal limit reached; refusing partial output')
                time.sleep(.1)
                found, children, main = parse_page(self._fetch(url), url)
                owner = assigned[url]
                current = groups[owner]
                current['source_urls'].append(url)
                docs = documents[owner]
                seen.add(url)
                sources.append(url)
                # Approval narrative names two distinct instruments. Never attach
                # the urbanisation approval to the residential special plan.
                for li in main.select('.journal-content-article li'):
                    text = li.get_text(' ', strip=True)
                    if 'Proyecto de Urbanización' in text:
                        links = [canonical(urljoin(url, a['href'])) for a in li.select('a[href]')
                                 if '/documents/' in a['href']]
                        if len(links) != 1 or not re.search(r'Proyecto de Urbanización del área .+ de Pasaia', text):
                            raise ValueError('Unreviewed urbanisation approval structure')
                        doc_url = links[0]
                        if doc_url not in separate_urls:
                            extra = self._record(doc_url, re.search(r'Proyecto de Urbanización del área .+ de Pasaia', text)[0], 'proyecto_urbanizacion')
                            extra.update(fecha_acuerdo=agreement_date(text), fecha_aprob=agreement_date(text),
                                         descripcion=text, source_urls=[root], documentos=[found[doc_url]])
                            records.append(extra)
                            separate_urls.add(doc_url)
                    elif 'Aprobación Inicial del' in text and 'PLAN ESPECIAL' in text:
                        row['descripcion'] = text
                        row['fecha_acuerdo'] = agreement_date(text)
                        row['fecha_aprob'] = agreement_date(text)
                        row['alcance_fecha_aprob'] = 'aprobación inicial; no acredita aprobación definitiva del plan'
                for key, doc in found.items():
                    if key not in docs:
                        docs[key] = doc
                    else:
                        docs[key]['source_urls'] = sorted(set(docs[key]['source_urls'] + doc['source_urls']))
                for child in children:
                    if child in assigned:
                        continue  # breadcrumbs and cyclic folder links
                    labels = [a.get_text(' ', strip=True) for a in main.select('a[href]')
                              if canonical(urljoin(url, a['href'])) == child]
                    instrument = next((label for label in labels if re.search(
                        r'modificaci[oó]n|^Plan (especial|parcial)|^Programa de Actuaci', label, re.I)), None)
                    child_owner = owner
                    if instrument:
                        # One named modification is linked from two area folders.
                        # Keep it as one instrument with both document provenances.
                        child_owner = instrument.casefold()
                        if child_owner not in groups:
                            groups[child_owner] = self._record(child, instrument)
                            groups[child_owner]['instrumento_marco_url'] = root
                            documents[child_owner] = {}
                    assigned[child] = child_owner
                    pending.append(child)
            for owner, item in groups.items():
                item['documentos'] = [d for u, d in documents[owner].items() if u not in separate_urls]
                item['source_urls'] = [SOURCE] + sorted(set(item['source_urls']))
                if not item['documentos']:
                    raise ValueError('Instrument lacks documents: ' + item['url'])
                records.append(item)
        result = self._write(out_jsonl, sorted(records, key=lambda r: r['id']))
        return {**result, 'source_urls': sorted(set(sources)), 'coverage': 'municipal planning catalogue only'}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)
        return {'status': 'ok', 'rows': len(rows)}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), 'status': 'disabled'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
