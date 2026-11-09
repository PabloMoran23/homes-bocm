"""Complete snapshot of the municipality's curated public-works inventory."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = 'https://www.santpol.cat/'
SOURCE = BASE + 'node/14628'
SECTIONS = (
    'Projectes en exposició pública',
    'Projectes en tràmit de contractació',
    'Projectes en execució',
    'Projectes executats',
)
SCHOOL_TITLE = "Projecte d'ampliació de l'escola Sant Pau per a la seva conversió en institut escola"


def _norm(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if not unicodedata.combining(c))


def _identity(title: str) -> tuple[str, str]:
    title = re.sub(r'\s*\(addenda\)\s*$', '', title, flags=re.I)
    normalized = _norm(title)
    # The municipal inventory links three versions of the school extension.
    # Keep all original titles/URLs, including its overview page, in one work.
    if "escola sant pau" in normalized and re.search(r"ampli[ac]+cio", normalized):
        title = SCHOOL_TITLE
    return _norm(title), title


class SantPolDeMarAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or BASE.rstrip('/'))

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        # This is a single curated page. Fail explicitly if it becomes paginated.
        for a in soup.select('a[href]'):
            label = _norm(a.get_text(' ', strip=True))
            if ('next' in a.get('rel', []) or label in {'seguent', 'seguents', 'siguiente', 'next', '»', '›'}
                    or a.find_parent(class_=re.compile(r'pag(?:er|ination|inacio)', re.I))):
                if a['href'] not in {'', '#'}:
                    raise ValueError('Inventory is paginated; crawler must be extended')
        candidates = [c for c in soup.select('.cos_fitxa')
                      if any(h.get_text(' ', strip=True) == SECTIONS[0] for h in c.find_all('h2'))]
        if len(candidates) != 1:
            raise ValueError('Missing or ambiguous municipal public-works inventory')
        content = candidates[0]
        headings = [h.get_text(' ', strip=True) for h in content.find_all('h2')]
        if headings != list(SECTIONS):
            raise ValueError('Changed public-works sections; review source coverage')
        named_urls = {urljoin(BASE, a['href']) for a in content.select('a[href]')
                      if a.get_text(' ', strip=True)}
        rows: dict[str, dict[str, Any]] = {}
        seen_docs: dict[str, str] = {}
        section = None
        section_counts = dict.fromkeys(SECTIONS, 0)
        for element in content.find_all(['h2', 'a']):
            if element.name == 'h2':
                section = element.get_text(' ', strip=True)
                continue
            if not element.has_attr('href'):
                raise ValueError('Work document missing href')
            title = ' '.join(element.get_text(' ', strip=True).split())
            url = urljoin(BASE, element['href'])  # site uses root-relative semantics via <base>
            if not title:
                # A known stray empty anchor to Parc del Litoral also occurs
                # beside the pumping-station project. Never attach it there.
                if url in named_urls:
                    continue
                raise ValueError('Unnamed document without a named inventory entry')
            if section is None or not re.match(r'^(Projecte\b|Memòria valorada\b)', title, re.I):
                raise ValueError('Unexpected entry in public-works inventory')
            parsed = urlparse(url)
            if (parsed.scheme != 'https' or parsed.hostname not in {'www.santpol.cat', 'governobert.santpol.cat'}
                    or not (parsed.path.lower().endswith('.pdf') or url == BASE + 'institutescola')):
                raise ValueError('Unexpected public-works document URL')
            key, main_title = _identity(title)
            if url in seen_docs and seen_docs[url] != key:
                raise ValueError('One document assigned to conflicting works')
            seen_docs[url] = key
            if key not in rows:
                rows[key] = {
                    'id': 'sant-pol-de-mar-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                    'municipio': 'Sant Pol de Mar', 'provincia': 'Barcelona', 'codigo_ine': '08235',
                    'titulo': main_title, 'tipo': 'proyecto_obra_publica',
                    # The source publishes project documents, without dossier
                    # identifiers. Do not claim an expediente or granted act.
                    'source_entity_type': 'documento',
                    'fase': section, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_obras',
                    'url': SOURCE, 'url_documento': url, 'documentos': [],
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None, 'fecha_aprob': None,
                    'lat': None, 'lon': None, 'geometry': None, 'publication_ready': False,
                    'geometry_status': 'No verified work geometry extracted from the inventory',
                    'coverage': 'Municipal public-works inventory only; source categories are not verified completion or approval dates',
                }
            row = rows[key]
            if row['fase'] != section:
                raise ValueError('Versions of one work have conflicting inventory phases')
            if not any(d['url'] == url for d in row['documentos']):
                row['documentos'].append({'titulo': title, 'url': url, 'source_url': SOURCE,
                                           'seccion_fuente': section,
                                           'tipo': 'pdf' if parsed.path.lower().endswith('.pdf') else 'pagina_proyecto'})
            section_counts[section] += 1
        if not rows or not all(section_counts.values()):
            raise ValueError('Empty public-works section; review inventory before accepting a snapshot')
        # Prefer the main document over an addendum even if the addendum is first.
        for row in rows.values():
            main = next((d for d in row['documentos'] if '(addenda)' not in d['titulo'].lower()), None)
            row['url_documento'] = main['url'] if main else row['documentos'][0]['url']
        return list(rows.values())

    @staticmethod
    def _write(path: Path, rows: list[dict[str, Any]]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=35, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-sant-pol-de-mar/1.0')
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != 'www.santpol.cat':
                raise ValueError('Municipal inventory redirected outside the official website')
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 3_000_000:
                    raise ValueError('Municipal inventory exceeds reviewed response size')
            # The current municipal server declares ISO-8859-1, not UTF-8.
            html = data.decode(response.encoding or 'utf-8')
        rows = self.parse_projects(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'works-live.html').write_bytes(data)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'documents': sum(len(r['documentos']) for r in rows),
                'publication_ready': False, 'coverage': 'Complete single-page public-works inventory snapshot'}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Refresh the full inventory; preserve no unverified incremental cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
