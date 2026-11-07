"""Municipal POM document inventory, grouped by planning instrument."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://bolanosdecalatrava.es'
SOURCE = BASE + '/node/2352'


def normalized(text):
    return unicodedata.normalize('NFKD', text.lower()).encode('ascii', 'ignore').decode()


def content(html):
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('article[about]')
    if article is None:
        raise ValueError('Missing municipal article; inventory layout changed')
    # Calendar pagination belongs to the surrounding site, not this inventory.
    if article.select('.pager, a[rel~=next], a[rel~=prev]'):
        raise ValueError('Inventory pagination detected; crawler must be extended')
    for a in article.select('a[href]'):
        if re.search(r'[?&]page=', a['href']) or normalized(a.get_text(strip=True)) in {'siguiente', 'next', 'ultima', 'last'}:
            raise ValueError('Inventory pagination detected')
    return article


def document(a, source):
    url = urljoin(source, a['href'])
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not (
        (parsed.hostname == 'bolanosdecalatrava.es' and parsed.path.startswith('/sites/default/files/') and parsed.path.lower().endswith('.pdf'))
        or (parsed.hostname == 'drive.google.com' and parsed.path.startswith('/file/d/'))
    ):
        raise ValueError(f'Unreviewed document link: {url}')
    return {'titulo': a.get_text(' ', strip=True), 'url': url, 'source_url': source,
            'provenance': 'Enlace publicado por el Ayuntamiento; contenido del archivo no interpretado'}


def record(key, title, docs, source_urls):
    return {'id': 'bolanos-de-calatrava-proy-' + key, 'municipio': 'Bolaños de Calatrava',
            'codigo_ine': '13023', 'provincia': 'Ciudad Real', 'titulo': title,
            'tipo': 'planeamiento_urbanistico', 'fase': None,
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_documental_pom',
            'documentos': docs, 'source_urls': source_urls,
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'geometry_status': 'Sin geometría verificada',
            'cobertura': 'Inventario POM municipal; no acredita por sí solo vigencia ni fechas de acuerdos'}


def parse_inventory(html):
    article = content(html)
    groups = {}
    anchors = article.select('.ps_adjunto_pageStatic a[href]')
    if not anchors or 'modificaciones puntuales' not in normalized(article.get_text(' ', strip=True)):
        raise ValueError('Missing POM modification inventory')
    for a in anchors:
        doc = document(a, SOURCE)
        title = normalized(doc['titulo'])
        # MP_6 is the municipal technical document's filename convention.
        match = re.search(r'(?:puntual\s*(?:n[º°o.]?\s*)?|mp_)(\d+)', title)
        correction = re.search(r'correccion\s+(?:de\s+)?errores\s*n[º°o.]?\s*(\d+)', title)
        if correction:
            key = 'correccion-' + correction[1]
            label = f'Corrección de errores nº {correction[1]} del POM de Bolaños de Calatrava'
        elif match:
            key = 'modificacion-' + match[1]
            label = f'Modificación puntual nº {match[1]} del POM de Bolaños de Calatrava'
        else:
            raise ValueError(f'Unclassified POM attachment: {doc["titulo"]}')
        row = groups.setdefault(key, record(key, label, [], [SOURCE]))
        if doc['url'] not in {d['url'] for d in row['documentos']}:
            row['documentos'].append(doc)
    children = []
    for a in article.select('.ps_body_pageStatic a[href]'):
        url = urljoin(SOURCE, a['href'])
        if urlparse(url).hostname != 'bolanosdecalatrava.es' or not re.fullmatch(r'/node/\d+', urlparse(url).path):
            raise ValueError(f'Unreviewed POM section: {url}')
        if url not in children:
            children.append(url)
    if not children:
        raise ValueError('POM base document sections missing')
    return list(groups.values()), children


class BolanosDeCalatravaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=45, headers={'User-Agent': 'municipio-bolanos/1.0'},
                                verify=self.config.get('verify_tls', True))
        response.raise_for_status()
        if urlparse(response.url).hostname != 'bolanosdecalatrava.es':
            raise ValueError('Unexpected inventory redirect')
        response.encoding = 'utf-8'
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            (path / (urlparse(url).path.rsplit('/', 1)[-1] + '.html')).write_text(response.text, encoding='utf-8')
        return response.text

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows, pending = parse_inventory(self._fetch(SOURCE))
        visited = {SOURCE}
        docs = {}
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 30:
                raise ValueError('POM section crawl exceeds reviewed size; no partial output written')
            article = content(self._fetch(url))
            visited.add(url)
            for a in article.select('a[href]'):
                link = urljoin(url, a['href'])
                if urlparse(link).hostname == 'bolanosdecalatrava.es' and re.fullmatch(r'/node/\d+', urlparse(link).path):
                    if link not in visited:
                        pending.append(link)
                else:
                    doc = document(a, url)
                    docs.setdefault(doc['url'], doc)
        if not docs:
            raise ValueError('No base POM documents')
        rows.insert(0, record('pom', 'Plan de Ordenación Municipal de Bolaños de Calatrava', list(docs.values()), sorted(visited)))
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sorted(visited),
                'documents': sum(len(row['documentos']) for row in rows),
                'tls_verified': self.config.get('verify_tls', True), 'coverage': 'partial municipal POM inventory'}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
