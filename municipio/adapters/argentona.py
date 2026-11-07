"""Argentona's two municipal document inventories, grouped by instrument.

Dates and geometry are deliberately unknown: the inventory provides titles and
PDF links, not dated agreements or machine-readable project boundaries.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://argentona.cat/'
SOURCES = {
    'exposicion_publica': BASE + 'document.php?id=63455',
    'documentos_aprobados': BASE + 'document.php?id=63456',
}
LIMITATIONS = [
    'Partial coverage: two current municipal document inventories, not all municipal history or POUM documents.',
    'Inventory titles establish document identity; PDF bodies and agreement dates are not parsed.',
    'Publication, agreement and approval dates are unknown; filename dates are not used.',
    'No verified coordinates or geometry; no granted-licence register.',
    'Groups may contain different versions; inventory placement does not establish the latest legal status.',
]


def _norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def _phase(title):
    t = _norm(title)
    if re.search(r'aprovacio definitiva|aprovat definitivament|aprovada definitivament', t):
        return 'aprobación definitiva'
    if 'aprovacio inicial' in t:
        return 'aprobación inicial'
    return None


def _group(title, url):
    """Only merge reviewed equivalences; same area alone is not an identity."""
    t = _norm(title)
    if 'jardi' in t and 'puig i cadafalch' in t:
        return 'rehabilitacio-jardi-casa-puig-i-cadafalch'
    if 'reurbanitzacio' in t and 'cruilla' in t and 'puig i cadafalch' in t:
        return 'reurbanitzacio-cruilla-puig-i-cadafalch-farrero-mataro'
    if 'reparcellacio' in t.replace('·', '') and 'pa-13' in t and 'serra llado' in t:
        return 'reparcellacio-pa13-serra-llado'
    return url


class ArgentonaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE.rstrip('/'))

    @staticmethod
    def parse_inventory(html, source_url, inventory):
        soup = BeautifulSoup(html, 'html.parser')
        body = soup.select_one('.document #cos')
        if body is None:
            raise ValueError('Argentona document inventory markup missing')
        # These are single-page inventories. Fail closed if pagination appears;
        # there is no arbitrary item or page limit silently cutting off results.
        for a in soup.select('a[href]'):
            label = _norm(a.get_text(' ', strip=True))
            if ('next' in a.get('rel', []) or label in {'seguent', 'seguent >', 'siguiente', 'next', '»', '›'}
                    or re.search(r'[?&](?:page|pagina|pag|offset|start)=', a['href'], re.I)):
                raise ValueError('Pagination detected: extend Argentona crawler')
        if soup.select('.pagination, .paginacio, .paginacion'):
            raise ValueError('Pagination container detected')
        docs = []
        for a in body.select('a[href]'):
            title = a.get_text(' ', strip=True)
            t = _norm(title)
            # Exclude financing, administrative notices, generic plans and
            # standalone draft deeds, rather than treating all PDFs as projects.
            if not re.match(r'^(?:(?:aprovacio (?:inicial|definitiva)(?: del?| de)?|actualitzacio del|text refos del) )?(?:projecte|avantprojecte|memoria valorada|modificacio puntual del poum)\b', t):
                if not (t.startswith('escriptura de reparcel') and 'pa-13' in t):
                    continue
            if 'contribucions especials' in t:
                continue
            url = urljoin(source_url, a['href'])
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname != 'argentona.cat' or not parsed.path.lower().endswith('.pdf'):
                raise ValueError('Unexpected project document URL: ' + url)
            docs.append({'titulo': title, 'url': url, 'source_url': source_url,
                         'inventario': inventory, 'fase': _phase(title)})
        if not docs:
            raise ValueError('No supported Argentona project documents')
        return docs

    @staticmethod
    def group_documents(documents):
        groups = {}
        for doc in documents:
            key = _group(doc['titulo'], doc['url'])
            if key not in groups:
                groups[key] = []
            if doc not in groups[key]:
                groups[key].append(doc)
        rows = []
        for key, docs in groups.items():
            phases = {d['fase'] for d in docs if d['fase']}
            # Conflicting versions remain visible at document level. Do not
            # promote an old definitive version over a newly exposed text.
            phase = docs[0]['fase'] if len(docs) == 1 else None
            title = docs[0]['titulo']
            t = _norm(title)
            kind = 'planeamiento_urbanistico' if 'poum' in t or 'reparcel' in t else 'proyecto_obra'
            rows.append({
                'id': 'argentona-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Argentona', 'codigo_ine': '08009', 'provincia': 'Barcelona',
                'titulo': title, 'tipo': kind, 'fase': phase,
                'fases_documentadas': sorted(phases),
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                'url': docs[0]['source_url'], 'url_documento': docs[0]['url'],
                'source': 'ayuntamiento', 'origen': 'inventarios_documentos_urbanismo',
                'documentos': docs, 'source_urls': list(dict.fromkeys(d['source_url'] for d in docs)),
                'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                'cobertura': 'parcial',
            })
        return sorted(rows, key=lambda r: r['id'])

    def _fetch(self, url):
        with requests.get(url, timeout=40, stream=True,
                          headers={'User-Agent': 'municipio-argentona/1.0'}) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'argentona.cat':
                raise ValueError('Unexpected redirect outside municipal source')
            if 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Inventory is not HTML')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('Inventory exceeds response size limit')
                chunks.append(chunk)
            content = b''.join(chunks)
        capture_dir = self.config.get('capture_dir')
        if capture_dir:
            path = Path(capture_dir)
            path.mkdir(parents=True, exist_ok=True)
            name = next(name for name, source in SOURCES.items() if source == url)
            (path / (name + '.html')).write_bytes(content)
        # BeautifulSoup reads the declared charset (live source: ISO-8859-1).
        return content

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        documents = []
        for inventory, url in SOURCES.items():
            documents.extend(self.parse_inventory(self._fetch(url), url, inventory))
        rows = self.group_documents(documents)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'documents': len(documents),
                'source_urls': list(SOURCES.values()), 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete current snapshot; state is not a temporal cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
