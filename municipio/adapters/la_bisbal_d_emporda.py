"""Complete single-page Obres locals inventory; one row per physical project."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://www.labisbal.cat/serveis/urbanisme/obres-locals/'


class LaBisbalDEmpordaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://labisbal.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.select('a[href]'):
            rel = a.get('rel', [])
            if ('next' in rel or a.get_text(' ', strip=True).casefold() in
                    {'següent', 'següents', 'siguiente', 'next', 'carrega més', 'load more'}):
                raise ValueError('Paginated inventory requires crawler review')
        if soup.select('.pagination, .page-numbers, [data-infinite-scroll]'):
            raise ValueError('Pagination or lazy inventory requires crawler review')
        heading = next((h for h in soup.select('h1')
                        if h.get_text(' ', strip=True) == 'Obres locals'), None)
        content = heading.find_parent(class_='elementor-widget-wrap') if heading else None
        if not content or not any(h.get_text(' ', strip=True) == 'En exposició pública'
                                  for h in content.select('h2')):
            raise ValueError('Missing municipal public-works inventory')
        groups = {}
        for a in content.select('ul a[href]'):
            title = ' '.join(a.get_text(' ', strip=True).split())
            url = urljoin(SOURCE, a['href'])
            parsed = urlsplit(url)
            if (parsed.scheme != 'https' or parsed.hostname not in {'labisbal.cat', 'www.labisbal.cat'}
                    or not parsed.path.startswith('/wp-content/uploads/')
                    or not parsed.path.lower().endswith('.pdf')):
                raise ValueError('Unexpected inventory link: ' + url)
            initial = title.startswith('APROVACIO INICIAL ')
            base = title.removeprefix('APROVACIO INICIAL ')
            base = re.sub(r'_(?:PART[ _]\d+|PRESSUPOST|PLÀNOLS|PLEC DE CONDICIONS)$', '', base)
            if not re.match(r"^PROJECT(?:E (?:DE |D')|_URB )", base):
                raise ValueError('Unrecognized project document: ' + title)
            # Only explicit document suffixes are removed. Nearby streets and
            # squares remain distinct projects, and unknown titles fail closed.
            key = base.casefold()
            if key not in groups:
                groups[key] = {
                    'id': 'la-bisbal-d-emporda-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                    'municipio': "La Bisbal d'Empordà", 'codigo_ine': '17022',
                    'provincia': 'Girona', 'titulo': base, 'tipo': 'obra_publica',
                    'fase': 'aprobación inicial' if initial else 'exposición pública',
                    'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': None,
                    'fecha_aprob': None, 'url': SOURCE, 'source': 'ayuntamiento',
                    'origen': 'inventario_obres_locals', 'documentos': [],
                    'lat': None, 'lon': None, 'geometry': None,
                    'publication_ready': False,
                    'geometry_status': 'No verified project geometry extracted',
                }
            row = groups[key]
            if row['fase'] != ('aprobación inicial' if initial else 'exposición pública'):
                raise ValueError('Conflicting project stages')
            if url not in {d['url'] for d in row['documentos']}:
                row['documentos'].append({'titulo': title, 'url': url, 'source_url': SOURCE})
        if not groups:
            raise ValueError('Empty inventory; review source before replacing output')
        return list(groups.values())

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        # The www entry redirects to the canonical municipal host. No cached
        # fixture is ever used as a substitute for a successful live request.
        with requests.get(SOURCE, timeout=(15, 45), stream=True,
                          headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            if urlsplit(response.url).hostname not in {'labisbal.cat', 'www.labisbal.cat'}:
                raise ValueError('Unexpected source redirect')
            payload = bytearray()
            for chunk in response.iter_content(65536):
                payload.extend(chunk)
                if len(payload) > 2_000_000:
                    raise ValueError('Source exceeds reviewed response size')
            html = payload.decode('utf-8')
        rows = self.parse_projects(html)
        if self.config.get('evidence_dir'):
            capture = Path(self.config['evidence_dir']) / 'obres-locals.html'
            capture.parent.mkdir(parents=True, exist_ok=True)
            capture.write_bytes(payload)
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temporary = out_jsonl.with_suffix(out_jsonl.suffix + '.tmp')
        temporary.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        temporary.replace(out_jsonl)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE],
                'documents': sum(len(r['documentos']) for r in rows), 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        # Complete current snapshot, not a historical or incremental claim.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text('', encoding='utf-8')
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified granted-licence inventory'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
