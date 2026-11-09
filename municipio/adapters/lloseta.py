"""Lloseta dossiers in the official CAIB simplified environmental inventory.

This is a document inventory snapshot, not a register of granted licences or
an assertion that listed dossiers remain pending environmental assessment.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = 'https://www.caib.es/sites/serveiassessoramentambiental/ca/'
SOURCE = ROOT + 'publicacio_de_documents_ambientals_en_tramitacia_davaluacia_simplificada/'
EXPEDIENTE = re.compile(r'^(\d+[ae]/\d{4})\s+(.+)$', re.I)
LIMITATIONS = [
    'Partial coverage: only Lloseta dossiers in the CAIB simplified environmental document inventory.',
    'The inventory may retain historical dossiers; listing does not prove current procedural status or approval.',
    'Publication, agreement and approval dates are not supplied by these HTML entries and remain null.',
    'No verified project geometry; coordinates remain null. No granted-licence register extracted.',
    'Ordinary environmental assessment, environmental resolutions and other municipal works are outside this snapshot.',
]


def _official(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'www.caib.es' or not parsed.path.startswith('/sites/serveiassessoramentambiental/'):
        raise ValueError('Unexpected source URL: ' + url)
    return url


def _content(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    blocks = soup.select('main .imc--contenido-html')
    if len(blocks) != 1 or not blocks[0].select_one('h1'):
        raise ValueError('Missing unambiguous CAIB content block')
    # The reviewed inventory is a single complete HTML table. Stop if the
    # publisher introduces paging, rather than silently accepting its first page.
    for a in soup.select('a[href]'):
        text = a.get_text(' ', strip=True).casefold()
        query = parse_qs(urlparse(a['href']).query)
        if ('next' in (a.get('rel') or []) or text in {'next', 'siguiente', 'següent', 'següents', 'veure més'}
                or any(k.lower() in {'page', 'pagina', 'offset', 'start'} for k in query)
                or a.find_parent(class_=re.compile(r'pag(?:in|er)', re.I))):
            raise ValueError('Pagination detected; review crawler before extracting')
    return soup, blocks[0]


class LlosetaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug='lloseta', config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://ajlloseta.net')

    @staticmethod
    def parse_inventory(html: str) -> list[dict[str, str]]:
        soup, content = _content(html)
        if "avaluació simplificada" not in content.h1.get_text(' ', strip=True).casefold():
            raise ValueError('Unexpected environmental inventory heading')
        dossiers = {}
        for a in content.select('a[href]'):
            title = a.get_text(' ', strip=True)
            if not re.search(r'\bLloseta\b', title, re.I):
                continue
            match = EXPEDIENTE.fullmatch(title)
            if not match:
                raise ValueError('Unrecognized Lloseta inventory entry: ' + title)
            exp = match[1].lower()
            # The table sometimes links straight to a PDF. The site navigation
            # provides the corresponding document dossier, matched by its actual
            # environmental identifier, never by a guessed URL.
            detail_urls = set()
            for link in soup.select('a[href]'):
                other = EXPEDIENTE.fullmatch(link.get_text(' ', strip=True))
                url = urljoin(SOURCE, link['href'].strip())
                if other and other[1].lower() == exp and re.search(r'/ca/[^/]+/$', url):
                    detail_urls.add(_official(url))
            if len(detail_urls) != 1:
                raise ValueError('Missing or ambiguous dossier for ' + exp)
            entry = {'expediente': exp, 'titulo': title, 'url': detail_urls.pop(),
                     'url_inventario_enlace': _official(urljoin(SOURCE, a['href'].strip()))}
            if exp in dossiers and dossiers[exp] != entry:
                raise ValueError('Conflicting inventory entries for ' + exp)
            dossiers[exp] = entry
        if not dossiers:
            raise ValueError('No usable Lloseta dossiers in inventory')
        return [dossiers[k] for k in sorted(dossiers)]

    @staticmethod
    def parse_dossier(html: str, entry: dict[str, str]) -> dict[str, Any]:
        _, content = _content(html)
        title = content.h1.get_text(' ', strip=True)
        match = EXPEDIENTE.fullmatch(title)
        if not match or match[1].lower() != entry['expediente'] or not re.search(r'\bLloseta\b', title, re.I):
            raise ValueError('Dossier identity does not match inventory')
        docs = {}
        for a in content.select('a[href]'):
            url = _official(urljoin(entry['url'], a['href'].strip()))
            if 'archivopub.do' not in urlparse(url).path:
                raise ValueError('Unreviewed dossier link: ' + url)
            identifier = parse_qs(urlparse(url).query).get('id', [])
            if len(identifier) != 1 or not identifier[0].isdigit():
                raise ValueError('Missing document identifier')
            doc = {'titulo': a.get_text(' ', strip=True), 'url': url,
                   'id_documento_caib': identifier[0], 'url_procedencia': entry['url']}
            if not doc['titulo']:
                raise ValueError('Untitled source document')
            docs.setdefault(identifier[0], doc)
        if not docs:
            raise ValueError('Dossier exposes no documents')
        return {
            'id': 'lloseta-caib-' + entry['expediente'].replace('/', '-'),
            'municipio': 'Lloseta', 'codigo_ine': '07029', 'provincia': 'Illes Balears',
            'titulo': title, 'expediente_ambiental': entry['expediente'],
            'tipo': 'planeamiento_urbanistico' if 'e/' in entry['expediente'] else 'proyecto',
            'fase': None, 'fecha': None, 'fecha_publicacion': None,
            'fecha_acuerdo': None, 'fecha_aprob': None,
            'url': entry['url'], 'url_inventario': SOURCE,
            'url_inventario_enlace': entry['url_inventario_enlace'],
            'source': 'govern_illes_balears', 'organismo_fuente': "Servei d'Avaluació Ambiental (CAIB)",
            'origen': 'inventario_documentos_evaluacion_ambiental_simplificada',
            'documentos': list(docs.values()),
            'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
            'limitaciones': LIMITATIONS,
        }

    def _fetch(self, session, url: str) -> str:
        _official(url)
        with session.get(url, timeout=(15, 60), stream=True) as response:
            response.raise_for_status()
            _official(response.url)
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 8_000_000:
                    raise ValueError('Source response exceeds 8 MB; no partial parsing')
                chunks.append(chunk)
            raw = b''.join(chunks)
            capture_dir = self.config.get('capture_dir')
            if capture_dir:
                import hashlib
                path = Path(capture_dir)
                path.mkdir(parents=True, exist_ok=True)
                (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')).write_bytes(raw)
            return raw.decode('utf-8-sig')

    @staticmethod
    def _write(out_jsonl, rows):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.Session() as session:
            session.headers['User-Agent'] = 'municipio-lloseta/1.0 (public document inventory)'
            entries = self.parse_inventory(self._fetch(session, SOURCE))
            rows = [self.parse_dossier(self._fetch(session, entry['url']), entry) for entry in entries]
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE] + [e['url'] for e in entries],
                'limitations': LIMITATIONS, 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete refresh of this inventory; no date-based cutoff or record cap.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence register'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
