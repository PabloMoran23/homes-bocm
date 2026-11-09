"""Complete snapshot of the municipal POUM page, not a licence register."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = 'https://sils.cat/serveis-municipals/urbanisme-2/poum/'


class SilsAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=''):
        super().__init__(slug, config, base_url or 'https://sils.cat')

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.select_one('article#post-3217 .entry-content')
        if content is None or not soup.select_one('h1.entry-title') or soup.select_one('h1.entry-title').get_text(strip=True) != 'POUM':
            raise ValueError('Missing municipal POUM inventory')
        # This is a single inventory page. Refuse pagination rather than emit a
        # silently incomplete snapshot if the publisher changes its structure.
        if soup.select('a[rel~=next], link[rel~=next], .pagination, .page-links, .nav-links'):
            raise ValueError('Pagination requires review before extraction')
        rows = {}
        seen_lists = set()
        for p in content.find_all('p', recursive=False):
            title = p.get_text('', strip=True)
            if not p.find('strong'):
                continue  # introductory link to the separate normative inventory
            listing = p.find_next_sibling()
            if listing is None or listing.name != 'ul':
                raise ValueError('Instrument heading without document list')
            docs = []
            for a in listing.select('a[href]'):
                url = urljoin(SOURCE, a['href'])
                if urlparse(url).scheme not in {'https', 'http'}:
                    raise ValueError('Unsupported document URL')
                doc = {'titulo': a.get_text(' ', strip=True), 'url': url,
                       'url_indice': SOURCE, 'provenance': 'enlace publicado por el Ayuntamiento de Sils'}
                if not any(d['url'] == url for d in docs):
                    docs.append(doc)
            if not docs:
                raise ValueError('Instrument without documents')
            seen_lists.add(id(listing))
            is_poum = title.startswith('Podeu consultar el Pla Ordenació Urbanística Municipal')
            if is_poum:
                if len(docs) != 1 or not re.fullmatch(r'https://dtes\.gencat\.cat/rpucportal/#/consulta/detallExpedient/\d+', docs[0]['url']):
                    raise ValueError('Missing unambiguous POUM register dossier')
                title = 'Pla d’Ordenació Urbanística Municipal de Sils (POUM)'
                kind = 'POUM'
            elif re.match(r'^(Modificació|Exposició .*Modificació|Exposició modificació|Reparcel·lació)', title, re.I):
                kind = 'reparcelacion' if title.startswith('Reparcel·lació') else 'modificacion_planeamiento'
            else:
                raise ValueError('Unreviewed inventory heading: ' + title)
            phase = None
            if 'pendent d’aprovació' in title:
                phase = 'pendiente de aprobación'
            elif 'aprovació inicial' in title.lower():
                phase = 'aprobación inicial'
            agreement = None
            for doc in docs:
                match = re.search(r'aprovació Inicial Acord de Ple (\d{2}/\d{2}/\d{4})', doc['titulo'], re.I)
                if match:
                    agreement = datetime.strptime(match[1], '%d/%m/%Y').date().isoformat()
                    phase = 'aprobación inicial'
            key = docs[0]['url']
            if key in rows:
                raise ValueError('Duplicate primary instrument document; grouping needs review')
            rows[key] = {
                'id': 'sils-proy-' + hashlib.sha256(key.encode()).hexdigest()[:16],
                'municipio': 'Sils', 'codigo_ine': '17193', 'provincia': 'Girona',
                'titulo': title, 'tipo': kind, 'fase': phase,
                'fecha': None, 'fecha_publicacion': None, 'fecha_acuerdo': agreement,
                'fecha_aprob': None, 'url': SOURCE, 'url_documento': key,
                'documentos': docs, 'source': 'ayuntamiento', 'origen': 'inventario_municipal_poum',
                'descripcion': title, 'lat': None, 'lon': None, 'geometry': None,
                'publication_ready': False,
                'coverage': 'Inventario de la página POUM; no acredita vigencia ni estado actual de cada trámite',
            }
            if is_poum:
                rows[key]['rpuc_id'] = key.rsplit('/', 1)[-1]
        if not rows or not any(r['tipo'] == 'POUM' for r in rows.values()):
            raise ValueError('Empty or incomplete POUM inventory')
        if any(id(ul) not in seen_lists for ul in content.find_all('ul', recursive=False)):
            raise ValueError('Unassigned document list')
        return list(rows.values())

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=40, stream=True, headers={
            'User-Agent': self.config.get('user_agent', 'municipio-sils/1.0')
        }) as response:
            response.raise_for_status()
            payload = bytearray()
            for chunk in response.iter_content(65536):
                payload.extend(chunk)
                if len(payload) > 3_000_000:
                    raise ValueError('POUM inventory exceeds response limit')
            html = payload.decode('utf-8')
        rows = self.parse_projects(html)
        if self.config.get('capture_dir'):
            capture = Path(self.config['capture_dir'])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / 'poum-live.html').write_bytes(payload)
        self._write(out_jsonl, rows)
        return {'status': 'ok', 'rows': len(rows), 'source_urls': [SOURCE], 'publication_ready': False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {'status': 'disabled', 'rows': 0, 'reason': 'No verified public register of granted licences'}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
