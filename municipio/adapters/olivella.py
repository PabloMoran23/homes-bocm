"""Olivella's current municipal project-document inventory (not a licence register)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://seu-e.cat/ca/web/olivella/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme'
CATEGORIES = {
    'projectes-d-obres-aprovacio-inicial-205': ('proyecto_obras', 'aprobación inicial'),
    'projectes-d-obres-aprovacio-definitiva-206': ('proyecto_obras', 'aprobación definitiva'),
    'projectes-de-reparcel-lacio-aprovacio-inicial-214': ('reparcelacion', 'aprobación inicial'),
    'projectes-de-reparcel-lacio-aprovacio-definitiva-215': ('reparcelacion', 'aprobación definitiva'),
    'pla-especial-urbanistic-aprovacio-inicial-216': ('plan_especial', 'aprobación inicial'),
    'pla-especial-urbanistic-aprovacio-definitiva-217': ('plan_especial', 'aprobación definitiva'),
    'projecte-d-obres-actualitzacio-preus-218': ('proyecto_obras', 'aprobación definitiva de actualización de precios'),
    'plans-urbanistics-aprovacio-inicial-221': ('plan', 'aprobación inicial'),
    'plans-urbanistics-aprovacio-definitiva-222': ('plan', 'aprobación definitiva'),
}
LIMITATIONS = [
    'Current snapshot of nine municipal project/plan approval sections; not a historical or exhaustive works register.',
    'POUM, urban regulations, equipment strategy, audit, mobility study and technical studies are outside this extraction.',
    'Page update dates are retained only as fecha_actualizacion_fuente; publication and agreement dates are unverified and null.',
    'Documents are linked, not interpreted as executed works or granted licences. Plana Novella source omits personal-data annexes.',
    'No verified project coordinates or geometry; publication_ready=false. No licence register extracted.',
]


def _soup(html):
    soup = BeautifulSoup(html, 'html.parser')
    # These reviewed pages are unpaginated. Fail closed if pagination appears.
    for a in soup.select('a[href]'):
        label = a.get_text(' ', strip=True).casefold()
        if (a.get('rel') and 'next' in a['rel']) or label in {'següent', 'següent »', 'siguiente', 'next', '›', '»'} or re.search(r'(?:[?&](?:_.*_cur|cur|page|start)=)', a['href']):
            if a['href'] not in {'', '#', 'javascript:;'}:
                raise ValueError('Pagination detected; extend crawler before accepting partial output')
    return soup


class OlivellaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://www.olivella.cat')

    @staticmethod
    def parse_inventory(html):
        soup = _soup(html)
        urls = {urljoin(SOURCE, a['href']) for a in soup.select('a[href]')}
        expected = [SOURCE + '/' + key for key in CATEGORIES]
        if not set(expected).issubset(urls):
            raise ValueError('Official Olivella inventory missing reviewed project categories')
        return expected

    @staticmethod
    def parse_category(html, url):
        key = url.rsplit('/', 1)[-1]
        tipo, fase = CATEGORIES[key]
        soup = _soup(html)
        # Exclude generic transparency help/navigation articles, retaining all
        # actual content articles, including explicitly empty sections.
        articles = [a for a in soup.select('.journal-content-article')
                    if not a.select_one('.item_indicador, .accessdirecte_element')]
        if not articles:
            raise ValueError('Missing municipal content container')
        rows = []
        for article in articles:
            for script in article.select('script, style'):
                script.decompose()
            footer = article.select_one('.datatable_info_footer')
            updated = None
            if footer:
                match = re.search(r'Actualització:\s*(\d{2}/\d{2}/\d{4})', footer.get_text(' ', strip=True))
                if match:
                    updated = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
                footer.decompose()
            description = article.get_text(' ', strip=True)
            if not description:
                continue
            docs = {}
            for a in article.select('a[href]'):
                doc_url = urljoin(url, a['href'])
                if urlparse(doc_url).hostname != 'seu-e.cat' or not urlparse(doc_url).path.startswith('/documents/1125140/'):
                    raise ValueError('Unreviewed link in project content')
                title = re.sub(r'^Descarrega\s+', '', a.get_text(' ', strip=True))
                docs[doc_url] = {'titulo': title, 'url': doc_url, 'source_url': url}
            if not docs:
                raise ValueError('Nonempty project content has no supporting documents')
            documents = list(docs.values())
            if key == 'projectes-d-obres-aprovacio-inicial-205':
                # The reviewed list has distinct complete projects, not annexes.
                if any(not re.match(r'^(Projecte obres|MEMORIA I ANNEXOS PROJECTE OBRES)\b', d['titulo'], re.I) for d in documents):
                    raise ValueError('Initial works document grouping needs review')
                groups = [[d] for d in documents]
            else:
                principals = [d for d in documents if not re.match(r'^(ANNEX\b|NOTA ACLARIDORA\b)', d['titulo'], re.I)]
                if len(principals) != 1:
                    raise ValueError('Ambiguous instrument/document grouping')
                groups = [[principals[0]] + [d for d in documents if d != principals[0]]]
            paragraphs = [p.get_text(' ', strip=True) for p in article.select('p') if p.get_text(strip=True)]
            exp = re.search(r'\b\d{4}-\d{4}/\d{4}\b', ' '.join(paragraphs))
            for group in groups:
                identity = exp[0] if exp else group[0]['url'].rsplit('/', 1)[-1]
                rows.append({
                    'id': 'olivella-proy-' + hashlib.sha256(identity.encode()).hexdigest()[:16],
                    'municipio': 'Olivella', 'provincia': 'Barcelona', 'codigo_ine': '08148',
                    'titulo': group[0]['titulo'], 'tipo': tipo, 'fase': fase,
                    'expediente': exp[0] if exp else None,
                    'descripcion': description, 'fecha': None, 'fecha_publicacion': None,
                    'fecha_acuerdo': None, 'fecha_aprob': None,
                    'fecha_actualizacion_fuente': updated,
                    'url': url, 'url_documento': group[0]['url'], 'documentos': group,
                    'source': 'ayuntamiento', 'origen': 'inventario_municipal_urbanismo',
                    'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                    'geometry_status': 'sin geometría de proyecto verificada',
                })
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        sources = []
        def fetch(url):
            response = requests.get(url, timeout=45, headers={'User-Agent': 'municipio-olivella/1.0'})
            response.raise_for_status()
            if urlparse(response.url).path != urlparse(url).path or 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Unexpected source redirect or content type')
            response.encoding = 'utf-8'
            sources.append(url)
            if self.config.get('evidence_dir'):
                directory = Path(self.config['evidence_dir'])
                directory.mkdir(parents=True, exist_ok=True)
                (directory / (url.rsplit('/', 1)[-1] + '.html')).write_text(response.text, encoding='utf-8')
            return response.text
        urls = self.parse_inventory(fetch(SOURCE))
        rows = []
        for url in urls:
            rows.extend(self.parse_category(fetch(url), url))
        if not rows:
            raise ValueError('No verified municipal projects available')
        # Prevent the same instrument being emitted twice on changed inventories.
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Instrument appears in multiple sections; review grouping')
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': sources, 'limitations': LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
