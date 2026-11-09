"""Municipal planning library: one record per instrument, not per PDF sheet."""
from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from pathlib import Path
from urllib.parse import unquote, urldefrag, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://camarinas.net/portal-cidadan/presentacion-urbanismo/gl'
LIMITATIONS = [
    'Partial coverage: municipal PXOM, PEPRI and linked PXOM modification only; no works/news/procurement crawl.',
    'Document editions are not approval agreements. Dates and legal status are not inferred from filenames or covers.',
    'PDF URLs are inventoried from official indexes, not all PDF contents or availability are verified.',
    'No verified licence register or instrument geometry; coordinates and dates remain null.',
]


def canonical_url(base, href):
    """The legacy www HTTP links have a working, certificate-valid apex HTTPS equivalent."""
    parts = urlsplit(urldefrag(urljoin(base, href))[0])
    if parts.hostname in {'camarinas.net', 'www.camarinas.net'}:
        return urlunsplit(('https', 'camarinas.net', parts.path, parts.query, ''))
    return urlunsplit(parts)


def parse_links(html, base):
    soup = BeautifulSoup(html, 'html.parser')
    links = {}
    for node in soup.select('a[href], area[href], frame[src], iframe[src]'):
        href = node.get('href', node.get('src', ''))
        if not href or href.startswith('#'):
            continue
        url = canonical_url(base, href)
        label = node.get_text(' ', strip=True) or node.get('alt') or node.get('title') or unquote(urlsplit(url).path.rsplit('/', 1)[-1])
        # Never silently accept a newly paginated portal inventory.
        if ('next' in node.get('rel', []) or label.casefold() in {'seguinte', 'siguiente', 'next', 'seguinte »'}):
            raise ValueError('Pagination appeared: review and implement before extracting')
        links.setdefault(url, label)
    return links


def discover_instruments(html):
    links = parse_links(html, SOURCE)
    result = {}
    for url, title in links.items():
        if urlsplit(url).hostname != 'camarinas.net':
            continue
        label = title.casefold()
        if label == 'pxom':
            result['pxom'] = (url, 'PXOM de Camariñas')
        elif label == 'pepri':
            result['pepri'] = (url, 'PEPRI de Camariñas')
        elif 'modificación puntual pxom' in label:
            result['modificacion-pxom'] = (url, title)
    if set(result) != {'pxom', 'pepri', 'modificacion-pxom'}:
        raise ValueError('Municipal planning navigation changed or is incomplete')
    return result


class CamarinasAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='camarinas', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://camarinas.net')
        self.source_urls = []

    def _fetch(self, url):
        time.sleep(float(self.config.get('request_pause', .15)))
        response = requests.get(url, timeout=35, headers={
            'User-Agent': 'municipio-camarinas/1.0 (public planning inventory)',
        })
        response.raise_for_status()
        if urlsplit(response.url).hostname != 'camarinas.net':
            raise ValueError('Unexpected external redirect')
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected an HTML planning index: ' + url)
        response.encoding = response.apparent_encoding
        self.source_urls.append(url)
        if self.config.get('capture_dir'):
            folder = Path(self.config['capture_dir'])
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:20] + '.html'
            (folder / name).write_text(response.text, encoding='utf-8')
        return response.text

    def _instrument(self, key, url, title):
        # The two legacy libraries use nested frames, HTML lists and image maps.
        prefix = '/' + key + '/' if key in {'pxom', 'pepri'} else None
        queue = deque([url])
        seen, documents = set(), {}
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            if len(seen) >= 200:
                raise ValueError('Planning library exceeds 200 HTML pages; no truncated output accepted')
            seen.add(current)
            html = self._fetch(current)
            links = parse_links(html, current)
            if not prefix:
                content = BeautifulSoup(html, 'html.parser').select_one('.listado-descargas-convocatorias')
                if content is None:
                    raise ValueError('Modification document container missing')
                links = parse_links(str(content), current)
            for target, label in links.items():
                parsed = urlsplit(target)
                if parsed.hostname != 'camarinas.net':
                    continue
                if prefix and not parsed.path.startswith(prefix):
                    continue
                if not prefix and not parsed.path.startswith('/media/documentos/'):
                    continue
                if parsed.path.lower().endswith('.pdf'):
                    if target not in documents:
                        documents[target] = {'titulo': label, 'url': target, 'url_indice': current,
                                             'origen': 'biblioteca_municipal', 'contenido_verificado': False}
                elif prefix and parsed.path.lower().endswith(('.htm', '.html')):
                    if 'axuda' not in parsed.path.lower():
                        queue.append(target)
            if not prefix:
                break
        if not documents:
            raise ValueError('Instrument has no linked source documents: ' + url)
        return {
            'id': 'camarinas-proy-' + key, 'municipio': 'Camariñas',
            'codigo_ine': '15016', 'provincia': 'A Coruña', 'titulo': title,
            'tipo': 'planeamiento_urbanistico', 'url': url,
            'source': 'ayuntamiento', 'origen': 'biblioteca_planeamiento_municipal',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'descripcion': 'Instrumento enlazado desde Urbanismo municipal; documentos agrupados sin inferir aprobación ni vigencia.',
            'documentos': [documents[k] for k in sorted(documents)],
            'paginas_fuente': sorted(seen), 'url_inventario': SOURCE,
            'lat': None, 'lon': None, 'geometry': None,
            'geometry_status': 'unavailable', 'publication_ready': False,
        }

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        inventory = discover_instruments(self._fetch(SOURCE))
        rows = [self._instrument(key, url, title) for key, (url, title) in inventory.items()]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': self.source_urls,
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl, state_path):
        # A complete refresh: removed documents must not survive an append-only update.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory; forms excluded'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
