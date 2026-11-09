"""Municipal PGOU phase inventory; one instrument with all current-phase documents."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.balmaseda.eus'
PAGES = '/es-ES/Servicios/Urbanismo/Paginas/'
SOURCE = BASE + PAGES + 'ordenacion-estructural-pgou.aspx'


def canonical(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, quote(unquote(parts.path), safe='/'), parts.query, ''))


class BalmasedaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def _main(html):
        soup = BeautifulSoup(html, 'html.parser')
        main = soup.select_one('#main-content')
        if main is None:
            raise ValueError('Missing municipal main content')
        for a in main.select('a[href]'):
            label = a.get_text(' ', strip=True).casefold()
            if (label in {'siguiente', 'next', 'hurrengoa', '›', '»'}
                    or 'next' in a.get('rel', [])
                    or re.search(r'(?:page|pagina|pagenum|paged)=', a['href'], re.I)):
                raise ValueError('Unreviewed pagination; refusing partial PGOU snapshot')
        return main

    @classmethod
    def parse_inventory(cls, html):
        main = cls._main(html)
        if 'PGOU' not in main.get_text(' ', strip=True):
            raise ValueError('Missing PGOU inventory identity')
        phases = {}
        for a in main.select('a[href]'):
            url = canonical(urljoin(SOURCE, a['href']))
            match = re.fullmatch(re.escape(BASE + PAGES) + r'pgou_fase(\d+)\.aspx', url, re.I)
            if match:
                phases[int(match[1])] = url
        if not phases or max(phases) != 6:
            raise ValueError('Current PGOU phase changed; review instrument semantics')
        return phases

    @classmethod
    def parse_page(cls, html, source_url):
        main = cls._main(html)
        content = main.select_one('[id$="content__ControlWrapper_RichHtmlField"]')
        if content is None:
            raise ValueError('Missing PGOU document content')
        # SharePoint also renders document lists in embedded web parts beside the rich field.
        content = main.select_one('#SectionBody') or content
        for navigation in content.select('.viewMore'):
            navigation.decompose()
        documents, children = {}, {}
        for a in content.select('a[href]'):
            href = a['href'].strip()
            if not href or href.startswith('#'):
                continue
            url = canonical(urljoin(source_url, href))
            parts = urlsplit(url)
            title = a.get_text(' ', strip=True) or unquote(parts.path.rsplit('/', 1)[-1])
            if parts.hostname != 'www.balmaseda.eus' or parts.scheme != 'https':
                raise ValueError('Unexpected external PGOU content link: ' + url)
            if parts.path.lower().endswith('.pdf'):
                documents[url] = {'titulo': title, 'url': url, 'source_page': source_url}
            elif parts.path.startswith(PAGES) and parts.path.lower().endswith('.aspx'):
                children[url] = title
            else:
                raise ValueError('Unsupported PGOU content link: ' + url)
        if not documents and not children:
            raise ValueError('Empty PGOU documentation page')
        return list(documents.values()), list(children)

    def _fetch(self, session, url):
        response = session.get(url, timeout=30)
        response.raise_for_status()
        if urlsplit(response.url).hostname != 'www.balmaseda.eus':
            raise ValueError('Municipal source redirected outside official host')
        if 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('Expected municipal HTML inventory')
        capture = self.config.get('evidence_dir')
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(response.content)
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-balmaseda/1.0 (public planning inventory)'
            phases = self.parse_inventory(self._fetch(session, SOURCE))
            pending = [phases[6]]
            visited, documents = [], {}
            while pending:
                url = pending.pop(0)
                if url in visited:
                    continue
                if len(visited) >= 100:
                    raise ValueError('PGOU graph exceeds reviewed safety bound; no output written')
                docs, children = self.parse_page(self._fetch(session, url), url)
                visited.append(url)
                for doc in docs:
                    previous = documents.setdefault(doc['url'], doc)
                    origins = previous.setdefault('source_pages', [previous['source_page']])
                    if url not in origins:
                        origins.append(url)
                pending.extend(child for child in children if child not in visited)
        certificates = [d for d in documents.values()
                        if 'certificado' in d['titulo'].casefold() and 'aprobación inicial' in d['titulo'].casefold()]
        if len(certificates) != 1:
            raise ValueError('Missing or ambiguous initial approval certificate')
        row = {
            'id': 'balmaseda-pgou', 'municipio': 'Balmaseda', 'codigo_ine': '48090',
            'provincia': 'Bizkaia', 'titulo': 'Plan General de Ordenación Urbana de Balmaseda (PGOU)',
            'tipo': 'planeamiento_urbanistico', 'fase': 'aprobación inicial',
            'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': SOURCE, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_pgou',
            'documentos': list(documents.values()), 'source_urls': [SOURCE] + visited,
            'fases_documentadas': [{'fase': n, 'url': url} for n, url in sorted(phases.items())],
            'fase_source_url': certificates[0]['url'],
            'descripcion': 'Instrumento único; documentación urbanística y ambiental de la fase 6. '
                           'Los borradores, planos y anexos son documentos del PGOU, no proyectos ni licencias independientes.',
            'coverage': 'Parcial: solo PGOU en tramitación, fase 6; fases anteriores enlazadas sin extraer sus documentos. '
                        'Fechas no extraídas del PDF; publicación municipal desconocida.',
            'lat': None, 'lon': None, 'geometry': None, 'geometry_status': 'unavailable',
            'publication_ready': False,
        }
        self._write(out_jsonl, [row])
        return {'status': 'ok', 'rows': 1, 'documents': len(documents), 'source_urls': row['source_urls']}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
